// Offline synthetic writer verification. Never loads either trading platform.
using System;
using System.Collections.Generic;
using System.Threading;
using AiTrader.MarketData;

public static class WriterSmoke
{
    public static int Main(string[] args)
    {
        if (args.Length != 1) return 2;
        using (var writer = new BoundedCaptureWriter(args[0], "ctrader", "EURUSD", "EURUSD",
            "demo", "SYNTHETIC_WRITER_SMOKE_NOT_MARKET_DATA", "0.00001", 1, 100))
        {
            writer.Record("quote", new Dictionary<string, object> { { "bid", "1.10000" }, { "ask", "1.10010" } });
            Thread.Sleep(1200);
            writer.Dispose();
            if (!writer.IsClosed) return 3;
            Console.WriteLine(writer.FilePath);
        }
        using (var writer = new BoundedCaptureWriter(args[0], "ninjatrader", "6E", "6E 12-26",
            "unverified", "SYNTHETIC_WRITER_SMOKE_NOT_MARKET_DATA", "0.00005", 60, 2))
        {
            writer.Record("bid", new Dictionary<string, object> { { "price", "1.1" }, { "size", 10L }, { "provider_time_text", "diagnostic" } });
            writer.Record("ask", new Dictionary<string, object> { { "price", "1.10005" }, { "size", 10L }, { "provider_time_text", "diagnostic" } });
            writer.Record("trade", new Dictionary<string, object> { { "price", "1.10005" }, { "size", 1L }, { "provider_time_text", "diagnostic" } });
            if (!writer.IsClosed) return 4;
            Console.WriteLine(writer.FilePath);
        }
        return 0;
    }
}
