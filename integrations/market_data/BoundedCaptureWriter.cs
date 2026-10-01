// Shared capture-only transport. No platform, account, order, credential or network APIs.
// Compatible with .NET Framework 4.8 and .NET 6. Source clocks are diagnostic only.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.Serialization.Json;
using System.Text;
using System.Threading;

namespace AiTrader.MarketData
{
    public sealed class BoundedCaptureWriter : IDisposable
    {
        private const long MaxBytes = 64L * 1024 * 1024;
        private const long EpochTicks = 621355968000000000L;
        private readonly object gate = new object();
        private readonly Stopwatch watch;
        private readonly StreamWriter output;
        private readonly int maxSeconds;
        private readonly int maxEvents;
        private readonly long startedUtc;
        private readonly string session;
        private System.Threading.Timer timer;
        private int sequence;
        private long bytes;
        private bool closed;

        public string FilePath { get; private set; }
        public bool IsClosed { get { lock (gate) { return closed; } } }

        public BoundedCaptureWriter(string directory, string provider, string market,
            string instrument, string feedEnvironment, string feedLabel, string tickSize,
            int seconds, int events)
        {
            if ((provider != "ninjatrader" && provider != "ctrader") || seconds < 1
                || seconds > 3600 || events < 1 || events > 1000000
                || String.IsNullOrWhiteSpace(instrument) || instrument.Length > 80
                || String.IsNullOrWhiteSpace(feedLabel) || feedLabel.Length > 120)
                throw new ArgumentException("Invalid bounded capture configuration.");
            maxSeconds = seconds;
            maxEvents = events;
            session = provider + "-" + Guid.NewGuid().ToString("N");
            Directory.CreateDirectory(directory);
            FilePath = Path.Combine(directory, session + ".jsonl");
            output = new StreamWriter(new FileStream(FilePath, FileMode.CreateNew,
                FileAccess.Write, FileShare.Read), new UTF8Encoding(false));
            output.NewLine = "\n";
            watch = Stopwatch.StartNew();
            startedUtc = UtcNs();
            try
            {
                WriteLocked("session_start", new Dictionary<string, object> {
                    { "schema", "ai_trader_market_capture_v1" },
                    { "provider", provider }, { "market", market },
                    { "instrument", instrument }, { "feed_environment", feedEnvironment },
                    { "feed_label", feedLabel }, { "tick_size", tickSize },
                    { "max_seconds", seconds }, { "max_events", events },
                    { "clock_basis", "serialized_callback_observation_utc" },
                    { "clock_sync_verified", false }, { "trading_enabled", false }
                }, startedUtc, 0);
                // This timer touches only this writer, never a platform API.
                timer = new System.Threading.Timer(delegate { Heartbeat(); }, null, 1000, 1000);
            }
            catch { output.Dispose(); closed = true; throw; }
        }

        private static long UtcNs() { return checked((DateTime.UtcNow.Ticks - EpochTicks) * 100); }
        private long ElapsedNs() { return (long)(watch.ElapsedTicks * (1000000000m / Stopwatch.Frequency)); }

        public static string Price(double value)
        {
            if (Double.IsNaN(value) || Double.IsInfinity(value) || value < 0 || value >= 1000)
                throw new ArgumentException("Invalid market price.");
            return ((decimal)value).ToString("0.#########", CultureInfo.InvariantCulture);
        }

        public void Record(string kind, Dictionary<string, object> fields)
        {
            lock (gate)
            {
                if (closed) return;
                try
                {
                    if (kind != "quote" && kind != "bid" && kind != "ask"
                        && kind != "trade" && kind != "depth")
                        throw new ArgumentException("Unsupported market-data kind.");
                    RecordLocked(kind, fields);
                }
                catch { FinishLocked("capture_error", false); }
            }
        }

        private void RecordLocked(string kind, Dictionary<string, object> fields)
        {
            long elapsed = ElapsedNs();
            long utc = UtcNs();
            if (Math.Abs((utc - startedUtc) - elapsed) > 250000000L)
            { FinishLocked("clock_jump", false); return; }
            if (elapsed >= maxSeconds * 1000000000L)
            { FinishLocked("duration_limit", true); return; }
            if (sequence >= maxEvents)
            { FinishLocked("event_limit", true); return; }
            if (bytes >= MaxBytes - 8192)
            { FinishLocked("byte_limit", true); return; }
            sequence++;
            WriteLocked(kind, fields, utc, elapsed);
        }

        private void Heartbeat()
        {
            lock (gate)
            {
                if (closed) return;
                try { RecordLocked("heartbeat", new Dictionary<string, object>()); }
                catch { FinishLocked("capture_error", false); }
            }
        }

        private void WriteLocked(string kind, Dictionary<string, object> fields, long utc, long elapsed)
        {
            var record = new Dictionary<string, object>(fields);
            record.Add("kind", kind);
            record.Add("source_session", session);
            record.Add("sequence", sequence);
            record.Add("observed_utc_ns", utc);
            record.Add("elapsed_ns", elapsed);
            using (var buffer = new MemoryStream())
            {
                var serializer = new DataContractJsonSerializer(typeof(Dictionary<string, object>),
                    new DataContractJsonSerializerSettings { UseSimpleDictionaryFormat = true });
                serializer.WriteObject(buffer, record);
                if (buffer.Length > 4095 || bytes + buffer.Length + 1 > MaxBytes)
                    throw new InvalidOperationException("Capture byte budget exceeded.");
                string line = Encoding.UTF8.GetString(buffer.ToArray());
                output.WriteLine(line);
                output.Flush();
                bytes += buffer.Length + 1;
            }
        }

        private void FinishLocked(string reason, bool clean)
        {
            if (closed) return;
            closed = true;
            if (timer != null) timer.Dispose();
            int records = sequence;
            sequence++;
            try
            {
                WriteLocked("session_end", new Dictionary<string, object> {
                    { "reason", reason }, { "clean_shutdown", clean }, { "event_records", records }
                }, UtcNs(), ElapsedNs());
            }
            catch { /* A missing footer is deliberately rejected by the offline auditor. */ }
            finally { output.Dispose(); }
        }

        public void Fail(string reason)
        {
            lock (gate) { FinishLocked(reason, false); }
        }

        public void Dispose()
        {
            lock (gate) { FinishLocked("manual_stop", true); }
        }
    }
}
