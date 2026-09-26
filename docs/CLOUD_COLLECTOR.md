# Cloud BTCUSDT collector — operator guide

The collector runs on Google Cloud independently of this PC and ChatGPT. It
captures public Binance spot BTCUSDT order-book depth updates, a reconstruction
snapshot, and aggregate trades. It does **not** train Qwen, run a paper strategy,
or submit real orders. No OpenAI API key or exchange account key is required.

## Check it without ChatGPT

1. Open the [VM page](https://console.cloud.google.com/compute/instancesDetail/zones/europe-west1-b/instances/btcusdt-public-collector-1?project=collector-btc).
   Its name is `btcusdt-public-collector-1`; normal state is **Running**.
2. Open the [private bucket](https://console.cloud.google.com/storage/browser/collector-btc-btcusdt-20260925?project=collector-btc).
   Browse `btcusdt/sessions/YYYY/MM/DD/`. Each attempt produces an archive
   (`.tar.gz`) and a small readable `.receipt.json` file.
3. Check the newest receipt's UTC `completed_at` and `status`. During healthy
   operation, a new pair usually arrives a little over every five minutes.
   Refresh the page; VM state alone does not prove capture health. If no new
   receipts appear for 15 minutes, or failures recur, inspect the serial logs
   and retain the evidence. Do not treat interrupted sessions as complete.

You can close this chat or turn off your PC without stopping the **cloud**
collector. Any separate capture running on your PC still depends on that PC.
There is no heartbeat from ChatGPT required for the cloud service to run.
Billing emails are configured; capture-failure email alerts are not.

### Optional PowerShell checks

Google Cloud CLI is installed on this PC. These commands only inspect state;
they do not start, stop, or redeploy the collector. If your login expires,
authenticate through Google's official login flow; never paste keys into chat.

```powershell
$collectorGcloud = 'C:\Users\pabta\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
& $collectorGcloud compute instances describe btcusdt-public-collector-1 --zone=europe-west1-b --project=collector-btc --account=sarath.babu54@gmail.com --format='value(status)'
& $collectorGcloud storage ls 'gs://collector-btc-btcusdt-20260925/btcusdt/sessions/**' --project=collector-btc --account=sarath.babu54@gmail.com
& $collectorGcloud compute instances get-serial-port-output btcusdt-public-collector-1 --zone=europe-west1-b --project=collector-btc --account=sarath.babu54@gmail.com --port=1
```

For a particular receipt, use `gcloud storage cat` with its exact `gs://` path
and the same project/account flags. Downloading an archive through the bucket
UI or `gcloud storage cp` does not train a model or alter the cloud original.

## Limits, costs, and stopping

- The fixed VM shutdown timer is set to **2026-10-25 23:03:40 UTC**. It was
  installed and started at deployment; its future firing has not yet occurred.
- Captures use separate five-minute source sessions. Connection, snapshot,
  validation, compression, and upload take extra time. This is **not a gapless
  feed**; never join order-book sequences across sessions without a new snapshot.
- Each capture is bounded by the existing 32 MiB / 99,997-market-event limits.
  The service stops starting sessions at its deadline, 9,000 attempts, or
  30 GiB of uploaded compressed archives. The last bounded archive can take
  the total slightly over the archive-byte limit; small receipt objects are
  additional. A two-GiB free-disk guard protects the local spool.
- Failed attempts are archived under distinct session IDs. The next attempt
  follows a 60-second pause. Twelve consecutive capture failures halt further
  capture; the failure streak survives service restarts. Systemd retries a
  failed service with rate limits. Persistent failures need operator attention.
- Attempt/byte limits stop **capture**, not the VM. The fixed shutdown timer
  remains active. At shutdown an in-flight segment may remain partial locally;
  do not count it as uploaded. Do not automatically extend or restart this trial.
- The €15 monthly project budget sends actual-spend warnings at €7.50, €12,
  and €15. It is **not a spending cap** and reporting can lag. It does not
  guarantee that the bill stays below €15.

To stop early, use **Stop** on the VM page and confirm; this interrupts the
current segment but preserves the persistent disk and already-uploaded objects.
Do not choose **Delete**. A stopped VM still leaves billable disk and bucket
storage. Automatic VM shutdown does not delete data or eliminate all charges.
Bucket lifecycle deletion is not enabled; retain or remove data deliberately
after review. The bucket has seven-day soft-delete recovery, not seven-day
automatic expiry.

## Deployment identity and safeguards

- Project: `collector-btc` (`958144707510`); zone: `europe-west1-b`.
- VM: Debian 13, `e2-micro`, 20 GB standard persistent boot disk. Its external
  IPv4 is ephemeral; use the VM name, not a hard-coded address.
- Bucket: `gs://collector-btc-btcusdt-20260925`, Standard storage in
  `EUROPE-WEST1`, uniform access, public access prevention enforced.
- Managed VM identity:
  `btcusdt-collector@collector-btc.iam.gserviceaccount.com`, with bucket-level
  Object Creator and Object Viewer permissions. No project IAM grants or
  downloaded service-account keys were configured for this identity.
- Dedicated VPC with no inbound firewall rules; no public SSH/HTTP endpoint.
  The service runs as an unprivileged user with a read-only system filesystem
  and a writable `/var/lib/ai-trader-collector` spool. No model files or trading
  credentials were installed. The public-data service does not call an LLM.
- Archives and receipts are uploaded create-only. Size and checksum verification
  precede removal of heavy local spool files. Small local receipts and upload
  markers remain. Pending uploads are recovered before any new capture.
- Deployed source archive SHA-256:
  `fac68d128a878c35f17fc3a0294027c4da1dbe711295d79c9ebe89915b5aae53`.
  The release is stored under
  `releases/ai-trader-cloud-fac68d128a878c35f17fc3a0294027c4da1dbe711295d79c9ebe89915b5aae53.tar.gz`.
  Local code edits do not change the installed release. This pins source bytes,
  not all OS/transitive dependency versions for a future rebuild.

## Verification record — 2026-09-26

At approximately 11:58 UTC the bucket contained 146 archive/receipt pairs:
144 completed and two failed (`CaptureInterrupted`). All 146 receipt records
reported public-data-only, no orders, and no training. Archives plus receipts
occupied 37,994,464 bytes. This is a timestamped observation, not a promise
about future uptime or a validation of every archive.

Retained failed sessions:

- `s_20260926T015140Z_0fe21fd1cbc5`
- `s_20260926T082937Z_eb4ab0fd03e2`

Downloaded sample `s_20260926T114948Z_3ea9c7f0e7ae`:

- Completion: `2026-09-26T11:55:02.358353+00:00`.
- Counts: 2,999 depth updates and 1,149 aggregate trades.
- Archive: 204,175 bytes; SHA-256
  `f0b50802eafca7d2d3641e5017cd3a1d35068fcd834f4449e5b14f043462e1ca`.
- Raw capture: 2,029,898 bytes; SHA-256
  `34a85ff6940184bc6b77c579a462593c8d8fa09c20f37e5c2e67c7377e1d0fd9`.
- Archive/member sizes and hashes matched the receipt; the downloaded capture
  passed the existing receipt-causal order-book integrity replay locally.

The VM remained running and a subsequent check found 147 receipts (145
completed, two failed), latest completion at 12:00:15 UTC. All 147 had the
expected public-data-only/no-orders/no-training flags. Failed receipts preserve
the error type, not a full root-cause diagnosis. Do not count either failed
session as usable training data.

Local verification after implementation: Ruff passed; the complete test suite
reported **2,933 passed, one skipped** (optional Nautilus evaluation dependency).
Both Linux launch scripts passed Bash syntax checks. Cloud spool/upload tests
use fake collectors/uploaders; the downloaded-sample check above is the separate
real-cloud integration evidence. No training or trades were started by these
checks.

## After capture: research and training

Live collection is not automatic learning. Before any later training, verify
each selected archive and raw hash, reconstruct and validate its book, derive
causal microstructure/CVD features, and keep every source session exclusive to
one dataset split. Label possible outcomes using explicit execution costs and
time horizons. Discovery data already inspected here are not an untouched
final test; reserve prospectively collected sessions for that purpose.

Qwen fine-tuning, strategy validation, and paper execution are separate jobs.
This small collector VM is not configured for those jobs or for GPU training.
Neither a `completed` capture nor a successful training run proves a strategy
profitable or authorizes live trading.
