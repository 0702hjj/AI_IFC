// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";
import {
  NavCubePlugin,
  Viewer,
  XKTLoaderPlugin,
  type Entity,
  type MetaModel,
} from "@xeokit/xeokit-sdk";
import { modelAssetUrl } from "@/api/client";
import { IssuePins } from "./IssuePins";
import { usePicking, useSelectionHighlight } from "./usePicking";
import { useVisibility } from "./useVisibility";

export interface ViewerContextValue {
  viewer: Viewer;
  sceneModel: Entity;
  metaModel: MetaModel | null;
}

const ViewerContext = createContext<ViewerContextValue | null>(null);

export function useViewer() {
  return useContext(ViewerContext);
}

export function ViewerProvider({
  modelId,
  children,
}: {
  modelId: string;
  children?: ReactNode;
}) {
  const [ctx, setCtx] = useState<ViewerContextValue | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const viewer = new Viewer({
      canvasId: "xeokit-canvas",
      transparent: true,
      preserveDrawingBuffer: true,
    });
    new NavCubePlugin(viewer, { canvasId: "navcube-canvas", visible: true });
    const xktLoader = new XKTLoaderPlugin(viewer);
    const sceneModel = xktLoader.load({
      id: "model",
      src: modelAssetUrl(modelId, "model.xkt"),
      metaModelSrc: modelAssetUrl(modelId, "metadata.json"),
      edges: true,
    });
    sceneModel.on("loaded", () => {
      viewer.cameraFlight.flyTo(sceneModel);
      setCtx({
        viewer,
        sceneModel: sceneModel as unknown as Entity,
        metaModel: viewer.metaScene.metaModels[sceneModel.id] ?? null,
      });
    });
    sceneModel.on("error", (e: unknown) => {
      setError(e instanceof Error ? e.message : String(e));
    });
    return () => {
      viewer.destroy();
    };
  }, [modelId]);

  usePicking(ctx?.viewer ?? null);
  useSelectionHighlight(ctx?.viewer ?? null);
  useVisibility(ctx);

  return (
    <ViewerContext.Provider value={ctx}>
      <div className="viewer-canvas-wrap">
        <canvas id="xeokit-canvas" className="viewer-canvas" />
        <canvas id="navcube-canvas" className="navcube-canvas" />
        {ctx && <IssuePins />}
        {!ctx && !error && <div className="viewer-status">模型加载中…</div>}
        {error && (
          <div className="viewer-status viewer-error">
            <p>模型加载失败：{error}</p>
            <Link to="/">返回模型库</Link>
          </div>
        )}
      </div>
      {ctx && children}
    </ViewerContext.Provider>
  );
}
