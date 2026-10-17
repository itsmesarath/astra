# Footprint ("cluster") diagnostic on the thick-book reversal candidate — 17 Oct 2026

Code: `src/ai_trader/research/six_e_footprint_diagnostic.py`; result
`data/processed/6e_footprint_diagnostic_1.json`. Data: development store (Mar 2025 – Jun 2026),
bid/ask volume per price per minute (`tpx`) from the reconstructed book. Lockbox untouched.

Question: at the failed breakout, does the footprint (absorption at the extreme, delta, stacked
imbalances, volume burst) separate the candidate's winners from its losers — and does it do so
*more* than for random entries with the same filters (control)?

| feature (15-min window before entry) | candidate AUC (44 trades) | random control AUC (99) |
|---|---|---|
| aggressive volume at the extreme (absorption) | 0.51 | 0.50 |
| share of aggressive volume at the extreme | 0.52 | 0.50 |
| net delta in trade direction | 0.60 | 0.63 |
| entry-minute delta | 0.43 | 0.45 |
| stacked imbalance levels | 0.43 | 0.58 |
| window volume | 0.57 | 0.52 |
| volume vs trailing hour | 0.61 | 0.46 |

Reading:
- **Absorption carries no information** here: the volume hit into the low, and its share, are the
  same for winners and losers, in the candidate and in the control.
- **Net delta** does separate winners (AUC 0.60) — but it does so for random entries too (0.63), so it
  is the generic "flow in the direction of the next move" effect, not a property of the setup.
- **Volume burst vs trailing hour** is the only feature that looks setup-specific (0.61 vs 0.46 in the
  control). With 44 trades that is one noisy reading, not a finding.

Decision: no footprint condition is added to the rule. The live book store keeps `tpx` per minute, so
all these features can be recomputed for every live decision later; re-run this diagnostic when the
live tally reaches ~40 trades. The "cluster" view earns its place as a logged feature, not as a gate.
