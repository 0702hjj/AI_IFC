import { useEffect, useState } from "react";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import { locateIssue } from "./locateIssue";
import {
  aabbCenter,
  projectToCanvas,
  type PinPosition,
} from "./issuePinProjection";
import "./IssuePins.css";

interface SceneObjectLike {
  visible?: boolean;
  aabb?: number[];
}

function samePositions(
  a: Record<string, PinPosition | null>,
  b: Record<string, PinPosition | null>
) {
  const aKeys = Object.keys(a);
  const bKeys = Object.keys(b);
  if (aKeys.length !== bKeys.length) return false;
  return aKeys.every((k) => {
    const pa = a[k];
    const pb = b[k];
    if (pa === null || pb === null) return pa === pb;
    return pa.x === pb.x && pa.y === pb.y;
  });
}

export function IssuePins() {
  const ctx = useViewer();
  const issues = useViewerStore((s) => s.issues);
  const selectedIssueId = useViewerStore((s) => s.selectedIssueId);
  const [positions, setPositions] = useState<Record<string, PinPosition | null>>(
    {}
  );

  useEffect(() => {
    if (!ctx) return;
    const viewer = ctx.viewer;
    const scene = viewer.scene;
    const update = () => {
      const canvas = (
        scene.canvas as unknown as {
          canvas: { offsetWidth: number; offsetHeight: number };
        }
      ).canvas;
      const view = viewer.camera.viewMatrix;
      const proj = viewer.camera.projMatrix;
      const next: Record<string, PinPosition | null> = {};
      for (const iss of issues) {
        if (!iss.entityId) continue;
        const obj = (scene.objects as unknown as Record<string, SceneObjectLike>)[
          iss.entityId
        ];
        if (!obj || obj.visible === false || !obj.aabb) {
          next[iss.id] = null;
          continue;
        }
        next[iss.id] = projectToCanvas(
          aabbCenter(obj.aabb),
          view,
          proj,
          canvas.offsetWidth,
          canvas.offsetHeight
        );
      }
      setPositions((prev) => (samePositions(prev, next) ? prev : next));
    };
    const sub = scene.on("tick", update);
    update();
    return () => {
      scene.off(sub);
    };
  }, [ctx, issues]);

  if (!ctx) return null;

  return (
    <div className="issue-pins-layer">
      {issues
        .filter((iss) => iss.entityId)
        .map((iss) => {
          const pos = positions[iss.id];
          if (!pos) return null;
          return (
            <button
              key={iss.id}
              type="button"
              className={`issue-pin issue-status-${iss.status}${
                selectedIssueId === iss.id ? " active" : ""
              }`}
              style={{ left: pos.x, top: pos.y }}
              title={iss.title}
              aria-label={`Issue: ${iss.title}`}
              onClick={() => locateIssue(ctx, iss)}
            />
          );
        })}
    </div>
  );
}
