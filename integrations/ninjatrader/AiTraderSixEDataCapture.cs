// Data-only indicator: no Account access and no order methods. Disabled by default.
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using AiTrader.MarketData;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class AiTraderSixEDataCapture : Indicator
    {
        private const int MaximumFiles = 2000;
        private BoundedCaptureWriter writer;
        private bool attempted;
        private bool stopped;
        private int filesOpened;
        private DateTime rotationEndUtc;
        private readonly object lifecycleGate = new object();

        [NinjaScriptProperty]
        [Display(Name = "Enable capture", Order = 0, GroupName = "Capture only")]
        public bool EnableCapture { get; set; }

        [NinjaScriptProperty]
        [Range(1, 60)]
        [Display(Name = "Maximum minutes per file", Order = 1, GroupName = "Capture only")]
        public int MaximumMinutes { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000000)]
        [Display(Name = "Maximum event records per file", Order = 2, GroupName = "Capture only")]
        public int MaximumEvents { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Feed label no credentials", Order = 3, GroupName = "Capture only")]
        public string FeedLabel { get; set; }

        // 0 = one file only (original behaviour). 1-24 = keep opening a fresh file after each
        // clean per-file limit until this many hours have passed since the first file opened.
        [NinjaScriptProperty]
        [Range(0, 24)]
        [Display(Name = "Total hours with rotating files (0 = single file)", Order = 4, GroupName = "Capture only")]
        public int TotalHours { get; set; }

        protected override void OnStateChange()
        {
            // NinjaTrader may deliver lifecycle transitions on different threads.
            lock (lifecycleGate) { HandleStateChange(); }
        }

        private void HandleStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "AiTraderSixEDataCapture";
                Description = "Bounded 6E/M6E Level 1 and Level 2 observation capture; never trades.";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true;
                IsSuspendedWhileInactive = false;
                EnableCapture = false;
                MaximumMinutes = 10;
                MaximumEvents = 250000;
                FeedLabel = "unverified-feed";
                TotalHours = 0;
            }
            else if (State == State.Realtime && EnableCapture && !attempted)
            {
                attempted = true;
                // A simulation trading account does NOT prove the chart feed is real-time.
                string market = Instrument.MasterInstrument.Name;
                if ((market != "6E" && market != "M6E")
                    || Instrument.FullName.IndexOf("##", StringComparison.Ordinal) >= 0
                    || MaximumMinutes < 1 || MaximumMinutes > 60
                    || TotalHours < 0 || TotalHours > 24)
                {
                    stopped = true;
                    Print("Capture refused: use a dated 6E or M6E contract and bounded durations.");
                    return;
                }
                rotationEndUtc = DateTime.UtcNow.AddHours(TotalHours);
                OpenWriter();
            }
            else if (State == State.Terminated)
            {
                stopped = true;
                if (writer != null) writer.Dispose();
            }
            else if (attempted && State != State.Realtime && writer != null)
            {
                stopped = true;
                writer.Fail("platform_state_changed");
            }
        }

        private void OpenWriter()
        {
            try
            {
                writer = new BoundedCaptureWriter(
                    Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "ai-trader-captures"),
                    "ninjatrader", Instrument.MasterInstrument.Name, Instrument.FullName,
                    "unverified", FeedLabel, BoundedCaptureWriter.Price(TickSize),
                    MaximumMinutes * 60, MaximumEvents);
                filesOpened++;
                Print("Capture-only file " + filesOpened + ": " + writer.FilePath);
            }
            catch (Exception)
            {
                writer = null;
                stopped = true;
                Print("Capture initialization failed; no retry was started.");
            }
        }

        // Returns the writer to use for this event, or null. A new file is opened only when the
        // previous one ended cleanly at a per-file limit; any failure ends the whole capture.
        private BoundedCaptureWriter ActiveWriter()
        {
            lock (lifecycleGate)
            {
                if (writer == null || stopped) return null;
                if (!writer.IsClosed) return writer;
                string reason = writer.CloseReason;
                bool cleanLimit = reason == "duration_limit" || reason == "event_limit"
                    || reason == "byte_limit";
                if (TotalHours == 0 || !cleanLimit || DateTime.UtcNow >= rotationEndUtc
                    || filesOpened >= MaximumFiles)
                {
                    stopped = true;
                    Print("Capture finished: " + (reason ?? "unknown") + " after " + filesOpened + " file(s).");
                    return null;
                }
                OpenWriter();
                return stopped ? null : writer;
            }
        }

        protected override void OnBarUpdate() { }

        protected override void OnMarketData(MarketDataEventArgs update)
        {
            if (State != State.Realtime || update.Instrument.FullName != Instrument.FullName) return;
            BoundedCaptureWriter active = ActiveWriter();
            if (active == null) return;
            if (update.IsReset) { active.Fail("feed_reset"); return; }
            string kind = update.MarketDataType == MarketDataType.Bid ? "bid"
                : update.MarketDataType == MarketDataType.Ask ? "ask"
                : update.MarketDataType == MarketDataType.Last ? "trade" : null;
            if (kind == null) return;
            try
            {
                active.Record(kind, new Dictionary<string, object> {
                    { "price", BoundedCaptureWriter.Price(update.Price) },
                    { "size", update.Volume },
                    { "provider_time_text", update.Time.ToString("O", CultureInfo.InvariantCulture) }
                });
            }
            catch (Exception) { active.Fail("invalid_market_event"); }
        }

        protected override void OnMarketDepth(MarketDepthEventArgs update)
        {
            if (State != State.Realtime || update.Instrument.FullName != Instrument.FullName) return;
            BoundedCaptureWriter active = ActiveWriter();
            if (active == null) return;
            if (update.IsReset) { active.Fail("feed_reset"); return; }
            string side = update.MarketDataType == MarketDataType.Bid ? "bid"
                : update.MarketDataType == MarketDataType.Ask ? "ask" : null;
            if (side == null) { active.Fail("invalid_depth_side"); return; }
            try
            {
                active.Record("depth", new Dictionary<string, object> {
                    { "side", side }, { "operation", update.Operation.ToString().ToLowerInvariant() },
                    { "position", update.Position }, { "price", BoundedCaptureWriter.Price(update.Price) },
                    { "size", update.Volume },
                    { "provider_time_text", update.Time.ToString("O", CultureInfo.InvariantCulture) }
                });
            }
            catch (Exception) { active.Fail("invalid_depth_event"); }
        }
    }
}
