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
        private BoundedCaptureWriter writer;
        private bool attempted;
        private readonly object lifecycleGate = new object();

        [NinjaScriptProperty]
        [Display(Name = "Enable capture", Order = 0, GroupName = "Capture only")]
        public bool EnableCapture { get; set; }

        [NinjaScriptProperty]
        [Range(1, 60)]
        [Display(Name = "Maximum minutes", Order = 1, GroupName = "Capture only")]
        public int MaximumMinutes { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000000)]
        [Display(Name = "Maximum event records", Order = 2, GroupName = "Capture only")]
        public int MaximumEvents { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Feed label no credentials", Order = 3, GroupName = "Capture only")]
        public string FeedLabel { get; set; }

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
                Description = "Bounded 6E Level 1 and Level 2 observation capture; never trades.";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true;
                IsSuspendedWhileInactive = false;
                EnableCapture = false;
                MaximumMinutes = 10;
                MaximumEvents = 250000;
                FeedLabel = "unverified-feed";
            }
            else if (State == State.Realtime && EnableCapture && !attempted)
            {
                attempted = true;
                // A simulation trading account does NOT prove the chart feed is real-time.
                if (Instrument.MasterInstrument.Name != "6E"
                    || Instrument.FullName.IndexOf("##", StringComparison.Ordinal) >= 0
                    || MaximumMinutes < 1 || MaximumMinutes > 60)
                { Print("Capture refused: use a dated 6E contract and bounded duration."); return; }
                try
                {
                    writer = new BoundedCaptureWriter(
                        Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "ai-trader-captures"),
                        "ninjatrader", "6E", Instrument.FullName, "unverified", FeedLabel,
                        BoundedCaptureWriter.Price(TickSize), MaximumMinutes * 60, MaximumEvents);
                    Print("Capture-only file: " + writer.FilePath);
                }
                catch (Exception) { Print("Capture initialization failed; no retry was started."); }
            }
            else if (State == State.Terminated)
            {
                if (writer != null) writer.Dispose();
            }
            else if (attempted && State != State.Realtime && writer != null)
                writer.Fail("platform_state_changed");
        }

        protected override void OnBarUpdate() { }

        protected override void OnMarketData(MarketDataEventArgs update)
        {
            if (State != State.Realtime || writer == null || writer.IsClosed
                || update.Instrument.FullName != Instrument.FullName) return;
            if (update.IsReset) { writer.Fail("feed_reset"); return; }
            string kind = update.MarketDataType == MarketDataType.Bid ? "bid"
                : update.MarketDataType == MarketDataType.Ask ? "ask"
                : update.MarketDataType == MarketDataType.Last ? "trade" : null;
            if (kind == null) return;
            try
            {
                writer.Record(kind, new Dictionary<string, object> {
                    { "price", BoundedCaptureWriter.Price(update.Price) },
                    { "size", update.Volume },
                    { "provider_time_text", update.Time.ToString("O", CultureInfo.InvariantCulture) }
                });
            }
            catch (Exception) { writer.Fail("invalid_market_event"); }
        }

        protected override void OnMarketDepth(MarketDepthEventArgs update)
        {
            if (State != State.Realtime || writer == null || writer.IsClosed
                || update.Instrument.FullName != Instrument.FullName) return;
            if (update.IsReset) { writer.Fail("feed_reset"); return; }
            string side = update.MarketDataType == MarketDataType.Bid ? "bid"
                : update.MarketDataType == MarketDataType.Ask ? "ask" : null;
            if (side == null) { writer.Fail("invalid_depth_side"); return; }
            try
            {
                writer.Record("depth", new Dictionary<string, object> {
                    { "side", side }, { "operation", update.Operation.ToString().ToLowerInvariant() },
                    { "position", update.Position }, { "price", BoundedCaptureWriter.Price(update.Price) },
                    { "size", update.Volume },
                    { "provider_time_text", update.Time.ToString("O", CultureInfo.InvariantCulture) }
                });
            }
            catch (Exception) { writer.Fail("invalid_depth_event"); }
        }
    }
}
