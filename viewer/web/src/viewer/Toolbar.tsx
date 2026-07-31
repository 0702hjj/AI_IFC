import { useState } from "react";
import { downloadUrl } from "@/api/client";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import { useMeasurements } from "./useMeasurements";
import { SectionControl } from "./SectionControl";
import { VisibilityToolbar } from "./VisibilityToolbar";
import "./Toolbar.css";

export function Toolbar({ id }: { id: string }) {
  const ctx = useViewer();
  if (!ctx) return null;
  return <ToolbarInner id={id} />;
}

function ToolbarInner({ id }: { id: string }) {
  const { viewer, sceneModel } = useViewer()!;
  const tool = useViewerStore((s) => s.tool);
  const setTool = useViewerStore((s) => s.setTool);
  const diffOpen = useViewerStore((s) => s.diffOpen);
  const setDiffOpen = useViewerStore((s) => s.setDiffOpen);
  const { clear } = useMeasurements();
  const [sectionEnabled, setSectionEnabled] = useState(false);

  const measuring = tool === "measure";

  return (
    <div className="toolbar-wrap">
      <div className="toolbar" role="toolbar" aria-label="查看器工具栏">
        <button
          type="button"
          className="toolbar-btn"
          onClick={() => viewer.cameraFlight.flyTo(sceneModel)}
        >
          复位视角
        </button>
        <button
          type="button"
          className={`toolbar-btn${sectionEnabled ? " active" : ""}`}
          aria-pressed={sectionEnabled}
          onClick={() => setSectionEnabled((v) => !v)}
        >
          剖切
        </button>
        <button
          type="button"
          className={`toolbar-btn${measuring ? " active" : ""}`}
          aria-pressed={measuring}
          onClick={() => setTool(measuring ? "select" : "measure")}
        >
          测量
        </button>
        <button type="button" className="toolbar-btn" onClick={clear}>
          清除测量
        </button>
        <button
          type="button"
          className={`toolbar-btn${diffOpen ? " active" : ""}`}
          aria-pressed={diffOpen}
          onClick={() => setDiffOpen(!diffOpen)}
        >
          Diff
        </button>
        <VisibilityToolbar />
        <a className="toolbar-btn toolbar-link" href={downloadUrl(id)} download>
          下载 IFC
        </a>
      </div>
      <SectionControl enabled={sectionEnabled} />
    </div>
  );
}
