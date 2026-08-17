// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// web-ifc IFC 查看器组件：加载编排（下载→openIfcApi→几何→场景→树）+
// 树/属性侧栏 + 拾取/树点击的选中联动（store.selectedId ↔ expressID 字符串）。
// 分层：ifcLoader（纯提取）→ ifcScene（three 挂载）→ 本组件（React 桥接）。
// 移植说明：文案集中在本文件顶部常量，改 i18n 时单点替换。

import { useCallback, useEffect, useRef, useState } from "react";
import { downloadIfcBytes } from "@/api/client";
import { useViewerStore } from "@/viewer/store";
import {
  openIfcApi,
  loadIfcGeometry,
  loadSpatialTree,
  loadElementProps,
  type OpenedIfcModel,
  type SpatialTreeNode,
  type PropertyRow,
} from "./ifcLoader";
import { mountIfcScene, type IfcSceneHandle } from "./ifcScene";
import "./IfcLiteViewer.css";

// --- 文案（集中便于 i18n 化移植） ---
const TEXT = {
  loading: "模型加载中…",
  loadFailed: "模型加载失败",
  treeTitle: "空间结构",
  propsTitle: "构件属性",
  propsEmpty: "该节点无属性",
  backToList: "返回模型库",
};

export default function IfcLiteViewer({ modelId }: { modelId: string }) {
  const [canvasEl, setCanvasEl] = useState<HTMLCanvasElement | null>(null);
  const [tree, setTree] = useState<SpatialTreeNode | null>(null);
  const [props, setProps] = useState<PropertyRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selectedId = useViewerStore((s) => s.selectedId);
  const setSelected = useViewerStore((s) => s.setSelected);

  // 打开的模型与场景句柄跨渲染保留；卸载时统一清理
  const openedRef = useRef<OpenedIfcModel | null>(null);
  const sceneRef = useRef<IfcSceneHandle | null>(null);

  // 加载编排：modelId 变化即整链重来（ViewerPage reloadKey 已保证重挂载）。
  // 场景挂在下载成功之后——失败路径不创建 WebGL 资源。
  useEffect(() => {
    if (!canvasEl) return;
    let cancelled = false;
    setError(null);
    setTree(null);
    setProps(null);

    (async () => {
      try {
        const data = await downloadIfcBytes(modelId);
        if (cancelled) return;
        const scene = mountIfcScene(canvasEl);
        sceneRef.current = scene;
        const opened = await openIfcApi(data);
        if (cancelled) {
          opened.close();
          return;
        }
        openedRef.current = opened;
        for (const mesh of loadIfcGeometry(opened.api, opened.modelID)) {
          scene.addMesh(mesh);
        }
        scene.fitToBoundingBox();
        const spatial = await loadSpatialTree(opened.api, opened.modelID);
        if (cancelled) return;
        setTree(spatial);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();

    return () => {
      cancelled = true;
      openedRef.current?.close();
      openedRef.current = null;
      sceneRef.current?.dispose();
      sceneRef.current = null;
    };
  }, [canvasEl, modelId]);

  // 选中 → 属性面板（选中也来自树点击，同一管路加载属性行）
  useEffect(() => {
    const opened = openedRef.current;
    if (!opened || selectedId == null) {
      setProps(null);
      return;
    }
    let cancelled = false;
    loadElementProps(opened.api, opened.modelID, Number(selectedId))
      .then((rows) => {
        if (!cancelled) setProps(rows);
      })
      .catch(() => {
        if (!cancelled) setProps(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, tree]);

  // store 选中 → 场景高亮（拾取点击先经 setSelected 统一）
  useEffect(() => {
    sceneRef.current?.setSelection(selectedId == null ? null : Number(selectedId));
  }, [selectedId, tree]);

  const onCanvasClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const id = sceneRef.current?.pick(e.clientX, e.clientY) ?? null;
      setSelected(id == null ? null : String(id));
    },
    [setSelected]
  );

  return (
    <div className="ifc-lite-viewer">
      <div className="ifc-lite-canvas-wrap">
        <canvas
          ref={setCanvasEl}
          data-testid="ifc-canvas"
          className="ifc-lite-canvas"
          onClick={onCanvasClick}
        />
        {!tree && !error && <div className="ifc-lite-status">{TEXT.loading}</div>}
        {error && (
          <div className="ifc-lite-status ifc-lite-error">
            <p>
              {TEXT.loadFailed}：{error}
            </p>
            <a href="#/" className="ifc-lite-back">
              {TEXT.backToList}
            </a>
          </div>
        )}
      </div>
      <aside className="ifc-lite-side">
        <div className="ifc-lite-tree" data-testid="ifc-tree">
          <h3>{TEXT.treeTitle}</h3>
          {tree && <TreeNode node={tree} onSelect={(id) => setSelected(String(id))} />}
        </div>
        <div className="ifc-lite-props" data-testid="ifc-props">
          <h3>{TEXT.propsTitle}</h3>
          {selectedId == null ? (
            <p className="ifc-lite-props-empty">{TEXT.propsEmpty}</p>
          ) : props == null || props.length === 0 ? (
            <p className="ifc-lite-props-empty">{TEXT.propsEmpty}</p>
          ) : (
            <dl>
              {props.map((row) => (
                <div key={row.label} className="ifc-lite-prop-row">
                  <dt>{row.label}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </aside>
    </div>
  );
}

function TreeNode({
  node,
  onSelect,
}: {
  node: SpatialTreeNode;
  onSelect: (expressID: number) => void;
}) {
  return (
    <ul className="ifc-lite-tree-list">
      <li>
        <button
          type="button"
          className="ifc-lite-tree-node"
          onClick={() => onSelect(node.expressID)}
        >
          {node.name}
        </button>
        {node.children.length > 0 &&
          node.children.map((c) => <TreeNode key={c.expressID} node={c} onSelect={onSelect} />)}
      </li>
    </ul>
  );
}
