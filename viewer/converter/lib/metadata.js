const path = require("path");
const WebIFC = require("web-ifc");

async function extractMetadata(ifcData) {
  const ifcAPI = new WebIFC.IfcAPI();
  ifcAPI.SetWasmPath(path.join(__dirname, "..", "node_modules", "web-ifc") + "/", true);
  await ifcAPI.Init();
  const modelID = ifcAPI.OpenModel(new Uint8Array(ifcData));
  try {
    const props = new WebIFC.Properties(ifcAPI);
    const spatial = await props.getSpatialStructure(modelID, true);
    const metaObjects = [];
    const propertySets = [];

    async function walk(node, parentId) {
      const line = await ifcAPI.GetLine(modelID, node.expressID, true);
      const gid = line.GlobalId && line.GlobalId.value ? String(line.GlobalId.value) : `e${node.expressID}`;
      const type = line.constructor && line.constructor.name ? line.constructor.name : "IfcElement";
      const name = line.Name && line.Name.value != null ? String(line.Name.value) : type;
      const psets = await props.getPropertySets(modelID, node.expressID, true, false);
      const propertySetIds = [];
      for (const ps of psets || []) {
        const psId = `pset_${node.expressID}_${propertySetIds.length}`;
        const properties = (ps.HasProperties || []).map((p) => ({
          name: p.Name && p.Name.value != null ? String(p.Name.value) : "Property",
          value: p.NominalValue && p.NominalValue.value !== undefined ? p.NominalValue.value : null,
          type: p.NominalValue && p.NominalValue.type != null ? String(p.NominalValue.type) : "value",
        }));
        propertySets.push({ id: psId, name: ps.Name && ps.Name.value ? String(ps.Name.value) : "Pset", type: "Pset", properties });
        propertySetIds.push(psId);
      }
      const mo = { id: gid, type, name, parent: parentId };
      if (propertySetIds.length > 0) mo.propertySetIds = propertySetIds;
      metaObjects.push(mo);
      for (const child of node.children || []) await walk(child, mo.id);
    }

    await walk(spatial, null);
    return { projectId: "project", metaObjects, propertySets };
  } finally {
    ifcAPI.CloseModel(modelID);
  }
}

module.exports = { extractMetadata };
