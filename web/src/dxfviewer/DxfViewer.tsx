// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// DXF 只读查看器：canvas 挂载 + 图层开关侧栏 + 选中属性面板 + unsupported 角标。
// 选中 key 写 useViewerStore.selectedId（与 XKT viewer 同一语义）；高亮在
// fabric 内部完成，不走 xeokit useVisibility。

import { useCallback, useState } from "react";
import { useViewerStore } from "@/viewer/store";
import { useDxfCanvasEngine } from "./useDxfCanvasEngine";
import type { DxfHoverInfo, DxfSelectionInfo } from "./useDxfCanvasEngine";
import { useDxfRender } from "./useDxfRender";
import "./DxfViewer.css";

export default function DxfViewer({ modelId }: { modelId: string }) {
  const [canvasEl, setCanvasEl] = useState<HTMLCanvasElement | null>(null);
  const [selected, setSelected] = useState<DxfSelectionInfo | null>(null);
  const [hover, setHover] = useState<DxfHoverInfo | null>(null);
  const setSelectedStore = useViewerStore((s) => s.setSelected);

  const onObjectSelected = useCallback(
    (info: DxfSelectionInfo | null) => {
      setSelected(info);
      setSelectedStore(info?.key ?? null);
    },
    [setSelectedStore]
  );

  const { canvas, fitTo } = useDxfCanvasEngine({ canvasEl, onObjectSelected, onHover: setHover });
  const render = useDxfRender(modelId, canvas, fitTo);

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
          </div>
        )}
      </aside>
    </div>
  );
}
