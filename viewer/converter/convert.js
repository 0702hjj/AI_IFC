#!/usr/bin/env node
// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

const fs = require("fs");
const path = require("path");
const { XKTModel, parseIFCIntoXKTModel, writeXKTModelToArrayBuffer } = require("@xeokit/xeokit-convert");
const WebIFC = require("web-ifc");
const { extractMetadata } = require("./lib/metadata");

async function convertIfc(inputPath, outDir) {
  const ifcData = fs.readFileSync(inputPath);
  const meta = await extractMetadata(ifcData);

  const xktModel = new XKTModel();
  await parseIFCIntoXKTModel({
    WebIFC,
    data: ifcData,
    xktModel,
    wasmPath: "./",
    log: (msg) => console.error(`[parseIFC] ${msg}`),
  });

  for (const ps of meta.propertySets) {
    xktModel.createPropertySet({
      propertySetId: ps.id,
      propertySetType: ps.type,
      propertySetName: ps.name,
      properties: ps.properties.map((p, i) => ({ id: `${ps.id}_p${i}`, type: "Default", name: p.name, value: p.value })),
    });
  }
  for (const mo of meta.metaObjects) {
    xktModel.createMetaObject({
      metaObjectId: mo.id,
      metaObjectType: mo.type,
      metaObjectName: mo.name,
      parentMetaObjectId: mo.parent || undefined,
      propertySetIds: mo.propertySetIds || [],
    });
  }

  const entityIds = Object.keys(xktModel.entities || {});
  const metaIds = new Set(meta.metaObjects.map((o) => o.id));
  const matched = entityIds.filter((id) => metaIds.has(id));
  if (entityIds.length > 0 && matched.length === 0) {
    throw new Error(`entity id mismatch: sample entity ids ${entityIds.slice(0, 3).join(",")} not found in metamodel; inspect xktModel.entities keys and adjust extractMetadata id mapping`);
  }

  await xktModel.finalize();
  const xktArrayBuffer = writeXKTModelToArrayBuffer(xktModel, "", {}, {});

  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, "model.xkt"), Buffer.from(xktArrayBuffer));
  fs.writeFileSync(path.join(outDir, "metadata.json"), JSON.stringify(meta, null, 2));
  return { xktBytes: xktArrayBuffer.byteLength, metaObjects: meta.metaObjects.length };
}

if (require.main === module) {
  const [input, outDir] = process.argv.slice(2);
  if (!input || !outDir) {
    console.error("usage: node convert.js <input.ifc> <outDir>");
    process.exit(2);
  }
  convertIfc(input, outDir)
    .then((stats) => console.log(JSON.stringify({ ok: true, ...stats })))
    .catch((err) => { console.error(`conversion failed: ${err.message}`); process.exit(1); });
}

module.exports = { convertIfc };
