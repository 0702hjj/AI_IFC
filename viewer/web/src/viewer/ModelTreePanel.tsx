import { useEffect, useRef } from "react";
import { TreeViewPlugin } from "@xeokit/xeokit-sdk";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import "./tree.css";

interface NodeTitleClickedEvent {
  treeViewNode: { objectId: string };
}

export function ModelTreePanel() {
  const ctx = useViewer();
  const containerRef = useRef<HTMLDivElement>(null);
  const setSelected = useViewerStore((s) => s.setSelected);

  useEffect(() => {
    const container = containerRef.current;
    if (!ctx || !container) return;
    const { viewer } = ctx;
    const treeView = new TreeViewPlugin(viewer, {
      containerElement: container,
      hierarchy: "containment",
      autoExpandDepth: 1,
    });
    const subId = (
      treeView.on as unknown as (
        event: string,
        callback: (e: NodeTitleClickedEvent) => void
      ) => string
    )("nodeTitleClicked", (e) => {
      const objectId = e.treeViewNode.objectId;
      setSelected(objectId);
      viewer.cameraFlight.flyTo({ component: objectId });
    });
    return () => {
      treeView.off(subId);
      treeView.destroy();
    };
  }, [ctx, setSelected]);

  return <div ref={containerRef} className="xeokit-tree-view tree-panel" />;
}
