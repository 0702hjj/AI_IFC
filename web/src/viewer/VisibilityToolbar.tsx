// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { useViewerStore } from "./store";

export function VisibilityToolbar() {
  const selectedId = useViewerStore((s) => s.selectedId);
  const hiddenIds = useViewerStore((s) => s.hiddenIds);
  const isolateId = useViewerStore((s) => s.isolateId);
  const xray = useViewerStore((s) => s.xray);
  const toggleHidden = useViewerStore((s) => s.toggleHidden);
  const isolate = useViewerStore((s) => s.isolate);
  const setXray = useViewerStore((s) => s.setXray);
  const resetVisibility = useViewerStore((s) => s.resetVisibility);

  const dirty = hiddenIds.length > 0 || isolateId !== null || xray;

  return (
    <div className="visibility-toolbar" role="toolbar" aria-label="可见性工具栏">
      <button
        type="button"
        className="toolbar-btn"
        disabled={!selectedId}
        onClick={() => selectedId && toggleHidden(selectedId)}
      >
        隐藏选中
      </button>
      <button
        type="button"
        className={`toolbar-btn${isolateId ? " active" : ""}`}
        aria-pressed={isolateId !== null}
        disabled={!selectedId && !isolateId}
        onClick={() => isolate(isolateId ? null : selectedId)}
      >
        隔离
      </button>
      <button
        type="button"
        className={`toolbar-btn${xray ? " active" : ""}`}
        aria-pressed={xray}
        onClick={() => setXray(!xray)}
      >
        X-Ray
      </button>
      <button
        type="button"
        className="toolbar-btn"
        disabled={!dirty}
        onClick={resetVisibility}
      >
        重置可见性
      </button>
    </div>
  );
}
