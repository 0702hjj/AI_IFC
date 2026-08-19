// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// DXF 只读查看器：canvas 挂载 + 图层开关侧栏 + 选中属性面板 + unsupported 角标。
// 选中 key 写 useViewerStore.selectedId（与 XKT viewer 同一语义）；高亮在
// fabric 内部完成，不走 xeokit useVisibility。
// 选中面板可「定位脚本」：key → locate → requestScriptJump → DesignPanel 跳行
// （对齐 PropertyPanel 的 IFC guid 链路；dxf 端点按 key 定位）。miss/stale/
// 请求失败降级为非阻断只读提示。

import { useCallback, useState } from "react";
import { useViewerStore } from "@/viewer/store";
import { locateScriptByKey } from "@/api/client";
import { useDxfCanvasEngine } from "./useDxfCanvasEngine";
import type { DxfHoverInfo, DxfSelectionInfo } from "./useDxfCanvasEngine";
import { useDxfRender } from "./useDxfRender";
import "./DxfViewer.css";

export default function DxfViewer({ modelId }: { modelId: string }) {
  const [canvasEl, setCanvasEl] = useState<HTMLCanvasElement | null>(null);
  const [selected, setSelected] = useState<DxfSelectionInfo | null>(null);
  const [hover, setHover] = useState<DxfHoverInfo | null>(null);
  const [locating, setLocating] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const setSelectedStore = useViewerStore((s) => s.setSelected);
  const requestScriptJump = useViewerStore((s) => s.requestScriptJump);

  const onObjectSelected = useCallback(
    (info: DxfSelectionInfo | null) => {
      setSelected(info);
      setSelectedStore(info?.key ?? null);
      setNotice(null);
    },
    [setSelectedStore]
  );

  const { canvas, fitTo } = useDxfCanvasEngine({ canvasEl, onObjectSelected, onHover: setHover });
  const render = useDxfRender(modelId, canvas, fitTo);

  const locate = () => {
    if (!selected?.key || locating) return;
    setLocating(true);
    setNotice(null);
    locateScriptByKey(modelId, selected.key)
      .then((res) => {
        if (res.found && res.line != null) {
          requestScriptJump({ line: res.line, origin: res.origin, paramsKeys: res.params_keys });
          setNotice(
            res.origin === "traced"
              ? `已定位到脚本第 ${res.line} 行；该实体由运行期逻辑生成，请在脚本编辑器中手动修改`
              : `已定位到脚本第 ${res.line} 行`
          );
        } else if (res.stale) {
          setNotice("脚本有未运行的修改，调用点定位已过期；请先运行脚本");
        } else {
          setNotice("该实体没有脚本调用点（非脚本生成）；可在脚本编辑器中手动修改");
        }
      })
      .catch(() => setNotice("脚本定位不可用"))
      .finally(() => setLocating(false));
  };

  const isEmpty =
    render.payload != null &&
    render.payload.entities.length === 0 &&
    render.unsupportedCount === 0;

  return (
    <div className="dxf-viewer">
      <div className="dxf-canvas-wrap">
        <canvas ref={setCanvasEl} data-testid="dxf-canvas" className="dxf-canvas" />
        {isEmpty && <div className="dxf-empty">空图纸：render.json 无可绘制实体</div>}
        {render.error && <div className="dxf-error">{render.error}</div>}
        {render.unsupportedCount > 0 && (
          <div className="dxf-unsupported-badge">
            {render.unsupportedCount} 个不支持的实体
          </div>
        )}
        {hover && (
          <div className="dxf-hover-tip">
            {hover.layer}
            {hover.block ? ` · 块 ${hover.block}` : ""}
          </div>
        )}
      </div>
      <aside className="dxf-side">
        <div className="dxf-layers">
          <h3>图层</h3>
          {render.layers.map((l) => (
            <label key={l.name} className="dxf-layer-item">
              <input
                type="checkbox"
                checked={!render.hiddenLayers.includes(l.name)}
                onChange={() => render.toggleLayer(l.name)}
              />
              {l.name}
            </label>
          ))}
        </div>
        {selected && (
          <div className="dxf-selected-panel" data-testid="dxf-selected-panel">
            <h3>选中实体</h3>
            <dl>
              <dt>key</dt>
              <dd>{selected.key ?? "（块内子实体）"}</dd>
              <dt>类型</dt>
              <dd>{selected.entityType}</dd>
              <dt>图层</dt>
              <dd>{selected.layer}</dd>
              {selected.block && (
                <>
                  <dt>块</dt>
                  <dd>{selected.block}</dd>
                </>
              )}
            </dl>
            {selected.key && (
              <button
                type="button"
                className="dxf-locate-btn"
                disabled={locating}
                onClick={locate}
              >
                {locating ? "定位中…" : "定位脚本"}
              </button>
            )}
            {notice && <p className="dxf-locate-notice">{notice}</p>}
          </div>
        )}
      </aside>
    </div>
  );
}
