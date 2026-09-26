# BTCUSDT 24-hour discovery capture — 2026-09-25

This is a **public-market-data, research-only** local run. It does not use account
credentials, place paper or live orders, train a model, or promote a strategy.
The entire run is discovery data; it is not a reserved evaluation set.

## Run identity and bounds

- Service ID: `btcusdt-24h-discovery-20260925-1`.
- Started: 2026-09-25 21:57:35 UTC.
- Requested: 288 sequential five-minute segments, totaling 24 hours of nominal
  recording time. Connection, snapshot, validation, and segment transitions add
  wall-clock time and can leave gaps. This is not a promise of uninterrupted
  24-hour coverage.
- Local directory: `data/raw/btcusdt_24h_discovery_20260925_1`.
- Audit manifest: `data/raw/btcusdt_24h_discovery_20260925_1/btcusdt-24h-discovery-20260925-1.jsonl`.
- Per-segment limits: at most 32 MiB and 99,997 market events. Across 288
  segments, published raw data are bounded by 9 GiB. The service stops on the
  first failed segment; it does not retry, replace, or silently skip failures.
- Launched through `.venv/Scripts/python.exe -m ai_trader.ingestion.paper_data_service`
  with `--enable-public-data --sessions 288 --seconds-per-session 300
  --skip-features` and the service ID/output directory above. Python launcher
  PID 39732 and child PID 42700 were observed with matching command lines at
  launch; PIDs alone are not durable process identity.
- Standard output and error: `logs/btcusdt_24h_discovery_20260925_1_stdout.log`
  and `logs/btcusdt_24h_discovery_20260925_1_stderr.log`.

The host was on AC power at launch. Windows' active plan has no AC idle-sleep
timeout, but a ten-minute battery idle-sleep timeout. Power loss, sleep, network
failure, source-data staleness, quota exhaustion, or interruption can stop this
single-use run. Do not remove its lock or restart into the same directory.

At 22:03:33 UTC, the first segment had completed and passed the collector's
integrity replay: 1,602 aggregate trades and 2,995 depth updates, 2,601,418
bytes, SHA-256 `e4806147d69c75017f97269ad9be229cf36aba94dd9d64cf2a7bb3acbb4c14d9`.
Segment two had started. The append-only manifest, not this time-stamped note
or process presence, is authoritative for later progress and terminal status.

## Later research boundary

Retain every completed, failed, and partial segment. Verify each raw hash,
capture footer, sequence, receipt freshness, and book reconstruction before
deriving causal order-book/CVD features. A five-minute segment is a separate
source session; do not assume continuity through connection/snapshot gaps.
Discover possible trades with frozen fill/cost/horizon assumptions and
features available at each decision time. Do not relabel a zero-trade paper
session as a win, or use this inspected discovery run as an untouched final
test. Later validation needs separately collected, prospectively assigned days.

## Cloud transfer pilot

The user confirmed the connected Google Drive account as the intended destination.
The first completed segment was uploaded to a new
[Drive folder](https://drive.google.com/drive/folders/1I__uXFwlg7NHoSky2RuW3W0-g27btILr).
The [Drive copy](https://drive.google.com/file/d/1xO9Dffhvm3IziNS8WZisnxGG2YzYnrtk/view)
was read back through Drive metadata and a raw-file fetch; its reported size is
2,601,418 bytes, matching the local file. This is a transfer pilot, not a
continuous upload service or an independently verified cloud SHA-256.
The user clarified that the desired cloud outcome is an always-on collector
that keeps running when the local PC is off, not mirroring local captures to
Drive. No further Drive upload is planned for this run; the user elected to
leave the one test copy and its folder in place.

Google Cloud project `collector-btc` (project number `958144707510`) was
confirmed linked to a paid billing account. On 2026-09-25, a project-scoped,
monthly €15 **alerts-only** budget named
`Auto-Trader collector-btc monthly €15 warning` was created and verified in
the Cloud Billing list. Its actual-spend email thresholds are 50% (€7.50),
80% (€12), and 100% (€15), addressed to billing admins/users and project
owners. This is **not a spending cap**: charges can continue above €15, and
cost reporting can lag. The billing account's listed credits were expired.

On 2026-09-25, a Compute Engine VM named `btcusdt-public-collector-1` was
created in `europe-west1-b`: Debian 13, `e2-micro` (1 GB RAM), 20 GB standard
persistent boot disk, standard-tier ephemeral external IPv4. It uses the
purpose-built VPC `btcusdt-collector-vpc` and subnet
`btcusdt-collector-euw1` (`10.70.0.0/24`), with zero inbound firewall rules.
HTTP/HTTPS ingress, automatic snapshots, the Ops Agent, and the default
service account are disabled; Secure Boot, vTPM, and integrity monitoring are
enabled. No trading credentials or model files were installed. After the
initial stopped-state review, a pinned public-data collector was deployed and
the VM started at 2026-09-25 23:05:19 UTC. It now captures independently of
this PC. Its ephemeral IP may change on restart.

The console's creation estimate was US$6.73/month for the running VM and
20 GB standard disk, excluding the in-use public IPv4 charge, Cloud Storage,
network egress, logging, taxes, and any price changes. The €15 budget sends
warnings only and does not stop charges. A stopped VM can still incur disk
charges. A private Cloud Storage bucket, narrowly scoped managed VM identity,
bounded capture service, and fixed shutdown timer are now configured.
The collector has a 30 GiB compressed-archive threshold, a 9,000-attempt limit,
and a fixed VM shutdown at 2026-10-25 23:03:40 UTC. No automatic bucket deletion
policy is enabled, so disk and stored objects can remain billable after shutdown.
Google AI Pro storage/Colab benefits do not by themselves provide an always-on
collector. See [the cloud operator guide](CLOUD_COLLECTOR.md) for verification,
limits, checking progress, and stopping it without ChatGPT.
