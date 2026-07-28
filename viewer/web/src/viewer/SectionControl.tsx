import { useEffect, useRef, useState } from "react";
import {
  SectionPlanesPlugin,
  type SectionPlane,
  type Viewer,
} from "@xeokit/xeokit-sdk";
import { useViewer } from "./ViewerContext";

type Axis = "x" | "y" | "z";

const AXIS_INDEX: Record<Axis, number> = { x: 0, y: 1, z: 2 };
const AXIS_DIR: Record<Axis, number[]> = {
  x: [-1, 0, 0],
  y: [0, -1, 0],
  z: [0, 0, -1],
};

export function SectionControl({ enabled }: { enabled: boolean }) {
  const ctx = useViewer();
  if (!ctx) return null;
  return <SectionControlInner viewer={ctx.viewer} enabled={enabled} />;
}

function SectionControlInner({
  viewer,
  enabled,
}: {
  viewer: Viewer;
  enabled: boolean;
}) {
  const pluginRef = useRef<SectionPlanesPlugin | null>(null);
  const planeRef = useRef<SectionPlane | null>(null);
  const [axis, setAxis] = useState<Axis>("y");
  const [value, setValue] = useState(0);

  useEffect(() => {
    const plugin = new SectionPlanesPlugin(viewer, {});
    pluginRef.current = plugin;
    return () => {
      pluginRef.current = null;
      plugin.destroy();
    };
  }, [viewer]);

  useEffect(() => {
    if (!enabled) return;
    const plugin = pluginRef.current;
    if (!plugin) return;
    const aabb = viewer.scene.aabb;
    const center = [
      (aabb[0] + aabb[3]) / 2,
      (aabb[1] + aabb[4]) / 2,
      (aabb[2] + aabb[5]) / 2,
    ];
    const plane = plugin.createSectionPlane({
      pos: center,
      dir: AXIS_DIR[axis],
    });
    planeRef.current = plane;
    setValue(center[AXIS_INDEX[axis]]);
    return () => {
      planeRef.current = null;
      plane.destroy();
    };
  }, [viewer, enabled, axis]);

  const aabb = viewer.scene.aabb;
  const idx = AXIS_INDEX[axis];
  const min = aabb[idx];
  const max = aabb[idx + 3];
  const step = (max - min) / 200 || 0.001;

  const onSlide = (v: number) => {
    setValue(v);
    const plane = planeRef.current;
    if (!plane) return;
    const pos = [
      (aabb[0] + aabb[3]) / 2,
      (aabb[1] + aabb[4]) / 2,
      (aabb[2] + aabb[5]) / 2,
    ];
    pos[idx] = v;
    plane.pos = pos;
  };

  if (!enabled) return null;

  return (
    <div className="section-control">
      <div className="section-axis">
        {(["x", "y", "z"] as Axis[]).map((a) => (
          <button
            key={a}
            type="button"
            className={`toolbar-btn${axis === a ? " active" : ""}`}
            aria-pressed={axis === a}
            onClick={() => setAxis(a)}
          >
            {a.toUpperCase()}
          </button>
        ))}
      </div>
      <input
        type="range"
        className="section-slider"
        aria-label="剖切位置"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onSlide(Number(e.target.value))}
      />
    </div>
  );
}
