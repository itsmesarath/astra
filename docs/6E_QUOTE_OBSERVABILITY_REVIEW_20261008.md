# 6E Quote Observability Review

The complete development-cohort comparison verified 196 sessions, 2,136,770 decisions and 5,381,624 counterfactual exit requests on 8 October 2026. Most exits that lacked a new quote within the original deadline still had a recently observed quote. This makes quote observability an important part of the next execution study, but does not establish an executable price, a profitable strategy or a new training label.

The original targets and models remain unchanged. No training, model inference, archive replay, reserved-price access, downloads, collection or trading occurred. The BTC collector was outside this work.

## Cohort and conservation

The comparison used the existing pinned native quote columns and target files for every accepted development session. These cover the fixed 12:00–16:00 UTC decision windows from 26 March through 31 December 2025, not every hour of the historical archive. The original excluded and reserved metadata dispositions remain in the registration.

| Existing role | Sessions | Original decisions | Counterfactual exit requests |
| --- | ---: | ---: | ---: |
| Train | 112 | 1,242,509 | 2,990,120 |
| Validation development | 43 | 473,337 | 1,264,800 |
| Test development | 41 | 420,924 | 1,126,704 |
| Total | 196 | 2,136,770 | 5,381,624 |

All three roles have already been exposed during development; none is an independent holdout. Every original decision remains represented, including 551,804 ineligible decisions, 86,436 entry timeouts and 153,124 widened-spread entry refusals. The 1,345,406 entered counterfactuals each contribute two directions under two exit plans. Their overlapping outcomes are not a simultaneous portfolio or independent trades.

The comparison rechecked 129,039,967 native completed quotes. It retained the original session and contract boundaries, native event ordering, entry eligibility, 100 ms exit delay and one-second fresh-quote deadline. Every original resolved exit matched its first native quote timestamp and bid/ask identity. Original unknown exits stayed unknown.

## Reference age among unresolved exits

A reference is the latest completed quote at or before the delayed exit request, within its explicitly declared historical vendor-receive prefix. It is not a broker fill, evidence of transport health, or proof of local publication timing. The age bands below are fixed descriptive categories, not alternative trading thresholds selected for performance.

| Reference age at delayed request | Time exit unknown side outcomes | Bracket exit unknown side outcomes |
| --- | ---: | ---: |
| At most 100 ms | 31,570 | 28,768 |
| Over 100 through 250 ms | 36,250 | 13,111 |
| Over 250 through 1,000 ms | 88,370 | 33,823 |
| Over 1,000 ms | 48,274 | 21,619 |
| No prior reference | 0 | 0 |
| Total unknown side outcomes | 204,464 | 97,321 |

A reference no more than one second old existed for 156,190 of the 204,464 unknown time-exit side outcomes (76.39%) and 75,702 of the 97,321 unknown bracket-exit side outcomes (77.79%). Long and short time exits share the same requests, so those counts are paired duplicates rather than additional independent opportunities.

This finding supports investigating how the fresh-event requirement affects outcome observability. It does not distinguish a quiet but valid standing book from missing feed events, cancellations not observed by a broker, or a price that could not actually be executed. Futures quote history also does not establish a cTrader EURUSD CFD fill.

The reference lookup preserves an explicit native publication cursor for equal-time events. The historical census declares its cursor from the vendor receive boundary; it does not claim that cursor was observed by our live system. No equal-time first-fresh versus latest-reference cursor differences occurred in these exit requests, but synthetic tests cover that distinction. The first strictly later event is tracked separately and never moved backward to invent an earlier fill.

## Implementation and verification

The standalone implementation is `src/ai_trader/research/six_e_quote_observability.py`. It validates read-only quote columns once per session, performs vectorized prefix lookups, and emits counts plus an ordered descriptor SHA256. Per-request native cursors and ages remain reproducible from the retained inputs; the comparison exports no mark prices, net returns, replacement labels or training dataset.

The registration binds the original collection, completion and verification pins, all 41 implementation source pins, complete coverage, one exclusive result path and resource limits. The run took approximately 77 seconds against a 30-minute total cap and a 60-second session cap. A separate read-only verifier recomputed every session and pooled metric, checked the original exit identities and rechecked input content hashes. The result pin also matched after verification.

There are no retries or successful-subset completion. An exclusive attempt file, owned durable progress journal and retained failure evidence prevent silent continuation. Unknown counterfactual exit liabilities remain explicitly unreconciled; the comparison neither closes them at a reference mark nor resets an account at midnight. All training, execution, promotion, trading and independent-holdout authority flags are false.

The final focused verification passed 183 Python tests, including all 57 new observability tests, and all 38 JavaScript tests passed. Ruff and formatting checks passed for the new code. The complete Python baseline, continued past collection errors to exercise the remaining tests, finished with 4,321 passed, one optional Nautilus skip and ten collection errors. Those errors arose because Windows Smart App Control blocked the unsigned PyTorch `c10.dll`; Windows Code Integrity events confirmed the path and signing-policy block. Security settings and installed dependencies were not changed. The baseline collected before the new test file was added, so the separate 183-test run covers the new implementation; these totals overlap and must not be added together as a single full-suite result. A fully green suite remains unavailable until the environment issue is resolved.

## Next development decision

The next step is an explicit paper-account closure and reconciliation contract, before any revised execution assumption is used for economic scoring. A selected position with an unresolved exit must carry an open liability across session boundaries until closure evidence is available. Reference marks may describe that liability, but cannot turn it into a realized return.

A separate future experiment can then specify standing-quote handling, receive-clock assumptions, latency, stale-feed refusal and costs before looking at revised results. Keep the original targets as a control, include missing and adverse sessions, and use a genuinely untouched prospective cohort for promotion. Do not choose an age cutoff merely because it resolves more cases. A temporal strategy or Qwen retraining study should follow only after its execution labels and account treatment are defensible.

## Reproducible evidence

The registered result is `data/processed/6e_quote_observability_20261008_1.json`. The registration is `logs/6e_quote_observability_20261008_1_registration.json`.

| Evidence | SHA256 |
| --- | --- |
| Observability registration | `d13052d355834fbdaeecd4efaaed3cbe76bf7e419683b78d42f613db9969c1a2` |
| Observability result | `18b8059d229fa103891491cb9d584e167b069f02c36d8958f3cef62b7ac2b0db` |
| Implementation | `5e6048c64c2ee4fa8b08685eb6068e659fa2e55899510225d92ab9ecd93b6a3f` |
| Observability tests | `2754bd97d8c7a572575db473d766d8e4dff3896c471d76099c5d09a050356240` |
| Exclusive attempt | `7b7516a4293b337393762f550e307f6dc827b54225020a244d00c8856845f696` |
| Owned progress journal | `64c2eafcafca60d6fb729fc514b3c7d0cf2480c3bc0545253229443b3f7165c0` |
| Original collection completion | `c3c14ecf5344556c2aa3037e54979a2c3bbc417fe387775a44c266ec9d7ce58b` |
| Original collection verification | `22cdcb35811abd1d44fc4b3118e3a083cd9cf2f56572c9bf1a9c4847e2638e7c` |

From PowerShell in `C:\Users\pabta\Projects\ai-trader`, this command verifies the existing result without launching another run or changing files:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.six_e_quote_observability verify --registration logs/6e_quote_observability_20261008_1_registration.json --registration-sha256 d13052d355834fbdaeecd4efaaed3cbe76bf7e419683b78d42f613db9969c1a2 --output data/processed/6e_quote_observability_20261008_1.json --result-sha256 18b8059d229fa103891491cb9d584e167b069f02c36d8958f3cef62b7ac2b0db
```

Expected status: `verified_quote_observability_not_execution_validation`, with 196 sessions, 2,136,770 rows and all authority flags false. Verification does not authorize relabeling, training or trading.
