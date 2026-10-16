# Snapshot-preserving bridge regression window amendment

## Prospective need and exact authority

The direct 2026-10-15 eight-hour instruction establishes06:59:08Z–14:59:08Z and standing routine permission. Before today's whole regression, static inspection found the accepted test-only `tests/source_publication_bridge_oracles_20261014.py` still checks actual fresh native receipt times against yesterday's fixed window. No permission question or expired-window bypass is required. The current full body/identity/limit/cleanup/time-order assertions remain mandatory.

Original complete file:69,244bytes/SHA256`bc35d03137feed6ea49d024dcc9b047fd6bafa0ff6dbdd296e780377fac5ee7a`. Preserve its exact complete bytes as `logs/local_member_intake_proof_20261015_1/bridge_oracle_original_20261014.snapshot` before editing. No production file changes.

Only two full assignment lines may change:

```python
WINDOW_START = datetime(2026, 10, 14, 7, 33, 18, tzinfo=UTC)
HARD_END = datetime(2026, 10, 14, 13, 33, 18, tzinfo=UTC)
```

become:

```python
WINDOW_START = datetime(2026, 10, 15, 6, 59, 8, tzinfo=UTC)
HARD_END = datetime(2026, 10, 15, 14, 59, 8, tzinfo=UTC)
```

No assertion/callable/expected body/serializer/skip/collection identity may change. In particular `assert WINDOW_START <= times[0] <= times[1] <= HARD_END` stays byte-for-byte unchanged. This is a second precisely registered old test-support exception, alongside the already reviewed qualification-test one-literal amendment. All439otheroldPython/oldproduction remain held. Today's exact registered set remains448 until another explicit new-file release.

## Required closure before runtime

Root must prove original snapshot raw identity, exactly one occurrence of each old/new assignment, exact whole-file two-substitution equality and reverse-assignment byte equality; retain actual new raw length/hash and complete difference evidence. Independent exact-byte/guard review must close before any future collection/regression. Root tools/comparators must verify this new exact source identity and current literals; do not rebind function globals or relax any receipt data to compensate. Historical reports and original freeze containers keep their original raw pins, with this explicit current-file exception only.

Status at registration: **PROPOSED / UNEXECUTED**. No test/import/native run follows merely from this document. Current14:59:08Zhardend unchanged.

Later actual closure: root [whole-byte proof](../logs/local_member_intake_proof_20261015_1/bridge_oracle_window_amendment_acceptance_1.json) at10:11:37.3089260Z accepted exact69,242currentbytes/SHA256`305441e117100f95e80b0bd4f59f3db15ac0c3484579c2df1f5352132cc743c3`, unchanged original snapshot69,244bytes, exactly two assignment deltas at original offsets54,592/54,653, strict whole-file forward/reverse equality and unchanged time-order guard. All439otheroldPython pins and separate qualification amendment/raw freeze stayed held. Complete independent actual review [closed without Required finding](../logs/local_member_intake_proof_20261015_1/bridge_oracle_window_amendment_review_1.json). The earlier status is preserved chronology, not a current permission or evidence blocker. No pytest/native runtime was launched by this amendment.
