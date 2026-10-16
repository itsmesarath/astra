# Post-repair prospective windowed campaign

## Superseded before acquisition, at the user's request

At 14:01:20 UTC the verified waiting Python process was stopped after the user asked to start
earlier; its launcher also exited. No session had started and no market-data file existed.
The original schedule and one-row `started` audit remain unchanged and must never be resumed.
This is an operator cancellation, not a completed or market-failed campaign. A separate note
is retained at `logs/btcusdt_windowed_20260925_2_operator_cancellation.json`, raw SHA256
`1476dac6c709efe3ab3eeff93bf7da937540986ef5c403eae75e907160d82864`.
The new [campaign -3](WINDOWED_CAMPAIGN_20260925_3.md) has its own schedule and output directory.
The launch details below are historical; the follow-up no longer monitors campaign -2.

## Started, not yet completed (2026-09-25)

After the user confirmed the corrected host-availability window, prepared and launched the
distinct public-data-only campaign `btcusdt-windowed-20260925-2`. It uses the burst-repaired
collector and the unchanged pinned research recipe. The earlier failed campaign and successful
operational diagnostic remain separate: neither is an input to this campaign or a training fold.

| Role | UTC dispatch window | Lisbon nominal start | Duration |
| --- | --- | --- | --- |
| Train 1 | 14:15:00–14:15:30 | 15:15 | 120 s |
| Train 2 | 15:15:00–15:15:30 | 16:15 | 120 s |
| Validation | 16:15:00–16:15:30 | 17:15 | 120 s |
| Reserved | 17:15:00–17:15:30 | 18:15 | 120 s |

All windows are on **2026-09-25**. Last accepted footer: **17:17:45 UTC**; completion grace
ends **17:18:15 UTC** (18:18:15 Lisbon). Allow until approximately 18:20 Lisbon for the final
checks. These are predeclared observation times, not outcome-selected windows or evidence of
independent market regimes. A missed/failed slot ends the whole campaign; there are no retries,
replacement sessions, shifted windows, resumptions or successful-subset processing.

## Frozen inputs and limits

- Original schedule: `logs/btcusdt_windowed_plan_20260925_2.json` (5,676 bytes), raw SHA256
  `b9d7cf06b3c7466a387083f8cdcad7ad140a392a7c6150a625236cb02114d743`.
- Acquisition directory: `data/raw/btcusdt_windowed_20260925_2/`. Its exclusive claim and copied
  `schedule.json` are present; the copy has the same raw hash as the original schedule.
- Source: `e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5`.
- Settings: `configs/windowed_event_trial_v1.json`, raw SHA256
  `9fb76e9fd3f6b1467a76dd666ba3b813c82f2e6d2d682d0d52f2d604fa79b05a`.
- Runtime: Python 3.12.10, NumPy 2.5.3, websockets 17.1.
- Four captures: 480 nominal recording seconds, at most 128 MiB raw data / 399,988 stream
  events. Each capture retains the 256-slot queue and existing message/byte/idle limits.
- Three research sessions: 3,000 processing frames each, 9,000 total; 600,000 declared training
  row-epochs is only a compute ceiling, not authorization to fit. Train/validation have timing
  sidecars; reserved gets acquisition integrity checks only, no research timing or data reads.

Fees (10 bps each side), slippage (2 bps each side), 10-second hold, 20/40-bps stop/target,
warmup, 500-ms quote freshness, minimum resolved count/fraction and all class-diversity/training
gates are unchanged. The rule remains `abstain`; collection creates no orders or model calls.

### Processing-volume risk declared before launch

The preceding diagnostic produced **6,311 replay frames**, greater than this recipe's
3,000-frame/source cap. A similarly busy research source would fail the complete-session gate.
This risk was disclosed before launching; capture success does not imply research eligibility.
Do not truncate and call a source complete, enlarge the frozen cap afterward, replace a busy
source, or select only quiet/successful intervals. Any future resource-policy revision requires
a separate prospective design, not reinterpretation of this campaign's results.

## Preflight and launch evidence

Full suite before launch: **2,660 Python tests passed, one optional Nautilus skip** (125.84 s),
**38 JavaScript tests passed**, Ruff lint/format and `git diff --check` clean. The dirty/untracked
tree was preserved. No source/dependency/configuration changes occurred. The host was on AC,
AC idle sleep was already disabled, about 772 GB was free, and no conflicting ingestion/model/
training process was found. No power settings were changed.

The hidden runner started at **13:52:59 UTC**: virtual-environment launcher PID **31412**,
Python 3.12 child PID **24740**. Their creation time and command lines match the frozen schedule
and pin. Standard output/error paths are `logs/btcusdt_windowed_20260925_2.stdout.log` and
`logs/btcusdt_windowed_20260925_2.stderr.log`; both were empty at the initial check. The durable
audit has its initial `started` row. There is no receipt/failure at this launch check, and the
first session has not begun. Process presence is not proof of campaign success.

**Do not edit source or dependencies while this campaign is active.** Do not restart, kill or
repair it automatically. Original failed raw/reserved captures and all prior datasets remain
untouched. No labels, feature datasets, fitting, model evaluation or trading follows acquisition.

## Read-only follow-up

Created the task follow-up `check-bounded-binance-capture` at a 15-minute cadence. It monitors
only this already-running campaign's bounded metadata and matching process identities, stays
quiet during normal progress, and reports only completion, failure or necessary user action.
It cannot start/repair captures, change source/configuration, access credentials, open raw or
reserved contents, prepare research artifacts, train, call Qwen or trade.

After all-window completion and process exit, it must call
`ai_trader.research.windowed_trial.load_completed_schedule` with the original schedule pin and
fresh bounded receipt/audit hashes. Only this metadata-only verification can support a campaign
completion report; individual `session_completed` rows are insufficient. Incomplete append
reads are unverified, not automatically corruption. Any failure, early process disappearance,
or missing verifiable completion after **17:20 UTC** is terminal for the follow-up: report the
retained evidence and remove the follow-up, without restart, later-date continuation or archiving.

The [official OpenAI scheduled-task documentation](https://learn.chatgpt.com/docs/automations?surface=app)
requires the computer and desktop app to remain running for local-file follow-ups. The collector
is a separate local process; the follow-up is a read-only observer, not its scheduler or executor.
