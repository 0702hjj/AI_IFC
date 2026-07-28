import { useEffect } from "react";
import type { PickResult, Viewer } from "@xeokit/xeokit-sdk";
import { useViewerStore } from "./store";

export function usePicking(viewer: Viewer | null) {
  const setSelected = useViewerStore((s) => s.setSelected);

  useEffect(() => {
    if (!viewer) return;
    const control = viewer.cameraControl;
    const onPicked = (e: PickResult) => {
      if (useViewerStore.getState().tool !== "select") return;
      const entity = e.entity;
      if (entity && entity.isObject) setSelected(String(entity.id));
    };
    const onPickedNothing = () => {
      if (useViewerStore.getState().tool !== "select") return;
      setSelected(null);
    };
    const subPicked = control.on("picked", onPicked);
    const subPickedNothing = control.on("pickedNothing", onPickedNothing);
    return () => {
      control.off(subPicked);
      control.off(subPickedNothing);
    };
  }, [viewer, setSelected]);
}

export function useSelectionHighlight(viewer: Viewer | null) {
  const selectedId = useViewerStore((s) => s.selectedId);

  useEffect(() => {
    if (!viewer) return;
    const scene = viewer.scene;
    for (const id of scene.selectedObjectIds) {
      const obj = scene.objects[id];
      if (obj) obj.selected = false;
    }
    if (selectedId) {
      const obj = scene.objects[selectedId];
      if (obj) obj.selected = true;
    }
  }, [viewer, selectedId]);
}
