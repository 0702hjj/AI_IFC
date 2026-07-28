import { useCallback, useEffect, useRef } from "react";
import {
  DistanceMeasurementsMouseControl,
  DistanceMeasurementsPlugin,
} from "@xeokit/xeokit-sdk";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";

interface MeasurementsRefs {
  plugin: DistanceMeasurementsPlugin;
  control: DistanceMeasurementsMouseControl;
}

export function useMeasurements() {
  const { viewer } = useViewer()!;
  const tool = useViewerStore((s) => s.tool);
  const refs = useRef<MeasurementsRefs | null>(null);

  useEffect(() => {
    const plugin = new DistanceMeasurementsPlugin(viewer, {});
    const control = new DistanceMeasurementsMouseControl(plugin, {
      snapping: true,
    });
    refs.current = { plugin, control };
    return () => {
      refs.current = null;
      control.destroy();
      plugin.destroy();
    };
  }, [viewer]);

  useEffect(() => {
    const control = refs.current?.control;
    if (!control) return;
    if (tool === "measure") control.activate();
    else control.deactivate();
  }, [viewer, tool]);

  const clear = useCallback(() => {
    const r = refs.current;
    if (!r) return;
    const wasActive = tool === "measure";
    if (wasActive) r.control.deactivate();
    r.plugin.clear();
    if (wasActive) r.control.activate();
  }, [tool]);

  return { clear };
}
