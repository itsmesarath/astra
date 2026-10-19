// AiTraderFileBridge: file-driven DEMO order bridge for cTrader Automate (cBot).
//
// The Python live loop writes one JSON intent per file into this cBot's data folder, sub-folder
// "orders" (Documents\cAlgo\Data\cBots\AiTraderFileBridge\orders\<id>.json):
//   {"id":"...","action":"place","symbol":"EURUSD","side":"BUY","lots":0.01,
//    "stop_price_distance":0.0006,"target_price_distance":0.0018,"label":"shadow 2026-10-19 07:35 long"}
//   {"id":"...","action":"close","position_id":12345}
//   {"id":"...","action":"reconcile"}
// The cBot polls every second, executes, and writes <id>.done.json with the result. Guards, none of
// which an intent file can switch off: demo account only (Account.IsLive => every intent refused),
// MaxLots per order, MaxPositions open at once (counting this cBot's own label prefix), a KILL file
// in the data folder, and a symbol allowlist. Everything is appended to audit.log.
//
// Install: cTrader -> Automate -> cBots -> New -> paste -> Build; add to a EURUSD chart on the DEMO
// account; Start. AccessRights.FullAccess is required only for file access to its own data folder.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using System.Text.Json;
using cAlgo.API;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class AiTraderFileBridge : Robot
    {
        [Parameter("Max lots per order", DefaultValue = 0.01, MinValue = 0.01, MaxValue = 1.0)]
        public double MaxLots { get; set; }

        [Parameter("Max open positions", DefaultValue = 1, MinValue = 1, MaxValue = 5)]
        public int MaxPositions { get; set; }

        [Parameter("Allowed symbols (comma)", DefaultValue = "EURUSD")]
        public string AllowedSymbols { get; set; }

        [Parameter("Label prefix", DefaultValue = "aitrader")]
        public string LabelPrefix { get; set; }

        private string baseDir;
        private string ordersDir;
        private string auditPath;

        protected override void OnStart()
        {
            baseDir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "cAlgo", "Data", "cBots", "AiTraderFileBridge");
            ordersDir = System.IO.Path.Combine(baseDir, "orders");
            auditPath = System.IO.Path.Combine(baseDir, "audit.log");
            System.IO.Directory.CreateDirectory(ordersDir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(baseDir, "status.json"),
                "{\"running\":true,\"is_live\":" + (Account.IsLive ? "true" : "false") + ",\"broker\":\"" + Account.BrokerName
                + "\",\"account\":\"" + Account.Number + "\",\"symbol\":\"" + SymbolName + "\",\"pip_size\":"
                + Symbol.PipSize.ToString(CultureInfo.InvariantCulture) + ",\"started_utc\":\"" + DateTime.UtcNow.ToString("o") + "\"}");
            Audit("started; live=" + Account.IsLive + " broker=" + Account.BrokerName + " symbol=" + SymbolName);
            if (Account.IsLive) { Audit("LIVE account: bridge refuses every intent"); }
            Timer.Start(TimeSpan.FromSeconds(1));
        }

        protected override void OnStop()
        {
            try { System.IO.File.WriteAllText(System.IO.Path.Combine(baseDir, "status.json"), "{\"running\":false}"); } catch { }
            Audit("stopped");
        }

        protected override void OnTimer()
        {
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
                Audit(System.IO.Path.GetFileName(path) + " -> " + result);
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
                bool allowed = false;
                foreach (string s in AllowedSymbols.Split(',')) if (s.Trim() == symbol) allowed = true;
                if (!allowed) return Json(false, null, 0, "symbol not allowed: " + symbol);
                if (symbol != SymbolName) return Json(false, null, 0, "cBot runs on " + SymbolName + ", not " + symbol);
                double lots = root.GetProperty("lots").GetDouble();
                if (lots <= 0 || lots > MaxLots + 1e-9) return Json(false, null, 0, "lots exceed max " + MaxLots);
                int open = 0;
                foreach (Position p in Positions) if (p.Label != null && p.Label.StartsWith(LabelPrefix)) open++;
                if (open >= MaxPositions) return Json(false, null, 0, "max open positions reached");
                string side = (Get(root, "side") ?? "BUY").ToUpperInvariant();
                TradeType type = side == "SELL" ? TradeType.Sell : TradeType.Buy;
                double stopPips = root.GetProperty("stop_price_distance").GetDouble() / Symbol.PipSize;
                double tpPips = root.GetProperty("target_price_distance").GetDouble() / Symbol.PipSize;
                if (stopPips <= 0 || tpPips <= 0) return Json(false, null, 0, "stop/target must be positive");
                double volume = Symbol.NormalizeVolumeInUnits(Symbol.QuantityToVolumeInUnits(lots), RoundingMode.Down);
                string label = LabelPrefix + " " + (Get(root, "label") ?? "");
                if (label.Length > 100) label = label.Substring(0, 100);
                TradeResult res = ExecuteMarketOrder(type, symbol, volume, label, Math.Round(stopPips, 1), Math.Round(tpPips, 1));
                if (!res.IsSuccessful) return Json(false, null, 0, res.Error.ToString());
                return Json(true, res.Position.Id, res.Position.EntryPrice, null);
            }
        }

        private string Reconcile()
        {
            var sb = new StringBuilder();
            sb.Append("{\"ok\":true,\"is_live\":").Append(Account.IsLive ? "true" : "false")
              .Append(",\"broker\":\"").Append(Account.BrokerName).Append("\",\"balance\":")
              .Append(Account.Balance.ToString(CultureInfo.InvariantCulture)).Append(",\"equity\":")
              .Append(Account.Equity.ToString(CultureInfo.InvariantCulture)).Append(",\"positions\":[");
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
