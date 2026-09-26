#!/bin/sh
set -eu

exec /opt/ai-trader/venv/bin/python -m ai_trader.ingestion.cloud_capture_service \
  --enable-public-data \
  --bucket "$COLLECTOR_BUCKET" \
  --spool /var/lib/ai-trader-collector \
  --stop-at-utc "$COLLECTOR_STOP_AT_UTC" \
  --seconds-per-session 300 \
  --max-attempts 9000 \
  --max-uploaded-bytes 32212254720
