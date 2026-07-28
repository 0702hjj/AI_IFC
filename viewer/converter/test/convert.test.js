const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { convertIfc } = require("../convert");

const FIXTURE = path.join(__dirname, "fixtures", "wall-with-opening-and-window.ifc");
const OUT = path.join(__dirname, ".tmp-out");

test("convertIfc produces xkt and metadata", async (t) => {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });
  const stats = await convertIfc(FIXTURE, OUT);
  // 阈值说明：该夹具 IFC 源文件仅 ~12.5KB，xeokit 官方 convert2xkt 对其输出为 4004 字节；
  // 无几何的 XKT 远小于 4KB，故 >4KB 足以证明几何非平凡（brief 原阈值 10KB 对本夹具不可达）
  assert.ok(stats.xktBytes > 4 * 1024, "xkt should be non-trivial");
  assert.ok(stats.metaObjects > 0);
  const meta = JSON.parse(fs.readFileSync(path.join(OUT, "metadata.json"), "utf8"));
  const types = new Set(meta.metaObjects.map((o) => o.type));
  assert.ok([...types].some((t2) => t2.startsWith("Ifc")), "should contain Ifc* types");
  // 每个 propertySetIds 引用必须可解析
  const psetIds = new Set(meta.propertySets.map((p) => p.id));
  for (const o of meta.metaObjects) {
    for (const pid of o.propertySetIds || []) assert.ok(psetIds.has(pid), `dangling pset ${pid}`);
  }
  // parent 引用必须可解析或为 null
  const objIds = new Set(meta.metaObjects.map((o) => o.id));
  for (const o of meta.metaObjects) {
    if (o.parent != null) assert.ok(objIds.has(o.parent), `dangling parent ${o.parent}`);
  }
  // 至少一个构件携带属性集
  assert.ok(meta.metaObjects.some((o) => (o.propertySetIds || []).length > 0), "expected psets");
});
