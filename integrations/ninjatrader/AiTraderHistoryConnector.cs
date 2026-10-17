// AiTraderHistoryConnector: file-driven historical data connector for NinjaTrader 8.
//
// Python (or you) drops a request file into  <NinjaTrader 8 user dir>\ai-trader-requests\*.json:
//   {"instrument": "6E 12-26", "from": "2026-09-07", "to": "2026-10-16", "type": "tick"}
//   type: "tick" (every trade with the bid/ask at that moment) or "minute" (1-minute OHLCV, last).
// The add-on polls that folder, fetches each day through NinjaTrader's BarsRequest (the same path
// the Historical Data window uses, so the provider's lookback and entitlements apply unchanged),
// and writes one JSONL file per day into  <user dir>\ai-trader-history\<instrument>\<type>_<date>.jsonl
// Existing day files are skipped, so a request can be re-dropped to fill gaps. When a request is
// finished it is renamed *.done (or *.error with the message inside).
//
// Data-only: no Account access, no order methods, no connection changes. Historical depth (Level 2)
// is not available through BarsRequest on any provider; use Market Replay + the capture indicator.
//
// Install: NinjaTrader Control Center -> Tools -> NinjaScript Editor -> AddOns folder -> New -> paste,
// compile (F5). The add-on starts with NinjaTrader; the Output window (New -> NinjaScript Output)
// shows its log lines prefixed "AiTraderHistory".

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.AddOns
{
    public class AiTraderHistoryConnector : AddOnBase
    {
        private const int PollSeconds = 15;
        private System.Timers.Timer timer;
        private readonly object gate = new object();
        private bool busy;
        private string requestDir;
        private string historyDir;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "AiTraderHistoryConnector";
                Description = "Fulfils file-based historical tick/minute data requests; writes JSONL; never trades.";
            }
            else if (State == State.Configure)
            {
                requestDir = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "ai-trader-requests");
                historyDir = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "ai-trader-history");
                Directory.CreateDirectory(requestDir);
                Directory.CreateDirectory(historyDir);
                timer = new System.Timers.Timer(PollSeconds * 1000) { AutoReset = true };
                timer.Elapsed += (s, e) => Poll();
                timer.Start();
                Log("watching " + requestDir);
            }
            else if (State == State.Terminated)
            {
                if (timer != null) { timer.Stop(); timer.Dispose(); timer = null; }
            }
        }

        private static void Log(string text)
        {
            NinjaTrader.Code.Output.Process("AiTraderHistory " + DateTime.UtcNow.ToString("HH:mm:ss") + " " + text,
                PrintTo.OutputTab1);
        }

        private void Poll()
        {
            lock (gate)
            {
                if (busy) return;
                busy = true;
            }
            try
            {
                string[] files = Directory.GetFiles(requestDir, "*.json");
                Array.Sort(files, StringComparer.Ordinal);
                if (files.Length == 0) { lock (gate) { busy = false; } return; }
                StartRequest(files[0]);
            }
            catch (Exception ex)
            {
                Log("poll error " + ex.Message);
                lock (gate) { busy = false; }
            }
        }

        private sealed class Request
        {
            public string Path;
            public string InstrumentName;
            public string Type;
            public DateTime From;
            public DateTime To;
            public Instrument Instrument;
            public List<DateTime> Days = new List<DateTime>();
            public int Index;
            public int Written;
            public StringBuilder Errors = new StringBuilder();
        }

        private static string Field(string json, string name)
        {
            Match m = Regex.Match(json, "\"" + name + "\"\\s*:\\s*\"([^\"]*)\"");
            return m.Success ? m.Groups[1].Value : null;
        }

        private void StartRequest(string path)
        {
            Request req = new Request { Path = path };
            try
            {
                string json = File.ReadAllText(path);
                req.InstrumentName = Field(json, "instrument");
                req.Type = (Field(json, "type") ?? "tick").ToLowerInvariant();
                req.From = DateTime.ParseExact(Field(json, "from"), "yyyy-MM-dd", CultureInfo.InvariantCulture);
                req.To = DateTime.ParseExact(Field(json, "to"), "yyyy-MM-dd", CultureInfo.InvariantCulture);
                if (req.Type != "tick" && req.Type != "minute") throw new ArgumentException("type must be tick or minute");
                if (req.To < req.From || (req.To - req.From).TotalDays > 400) throw new ArgumentException("bad date range");
                req.Instrument = Instrument.GetInstrument(req.InstrumentName);
                if (req.Instrument == null) throw new ArgumentException("unknown instrument " + req.InstrumentName);
                for (DateTime d = req.From; d <= req.To; d = d.AddDays(1)) req.Days.Add(d);
                Log("request " + Path.GetFileName(path) + ": " + req.InstrumentName + " " + req.Type + " "
                    + req.Days.Count + " days");
                NextDay(req);
            }
            catch (Exception ex)
            {
                Finish(req, "invalid request: " + ex.Message);
            }
        }

        private string DayFile(Request req)
        {
            string folder = Path.Combine(historyDir, req.InstrumentName.Replace(' ', '_'));
            Directory.CreateDirectory(folder);
            return Path.Combine(folder, req.Type + "_" + req.Days[req.Index].ToString("yyyy-MM-dd") + ".jsonl");
        }

        private void NextDay(Request req)
        {
            while (req.Index < req.Days.Count && File.Exists(DayFile(req))) req.Index++;
            if (req.Index >= req.Days.Count) { Finish(req, null); return; }
            DateTime day = req.Days[req.Index];
            BarsPeriod period = req.Type == "tick"
                ? new BarsPeriod { BarsPeriodType = BarsPeriodType.Tick, Value = 1, MarketDataType = MarketDataType.Last }
                : new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 1, MarketDataType = MarketDataType.Last };
            BarsRequest barsRequest = new BarsRequest(req.Instrument, day, day.AddDays(1).AddSeconds(-1))
            {
                BarsPeriod = period,
                TradingHours = req.Instrument.MasterInstrument.TradingHours,
            };
            barsRequest.Request((bars, errorCode, errorMessage) =>
            {
                try
                {
                    if (errorCode != ErrorCode.NoError)
                    {
                        req.Errors.AppendLine(day.ToString("yyyy-MM-dd") + ": " + errorCode + " " + errorMessage);
                    }
                    else
                    {
                        WriteDay(req, bars.Bars, day);
                    }
                }
                catch (Exception ex)
                {
                    req.Errors.AppendLine(day.ToString("yyyy-MM-dd") + ": " + ex.Message);
                }
                finally
                {
                    if (bars != null) bars.Dispose();
                }
                req.Index++;
                NextDay(req);
            });
        }

        private void WriteDay(Request req, Bars bars, DateTime day)
        {
            string target = DayFile(req);
            string partial = target + ".partial";
            int count = bars == null ? 0 : bars.Count;
            using (StreamWriter w = new StreamWriter(partial, false, new UTF8Encoding(false)))
            {
                w.WriteLine("{\"record\":\"header\",\"schema\":\"ai_trader_nt_history_v1\",\"instrument\":\"" + req.InstrumentName
                    + "\",\"type\":\"" + req.Type + "\",\"day_local\":\"" + day.ToString("yyyy-MM-dd")
                    + "\",\"tick_size\":\"" + req.Instrument.MasterInstrument.TickSize.ToString("0.#########", CultureInfo.InvariantCulture)
                    + "\",\"provider\":\"ninjatrader\",\"count\":" + count + ",\"time_basis\":\"bar_time_utc\"}");
                for (int i = 0; i < count; i++)
                {
                    long utcNs = (bars.GetTime(i).ToUniversalTime().Ticks - 621355968000000000L) * 100L;
                    if (req.Type == "tick")
                    {
                        w.WriteLine("{\"t\":" + utcNs
                            + ",\"p\":" + bars.GetClose(i).ToString("0.#########", CultureInfo.InvariantCulture)
                            + ",\"v\":" + bars.GetVolume(i).ToString(CultureInfo.InvariantCulture)
                            + ",\"b\":" + bars.GetBid(i).ToString("0.#########", CultureInfo.InvariantCulture)
                            + ",\"a\":" + bars.GetAsk(i).ToString("0.#########", CultureInfo.InvariantCulture) + "}");
                    }
                    else
                    {
                        w.WriteLine("{\"t\":" + utcNs
                            + ",\"o\":" + bars.GetOpen(i).ToString("0.#########", CultureInfo.InvariantCulture)
                            + ",\"h\":" + bars.GetHigh(i).ToString("0.#########", CultureInfo.InvariantCulture)
                            + ",\"l\":" + bars.GetLow(i).ToString("0.#########", CultureInfo.InvariantCulture)
                            + ",\"c\":" + bars.GetClose(i).ToString("0.#########", CultureInfo.InvariantCulture)
                            + ",\"v\":" + bars.GetVolume(i).ToString(CultureInfo.InvariantCulture) + "}");
                    }
                }
            }
            if (File.Exists(target)) File.Delete(target);
            File.Move(partial, target);
            req.Written++;
            Log(req.InstrumentName + " " + req.Type + " " + day.ToString("yyyy-MM-dd") + ": " + count + " records");
        }

        private void Finish(Request req, string fatal)
        {
            try
            {
                string errors = req.Errors.ToString();
                if (fatal != null) errors = fatal + Environment.NewLine + errors;
                string done = Path.ChangeExtension(req.Path, errors.Length == 0 ? ".done" : ".error");
                if (File.Exists(done)) File.Delete(done);
                File.Move(req.Path, done);
                if (errors.Length > 0) File.AppendAllText(done, Environment.NewLine + "/* " + errors + " */");
                Log("finished " + Path.GetFileName(req.Path) + ": " + req.Written + " day files written"
                    + (errors.Length == 0 ? "" : "; errors recorded"));
            }
            catch (Exception ex)
            {
                Log("finish error " + ex.Message);
            }
            finally
            {
                lock (gate) { busy = false; }
            }
        }
    }
}
