#!/usr/bin/env bash
set -euo pipefail
# 前提：server 已在 :8090 运行
BASE=http://localhost:8090
FIXTURE="$(dirname "$0")/../converter/test/fixtures/wall-with-opening-and-window.ifc"
ID=$(curl -sf -F "file=@${FIXTURE}" "$BASE/api/models" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["id"])')
echo "uploaded: $ID"
STATUS=""
for i in $(seq 1 30); do
  STATUS=$(curl -sf "$BASE/api/models/$ID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["status"])')
  [ "$STATUS" = "ready" ] && break
  [ "$STATUS" = "failed" ] && { echo "conversion failed"; exit 1; }
  sleep 2
done
[ "$STATUS" = "ready" ] || { echo "timeout"; exit 1; }
curl -sf -o /dev/null -w "xkt: %{http_code} %{size_download}B\n" "$BASE/models/$ID/model.xkt"
curl -sf -o /dev/null -w "meta: %{http_code} %{size_download}B\n" "$BASE/models/$ID/metadata.json"
curl -sf -o /dev/null -w "download: %{http_code}\n" "$BASE/api/models/$ID/download"
curl -sf -X DELETE "$BASE/api/models/$ID" > /dev/null
echo "smoke OK"
