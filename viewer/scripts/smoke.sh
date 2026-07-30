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
# issues CRUD
python3 -c 'import base64,sys;sys.stdout.buffer.write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))' > /tmp/smoke-shot.png
ISSUE_ID=$(curl -sf \
  -F 'issue={"entityId":"3a82-xxxx","entityName":"Wall","entityType":"IfcWall","title":"smoke issue","comment":"c","camera":{"eye":[1,2,3],"look":[0,0,0],"up":[0,0,1]}}' \
  -F "screenshot=@/tmp/smoke-shot.png;type=image/png" \
  "$BASE/api/models/$ID/issues" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["id"])')
echo "issue created: $ISSUE_ID"
curl -sf "$BASE/api/models/$ID/issues" | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert len(d)==1 and d[0]["status"]=="open" and d[0]["screenshot"].startswith("issues/"),d'
curl -sf -o /dev/null -w "shot: %{http_code}\n" "$BASE/models/$ID/issues/$ISSUE_ID.png"
curl -sf -X PATCH -H 'Content-Type: application/json' -d '{"status":"resolved"}' \
  "$BASE/api/models/$ID/issues/$ISSUE_ID" | python3 -c 'import sys,json;assert json.load(sys.stdin)["data"]["status"]=="resolved"'
curl -sf -X DELETE "$BASE/api/models/$ID/issues/$ISSUE_ID" > /dev/null
curl -sf "$BASE/api/models/$ID/issues" | python3 -c 'import sys,json;assert json.load(sys.stdin)["data"]==[]'
# overrides + changes
curl -sf -X PUT -H 'Content-Type: application/json' \
  -d '{"entityName":"Wall","fields":{"FireRating":"F60","Comments":"smoke edit"}}' \
  "$BASE/api/models/$ID/entities/3a82-xxxx/properties" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert d["FireRating"]=="F60" and d["Comments"]=="smoke edit",d'
curl -sf "$BASE/api/models/$ID/overrides" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert d["3a82-xxxx"]["FireRating"]=="F60" and d["3a82-xxxx"]["Comments"]=="smoke edit",d'
curl -sf -X PUT -H 'Content-Type: application/json' \
  -d '{"entityName":"Wall","fields":{"FireRating":"F90","Comments":""}}' \
  "$BASE/api/models/$ID/entities/3a82-xxxx/properties" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert d["FireRating"]=="F90" and "Comments" not in d,d'
curl -sf "$BASE/api/models/$ID/overrides" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert d["3a82-xxxx"]["FireRating"]=="F90" and "Comments" not in d["3a82-xxxx"],d'
curl -sf "$BASE/api/models/$ID/changes" | python3 -c 'import sys,json
d=json.load(sys.stdin)["data"]
fr=[e for e in d if e["field"]=="FireRating"]
cm=[e for e in d if e["field"]=="Comments"]
assert len(d)==4 and len(fr)==2 and len(cm)==2,d
assert any(e["oldValue"]=="" and e["newValue"]=="F60" for e in fr),d
assert any(e["oldValue"]=="F60" and e["newValue"]=="F90" for e in fr),d
assert any(e["oldValue"]=="" and e["newValue"]=="smoke edit" for e in cm),d
assert any(e["oldValue"]=="smoke edit" and e["newValue"]=="" for e in cm),d
assert all(e["author"]=="local-user" and e["provenance"]["source"]=="UI" for e in d),d'
echo "overrides+changes OK"
curl -sf -X DELETE "$BASE/api/models/$ID" > /dev/null
echo "smoke OK"
