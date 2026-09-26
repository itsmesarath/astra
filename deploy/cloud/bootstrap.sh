#!/bin/bash
# GCE metadata startup script. The release hash and 30-day end are pinned in
# instance metadata before first boot; no credentials or trading code are used.
set -euo pipefail
exec > >(tee -a /var/log/ai-trader-bootstrap.log) 2>&1

metadata() {
  curl -fsS -H 'Metadata-Flavor: Google' \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"
}

bucket="$(metadata collector-bucket)"
object="$(metadata collector-release-object)"
expected_sha="$(metadata collector-release-sha256)"
stop_at="$(metadata collector-stop-at-utc)"
case "$bucket" in
  collector-btc-btcusdt-20260925) ;;
  *) echo 'Unexpected bucket'; exit 1 ;;
esac
case "$expected_sha" in
  *[!0-9a-f]*|'') echo 'Invalid release SHA-256'; exit 1 ;;
esac
if [ "${#expected_sha}" -ne 64 ]; then
  echo 'Invalid release SHA-256 length'
  exit 1
fi
if [ -f /opt/ai-trader/installed.sha256 ] && \
   [ "$(cat /opt/ai-trader/installed.sha256)" = "$expected_sha" ]; then
  systemctl start ai-trader-collector-stop.timer
  systemctl start ai-trader-collector.service
  echo 'Pinned collector release already installed'
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl python3 python3-venv python3-pip
install -d -m 0755 /opt/ai-trader
python3 -m venv /opt/ai-trader/bootstrap-venv
/opt/ai-trader/bootstrap-venv/bin/pip install --disable-pip-version-check 'uv==0.12.19'

token="$(curl -fsS -H 'Metadata-Flavor: Google' \
  'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
encoded_object="$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$object")"
curl -fsS --retry 3 -H "Authorization: Bearer $token" \
  "https://storage.googleapis.com/storage/v1/b/$bucket/o/$encoded_object?alt=media" \
  -o /opt/ai-trader/release.tar.gz
unset token
echo "$expected_sha  /opt/ai-trader/release.tar.gz" | sha256sum -c -
install -d -m 0755 /opt/ai-trader/release
tar -xzf /opt/ai-trader/release.tar.gz -C /opt/ai-trader/release

export UV_PYTHON_INSTALL_DIR=/opt/ai-trader/python
/opt/ai-trader/bootstrap-venv/bin/uv python install 3.12
/opt/ai-trader/bootstrap-venv/bin/uv venv --python 3.12 /opt/ai-trader/venv
/opt/ai-trader/bootstrap-venv/bin/uv pip install \
  --python /opt/ai-trader/venv/bin/python '/opt/ai-trader/release[cloud]'
/opt/ai-trader/venv/bin/python -c 'import ai_trader.ingestion.cloud_capture_service'

if ! id ai-trader-collector >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/ai-trader-collector \
    --shell /usr/sbin/nologin ai-trader-collector
fi
install -m 0755 /opt/ai-trader/release/deploy/cloud/run-collector.sh \
  /opt/ai-trader/run-collector.sh
install -m 0644 /opt/ai-trader/release/deploy/cloud/ai-trader-collector.service \
  /etc/systemd/system/ai-trader-collector.service
install -m 0644 /opt/ai-trader/release/deploy/cloud/ai-trader-collector-stop.service \
  /etc/systemd/system/ai-trader-collector-stop.service
printf 'COLLECTOR_BUCKET=%s\nCOLLECTOR_STOP_AT_UTC=%s\n' "$bucket" "$stop_at" \
  > /etc/ai-trader-collector.env
chmod 0600 /etc/ai-trader-collector.env
stop_calendar="$(date -u -d "$stop_at" '+%Y-%m-%d %H:%M:%S UTC')"
sed "s/__STOP_CALENDAR__/$stop_calendar/" \
  /opt/ai-trader/release/deploy/cloud/ai-trader-collector-stop.timer.in \
  > /etc/systemd/system/ai-trader-collector-stop.timer
chmod 0644 /etc/systemd/system/ai-trader-collector-stop.timer
printf '%s\n' "$expected_sha" > /opt/ai-trader/installed.sha256
systemctl daemon-reload
systemctl enable --now ai-trader-collector-stop.timer
systemctl enable --now ai-trader-collector.service
echo 'Collector bootstrap complete'
