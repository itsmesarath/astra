// AiTraderFileBridge v2: file-driven DEMO order and data bridge for cTrader Automate (cBot).
// Single-instance: if two instances run, one holds instance.lock and the other stands by.
//
// The Python live loop writes one JSON intent per file into this cBot's data folder, sub-folder
// "orders" (Documents\cAlgo\Data\cBots\AiTraderFileBridge\orders\<id>.json):
//   {"id":"...","action":"place","symbol":"XAUUSD","side":"BUY","lots":0.01,
//    "stop_price_distance":6.0,"target_price_distance":18.0,"label":"reversal 2026-10-19 13:35 long"}
//   {"id":"...","action":"close","position_id":12345}
//   {"id":"...","action":"reconcile"}
//   {"id":"...","action":"bars","symbol":"XAUUSD","count":4500}   -> last N completed 1-minute bars (UTC)
// The cBot polls every second, executes, and writes <id>.done.json with the result.
//
// Limits live in bridge_config.json in the data folder (created with defaults on first start, re-read
// every second so they can be tightened without a rebuild):
//   {"max_lots":0.01,"max_positions":2,"allowed_symbols":["EURUSD","XAUUSD"],"label_prefix":"aitrader"}
// Guards an intent file can never switch off: demo account only (Account.IsLive => every intent
// refused), max lots per order, max open positions (this cBot's label prefix), a KILL file in the
// data folder, the symbol allowlist. Everything is appended to audit.log.
//
// Build: cTrader -> Automate -> Build, or `dotnet build -c Release` in the project folder (the .algo
// is written to bin\Release\net6.0 and copied next to the Sources\Robots folder by the build script).
// Attach to any chart on the DEMO account (the chart symbol does not matter); Start.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using System.Text.Json;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class AiTraderFileBridge : Robot
    {
        private string baseDir;
        private string ordersDir;
        private string auditPath;
        private string configPath;
        private string lockPath;
        private readonly string instanceId = Guid.NewGuid().ToString("N");
        private bool active = false;

        // limits (from bridge_config.json; defaults below)
        private double maxLots = 0.01;
        private int maxPositions = 2;
        private HashSet<string> allowed = new HashSet<string> { "EURUSD", "XAUUSD" };
        private string labelPrefix = "aitrader";

        protected override void OnStart()
        {
            baseDir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "cAlgo", "Data", "cBots", "AiTraderFileBridge");
            ordersDir = System.IO.Path.Combine(baseDir, "orders");
            auditPath = System.IO.Path.Combine(baseDir, "audit.log");
            configPath = System.IO.Path.Combine(baseDir, "bridge_config.json");
            lockPath = System.IO.Path.Combine(baseDir, "instance.lock");
            System.IO.Directory.CreateDirectory(ordersDir);
            if (!System.IO.File.Exists(configPath))
                System.IO.File.WriteAllText(configPath,
                    "{\"max_lots\":0.01,\"max_positions\":2,\"allowed_symbols\":[\"EURUSD\",\"XAUUSD\"],\"label_prefix\":\"aitrader\"}");
            LoadConfig();
            Audit("started v2; live=" + Account.IsLive + " broker=" + Account.BrokerName + " chart=" + SymbolName
                  + " allowed=" + string.Join(",", allowed) + " maxLots=" + maxLots + " maxPositions=" + maxPositions);
            if (Account.IsLive) { Audit("LIVE account: bridge refuses every intent"); }
            Timer.Start(TimeSpan.FromSeconds(1));
        }

        protected override void OnStop()
        {
            if (active)
            {
                try { System.IO.File.WriteAllText(System.IO.Path.Combine(baseDir, "status.json"), "{\"running\":false}"); } catch { }
                try { System.IO.File.Delete(lockPath); } catch { }
            }
            Audit("stopped (" + (active ? "active" : "standby") + " instance " + instanceId.Substring(0, 8) + ")");
        }

        // Only one running instance may act on the orders folder. The active one refreshes
        // instance.lock every second; another instance stays on standby until the lock is stale (>5 s).
        private bool ClaimLock()
        {
            try
            {
                if (System.IO.File.Exists(lockPath))
                {
                    string[] parts = System.IO.File.ReadAllText(lockPath).Split('|');
                    if (parts.Length == 2 && parts[0] != instanceId)
                    {
                        DateTime t;
                        if (DateTime.TryParse(parts[1], null, DateTimeStyles.RoundtripKind, out t) && (DateTime.UtcNow - t).TotalSeconds < 5)
                        {
                            if (active) { active = false; Audit("lost lock to instance " + parts[0].Substring(0, 8) + "; standby"); }
                            return false;
                        }
                    }
                }
                System.IO.File.WriteAllText(lockPath, instanceId + "|" + DateTime.UtcNow.ToString("o"));
                if (!active) { active = true; Audit("active instance " + instanceId.Substring(0, 8) + " on chart " + SymbolName); WriteStatus(true); }
                return true;
            }
            catch { return active; }
        }

        private void LoadConfig()
        {
            try
            {
                using (JsonDocument doc = JsonDocument.Parse(System.IO.File.ReadAllText(configPath)))
                {
                    JsonElement r = doc.RootElement;
                    JsonElement v;
                    if (r.TryGetProperty("max_lots", out v)) maxLots = v.GetDouble();
                    if (r.TryGetProperty("max_positions", out v)) maxPositions = v.GetInt32();
                    if (r.TryGetProperty("label_prefix", out v) && v.ValueKind == JsonValueKind.String) labelPrefix = v.GetString();
                    if (r.TryGetProperty("allowed_symbols", out v) && v.ValueKind == JsonValueKind.Array)
                    {
                        var set = new HashSet<string>();
                        foreach (JsonElement e in v.EnumerateArray()) if (e.ValueKind == JsonValueKind.String) set.Add(e.GetString());
                        if (set.Count > 0) allowed = set;
                    }
                }
            }
            catch (Exception ex) { Audit("config error (keeping previous limits): " + ex.Message); }
            if (maxLots > 1.0) maxLots = 1.0;          // hard ceilings regardless of the file
            if (maxPositions > 5) maxPositions = 5;
        }

        private void WriteStatus(bool running)
        {
            var sb = new StringBuilder();
            sb.Append("{\"running\":").Append(running ? "true" : "false").Append(",\"version\":2,\"is_live\":")
              .Append(Account.IsLive ? "true" : "false").Append(",\"broker\":\"").Append(Account.BrokerName)
              .Append("\",\"account\":\"").Append(Account.Number).Append("\",\"chart_symbol\":\"").Append(SymbolName)
              .Append("\",\"max_lots\":").Append(maxLots.ToString(CultureInfo.InvariantCulture))
              .Append(",\"max_positions\":").Append(maxPositions).Append(",\"symbols\":{");
            bool first = true;
            foreach (string s in allowed)
            {
                try
                {
                    Symbol sym = Symbols.GetSymbol(s);
                    if (sym == null) continue;
                    if (!first) sb.Append(',');
                    first = false;
                    sb.Append('"').Append(s).Append("\":{\"pip_size\":").Append(sym.PipSize.ToString(CultureInfo.InvariantCulture))
                      .Append(",\"tick_size\":").Append(sym.TickSize.ToString(CultureInfo.InvariantCulture))
                      .Append(",\"digits\":").Append(sym.Digits).Append(",\"lot_size\":").Append(sym.LotSize.ToString(CultureInfo.InvariantCulture))
                      .Append(",\"min_volume\":").Append(sym.VolumeInUnitsMin.ToString(CultureInfo.InvariantCulture)).Append('}');
                }
                catch { }
            }
            sb.Append("},\"started_utc\":\"").Append(DateTime.UtcNow.ToString("o")).Append("\"}");
            try { System.IO.File.WriteAllText(System.IO.Path.Combine(baseDir, "status.json"), sb.ToString()); } catch { }
        }

        protected override void OnTimer()
        {
            if (!ClaimLock()) return;
            LoadConfig();
            string[] files;
            try { files = System.IO.Directory.GetFiles(ordersDir, "*.json"); } catch { return; }
            Array.Sort(files, StringComparer.Ordinal);
            foreach (string path in files)
            {
                if (path.EndsWith(".done.json")) continue;
                string donePath = path.Substring(0, path.Length - 5) + ".done.json";
                if (System.IO.File.Exists(donePath)) continue;
                string result;
                try { result = Handle(System.IO.File.ReadAllText(path)); }
                catch (Exception ex) { result = Json(false, null, 0, "exception: " + ex.Message); }
                System.IO.File.WriteAllText(donePath + ".partial", result);
                System.IO.File.Move(donePath + ".partial", donePath);
                Audit(System.IO.Path.GetFileName(path) + " -> " + (result.Length > 300 ? result.Substring(0, 300) + "..." : result));
            }
        }

        private string Handle(string text)
        {
            using (JsonDocument doc = JsonDocument.Parse(text))
            {
                JsonElement root = doc.RootElement;
                string action = Get(root, "action") ?? "place";
                if (System.IO.File.Exists(System.IO.Path.Combine(baseDir, "KILL"))) return Json(false, null, 0, "kill switch present");
                if (Account.IsLive) return Json(false, null, 0, "live account refused");
                if (action == "reconcile") return Reconcile();
                if (action == "bars") return BarsJson(root);
                if (action == "close")
                {
                    long pid = root.GetProperty("position_id").GetInt64();
                    foreach (Position p in Positions)
                    {
                        if (p.Id == pid)
                        {
                            TradeResult r = ClosePosition(p);
                            return r.IsSuccessful ? Json(true, p.Id, 0, null) : Json(false, p.Id, 0, r.Error.ToString());
                        }
                    }
                    return Json(false, pid, 0, "position not found");
                }
                // place
                string symbol = Get(root, "symbol") ?? SymbolName;
                if (!allowed.Contains(symbol)) return Json(false, null, 0, "symbol not allowed: " + symbol);
                Symbol sym = Symbols.GetSymbol(symbol);
                if (sym == null) return Json(false, null, 0, "unknown symbol: " + symbol);
                double lots = root.GetProperty("lots").GetDouble();
                if (lots <= 0 || lots > maxLots + 1e-9) return Json(false, null, 0, "lots exceed max " + maxLots);
                int open = 0;
                foreach (Position p in Positions) if (p.Label != null && p.Label.StartsWith(labelPrefix)) open++;
                if (open >= maxPositions) return Json(false, null, 0, "max open positions reached");
                foreach (Position p in Positions)
                    if (p.SymbolName == symbol && p.Label != null && p.Label.StartsWith(labelPrefix))
                        return Json(false, null, 0, "already in a position on " + symbol);
                string side = (Get(root, "side") ?? "BUY").ToUpperInvariant();
                TradeType type = side == "SELL" ? TradeType.Sell : TradeType.Buy;
                double stopPips = root.GetProperty("stop_price_distance").GetDouble() / sym.PipSize;
                double tpPips = root.GetProperty("target_price_distance").GetDouble() / sym.PipSize;
                if (stopPips <= 0 || tpPips <= 0) return Json(false, null, 0, "stop/target must be positive");
                double volume = sym.NormalizeVolumeInUnits(sym.QuantityToVolumeInUnits(lots), RoundingMode.Down);
                if (volume < sym.VolumeInUnitsMin) return Json(false, null, 0, "volume below broker minimum " + sym.VolumeInUnitsMin);
                string label = labelPrefix + " " + (Get(root, "label") ?? "");
                if (label.Length > 100) label = label.Substring(0, 100);
                TradeResult res = ExecuteMarketOrder(type, symbol, volume, label, Math.Round(stopPips, 1), Math.Round(tpPips, 1));
                if (!res.IsSuccessful) return Json(false, null, 0, res.Error.ToString());
                return Json(true, res.Position.Id, res.Position.EntryPrice, null);
            }
        }

        private string BarsJson(JsonElement root)
        {
            string symbol = Get(root, "symbol") ?? SymbolName;
            if (!allowed.Contains(symbol)) return Json(false, null, 0, "symbol not allowed: " + symbol);
            int count = 3000;
            JsonElement cv;
            if (root.TryGetProperty("count", out cv)) count = Math.Max(10, Math.Min(20000, cv.GetInt32()));
            Bars bars = MarketData.GetBars(TimeFrame.Minute, symbol);
            int guard = 0;
            while (bars.Count < count + 1 && guard++ < 40)
            {
                int loaded = bars.LoadMoreHistory();
                if (loaded <= 0) break;
            }
            // skip the last (still forming) bar
            int last = bars.Count - 2;
            int first = Math.Max(0, last - count + 1);
            var sb = new StringBuilder();
            sb.Append("{\"ok\":true,\"symbol\":\"").Append(symbol).Append("\",\"timeframe\":\"m1\",\"utc_now\":\"")
              .Append(DateTime.UtcNow.ToString("o")).Append("\",\"bars\":[");
            DateTime epoch = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
            for (int i = first; i <= last; i++)
            {
                if (i > first) sb.Append(',');
                long ms = (long)(bars.OpenTimes[i] - epoch).TotalMilliseconds;
                sb.Append('[').Append(ms).Append(',')
                  .Append(bars.OpenPrices[i].ToString(CultureInfo.InvariantCulture)).Append(',')
                  .Append(bars.HighPrices[i].ToString(CultureInfo.InvariantCulture)).Append(',')
                  .Append(bars.LowPrices[i].ToString(CultureInfo.InvariantCulture)).Append(',')
                  .Append(bars.ClosePrices[i].ToString(CultureInfo.InvariantCulture)).Append(',')
                  .Append(bars.TickVolumes[i].ToString(CultureInfo.InvariantCulture)).Append(']');
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private string Reconcile()
        {
            var sb = new StringBuilder();
            sb.Append("{\"ok\":true,\"version\":2,\"is_live\":").Append(Account.IsLive ? "true" : "false")
              .Append(",\"broker\":\"").Append(Account.BrokerName).Append("\",\"balance\":")
              .Append(Account.Balance.ToString(CultureInfo.InvariantCulture)).Append(",\"equity\":")
              .Append(Account.Equity.ToString(CultureInfo.InvariantCulture))
              .Append(",\"max_lots\":").Append(maxLots.ToString(CultureInfo.InvariantCulture))
              .Append(",\"max_positions\":").Append(maxPositions)
              .Append(",\"allowed_symbols\":[");
            bool f = true;
            foreach (string s in allowed) { if (!f) sb.Append(','); f = false; sb.Append('"').Append(s).Append('"'); }
            sb.Append("],\"positions\":[");
            bool first = true;
            foreach (Position p in Positions)
            {
                if (!first) sb.Append(',');
                first = false;
                sb.Append("{\"position_id\":").Append(p.Id).Append(",\"symbol\":\"").Append(p.SymbolName)
                  .Append("\",\"side\":\"").Append(p.TradeType == TradeType.Buy ? "BUY" : "SELL")
                  .Append("\",\"volume\":").Append(p.VolumeInUnits.ToString(CultureInfo.InvariantCulture))
                  .Append(",\"entry\":").Append(p.EntryPrice.ToString(CultureInfo.InvariantCulture))
                  .Append(",\"label\":\"").Append((p.Label ?? "").Replace("\"", "'")).Append("\",\"net_pnl\":")
                  .Append(p.NetProfit.ToString(CultureInfo.InvariantCulture)).Append('}');
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private static string Get(JsonElement root, string name)
        {
            JsonElement v;
            return root.TryGetProperty(name, out v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
        }

        private static string Json(bool ok, long? positionId, double entry, string error)
        {
            return "{\"ok\":" + (ok ? "true" : "false")
                + ",\"position_id\":" + (positionId.HasValue ? positionId.Value.ToString(CultureInfo.InvariantCulture) : "null")
                + ",\"entry_price\":" + entry.ToString(CultureInfo.InvariantCulture)
                + ",\"error\":" + (error == null ? "null" : "\"" + error.Replace("\"", "'") + "\"")
                + ",\"utc\":\"" + DateTime.UtcNow.ToString("o") + "\"}";
        }

        private void Audit(string text)
        {
            try { System.IO.File.AppendAllText(auditPath, DateTime.UtcNow.ToString("o") + " " + text + Environment.NewLine); } catch { }
            Print(text);
        }
    }
}
