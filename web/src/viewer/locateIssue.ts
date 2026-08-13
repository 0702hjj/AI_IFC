// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import type { Issue } from "@/api/types";
import type { ViewerContextValue } from "./ViewerContext";
import { useViewerStore } from "./store";

export function locateIssue(ctx: ViewerContextValue, iss: Issue) {
  ctx.viewer.cameraFlight.flyTo({
    eye: iss.camera.eye,
    look: iss.camera.look,
    up: iss.camera.up,
  });
  const objects = ctx.viewer.scene.objects as unknown as Record<string, unknown>;
  if (objects[iss.entityId]) useViewerStore.getState().setSelected(iss.entityId);
  useViewerStore.getState().setSelectedIssue(iss.id);
}
