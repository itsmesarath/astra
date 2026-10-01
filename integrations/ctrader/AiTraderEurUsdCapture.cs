// Read-only demo cBot. AccessRights.None is not a trading lock: there are no order calls.
using System;
using System.Collections.Generic;
using AiTrader.MarketData;
using cAlgo.API;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class AiTraderEurUsdCapture : Robot
    {
        [Parameter("Enable capture", DefaultValue = false)]
        public bool EnableCapture { get; set; }

        [Parameter("Maximum minutes", DefaultValue = 10, MinValue = 1, MaxValue = 60)]
        public int MaximumMinutes { get; set; }

        [Parameter("Maximum event records", DefaultValue = 250000, MinValue = 1, MaxValue = 1000000)]
        public int MaximumEvents { get; set; }

        private BoundedCaptureWriter writer;

        protected override void OnStart()
        {
            if (!EnableCapture || Account.IsLive || RunningMode != RunningMode.RealTime
                || Symbol.BaseAsset.Name != "EUR" || Symbol.QuoteAsset.Name != "USD"
                || MaximumMinutes < 1 || MaximumMinutes > 60)
            { Print("Capture refused: enable on a real-time EURUSD demo chart only."); Stop(); return; }
            try
            {
                // Relative paths are confined to this cBot's designated data directory.
                writer = new BoundedCaptureWriter("captures", "ctrader", "EURUSD", SymbolName,
                    "demo", Account.BrokerName, BoundedCaptureWriter.Price(Symbol.TickSize),
                    MaximumMinutes * 60, MaximumEvents);
                Print("Capture-only file: " + writer.FilePath);
                Timer.Start(1);
            }
            catch (Exception) { Print("Capture initialization failed; no retry."); Stop(); }
        }

        protected override void OnTick()
        {
            if (writer == null || writer.IsClosed) return;
            if (Account.IsLive || RunningMode != RunningMode.RealTime)
            { writer.Fail("platform_mode_changed"); Stop(); return; }
            try
            {
                writer.Record("quote", new Dictionary<string, object> {
                    { "bid", BoundedCaptureWriter.Price(Symbol.Bid) },
                    { "ask", BoundedCaptureWriter.Price(Symbol.Ask) }
                });
            }
            catch (Exception) { writer.Fail("invalid_market_event"); Stop(); }
        }

        protected override void OnTimer()
        {
            if (writer != null && writer.IsClosed) Stop();
        }

        protected override void OnStop()
        {
            if (writer != null) writer.Dispose();
        }
    }
}
