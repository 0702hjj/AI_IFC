#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj
set -euo pipefail
# 前提：server 已在 :8090 运行
BASE=http://localhost:8090
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FIXTURE="$(dirname "$0")/../converter/test/fixtures/wall-with-opening-and-window.ifc"
ID=$(curl -sf -F "file=@${FIXTURE}" "$BASE/api/v1/models" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["id"])')
echo "uploaded: $ID"
STATUS=""
for i in $(seq 1 30); do
  STATUS=$(curl -sf "$BASE/api/v1/models/$ID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["status"])')
  [ "$STATUS" = "ready" ] && break
  [ "$STATUS" = "failed" ] && { echo "conversion failed"; exit 1; }
  sleep 2
done
[ "$STATUS" = "ready" ] || { echo "timeout"; exit 1; }
curl -sf -o /dev/null -w "xkt: %{http_code} %{size_download}B\n" "$BASE/v1/models/$ID/model.xkt"
curl -sf -o /dev/null -w "meta: %{http_code} %{size_download}B\n" "$BASE/v1/models/$ID/metadata.json"
curl -sf -o /dev/null -w "download: %{http_code}\n" "$BASE/api/v1/models/$ID/download"
# issues CRUD
python3 -c 'import base64,sys;sys.stdout.buffer.write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))' > "$TMP/smoke-shot.png"
ISSUE_ID=$(curl -sf \
  -F 'issue={"entityId":"3a82-xxxx","entityName":"Wall","entityType":"IfcWall","title":"smoke issue","comment":"c","camera":{"eye":[1,2,3],"look":[0,0,0],"up":[0,0,1]}}' \
  -F "screenshot=@$TMP/smoke-shot.png;type=image/png" \
  "$BASE/api/v1/models/$ID/issues" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["id"])')
echo "issue created: $ISSUE_ID"
curl -sf "$BASE/api/v1/models/$ID/issues" | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert len(d)==1 and d[0]["status"]=="open" and d[0]["screenshot"].startswith("issues/"),d'
curl -sf -o /dev/null -w "shot: %{http_code}\n" "$BASE/v1/models/$ID/issues/$ISSUE_ID.png"
curl -sf -X PATCH -H 'Content-Type: application/json' -d '{"status":"resolved"}' \
  "$BASE/api/v1/models/$ID/issues/$ISSUE_ID" | python3 -c 'import sys,json;assert json.load(sys.stdin)["data"]["status"]=="resolved"'
curl -sf -X DELETE "$BASE/api/v1/models/$ID/issues/$ISSUE_ID" > /dev/null
curl -sf "$BASE/api/v1/models/$ID/issues" | python3 -c 'import sys,json;assert json.load(sys.stdin)["data"]==[]'
# overrides + changes
curl -sf -X PUT -H 'Content-Type: application/json' \
  -d '{"entityName":"Wall","fields":{"FireRating":"F60","Comments":"smoke edit"}}' \
  "$BASE/api/v1/models/$ID/entities/3a82-xxxx/properties" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert d["FireRating"]=="F60" and d["Comments"]=="smoke edit",d'
curl -sf "$BASE/api/v1/models/$ID/overrides" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert d["3a82-xxxx"]["FireRating"]=="F60" and d["3a82-xxxx"]["Comments"]=="smoke edit",d'
curl -sf -X PUT -H 'Content-Type: application/json' \
  -d '{"entityName":"Wall","fields":{"FireRating":"F90","Comments":""}}' \
  "$BASE/api/v1/models/$ID/entities/3a82-xxxx/properties" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert d["FireRating"]=="F90" and "Comments" not in d,d'
curl -sf "$BASE/api/v1/models/$ID/overrides" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert d["3a82-xxxx"]["FireRating"]=="F90" and "Comments" not in d["3a82-xxxx"],d'
curl -sf "$BASE/api/v1/models/$ID/changes" | python3 -c 'import sys,json
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
# edit flow（script 管线：暂存 → 沙箱 run → save 大版本；edit-service 不可达则跳过）
EDIT_URL=${VIEWER_EDIT_SERVICE_URL:-http://127.0.0.1:8100}
if curl -sf "$EDIT_URL/health" > /dev/null 2>&1; then
  # fixture 模型是 legacy（无脚本）→ GET /script 应 404，先确认基线
  GET_SCRIPT_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/models/$ID/script")
  [ "$GET_SCRIPT_CODE" = "404" ] || { echo "GET /script = $GET_SCRIPT_CODE, want 404 (legacy 无脚本)"; exit 1; }
  # 暂存一个最小契约合规 build 脚本（PARAMS + build + __main__，ifcopenshell.api 生成骨架墙）
  cat > "$TMP/smoke-build.py" <<'PY'
PARAMS = {"name": "Smoke Wall", "fireRating": "F60"}


def build(params, out_path):
    import ifcopenshell.api as api
    model = api.run("project.create_file")
    api.run("root.create_entity", model, ifc_class="IfcProject", name=params["name"])
    api.run("unit.assign_unit", model)
    api.run("context.add_context", model, context_type="Model")
    wall = api.run("root.create_entity", model, ifc_class="IfcWall", name=params["name"])
    api.run("pset.add_pset", model, product=wall, name="Pset_WallCommon")
    api.run("pset.edit_pset", model, pset=model.by_type("IfcPropertySet")[-1],
            properties={"FireRating": params["fireRating"]})
    model.write(out_path)


if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
PY
  SCRIPT_BODY=$(python3 -c 'import json,sys;print(json.dumps({"script": sys.stdin.read()}))' < "$TMP/smoke-build.py")
  curl -sf -X PUT -H 'Content-Type: application/json' -d "$SCRIPT_BODY" \
    "$BASE/api/v1/models/$ID/script" | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert d["staged"]>=1,d'
  curl -sf -X POST "$BASE/api/v1/models/$ID/script/run" \
    | python3 -c 'import sys,json;assert json.load(sys.stdin)["data"]["ok"] is True'
  V1=$(curl -sf -X POST "$BASE/api/v1/models/$ID/script/save" \
    | python3 -c 'import sys,json;v=json.load(sys.stdin)["data"]["version"];assert v=="v1",v;print(v)')
  # 版本记录：scripts（脚本 v1）+ versions（IFC 快照 v1）都在
  curl -sf "$BASE/api/v1/models/$ID/scripts" | python3 -c 'import sys,json
d=json.load(sys.stdin)["data"]
assert d["scripts"] and d["scripts"][0]["version"]=="v1",d'
  curl -sf "$BASE/api/v1/models/$ID/edit/versions" | python3 -c 'import sys,json
d=json.load(sys.stdin)["data"]
assert any(v["version"]=="v1" for v in d["versions"]) and d["current"]=="v1",d'
  # change log 不被 script 管线污染：仍只有 override 段写入的 4 条
  curl -sf "$BASE/api/v1/models/$ID/changes" | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];assert len(d)==4,d'
  STATUS=""
  for i in $(seq 1 30); do
    STATUS=$(curl -sf "$BASE/api/v1/models/$ID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["status"])')
    [ "$STATUS" = "ready" ] && break
    [ "$STATUS" = "failed" ] && { echo "reconversion failed"; exit 1; }
    sleep 2
  done
  [ "$STATUS" = "ready" ] || { echo "reconversion timeout"; exit 1; }
  echo "edit flow OK (saved $V1)"
else
  echo "edit flow SKIP (edit service unreachable at $EDIT_URL)"
fi
curl -sf -X DELETE "$BASE/api/v1/models/$ID" > /dev/null
echo "smoke OK"
