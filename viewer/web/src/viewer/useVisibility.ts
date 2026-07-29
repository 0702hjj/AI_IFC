import { useEffect } from "react";
import { useViewerStore } from "./store";
import type { ViewerContextValue } from "./ViewerContext";

export function useVisibility(ctx: ViewerContextValue | null) {
  const hiddenIds = useViewerStore((s) => s.hiddenIds);
  const isolateId = useViewerStore((s) => s.isolateId);
  const xray = useViewerStore((s) => s.xray);

  useEffect(() => {
    if (!ctx) return;
    const objects = ctx.viewer.scene.objects as unknown as Record<
      string,
      { visible: boolean; xrayed: boolean }
    >;
    const hidden = new Set(hiddenIds);
    for (const id of Object.keys(objects)) {
      const obj = objects[id];
      obj.visible = !hidden.has(id) && (isolateId === null || id === isolateId);
      obj.xrayed = xray && id !== isolateId;
    }
  }, [ctx, hiddenIds, isolateId, xray]);
}
