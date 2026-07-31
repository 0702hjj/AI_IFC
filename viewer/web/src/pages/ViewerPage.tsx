import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchModel } from "@/api/client";
import type { ModelInfo } from "@/api/types";
import { ViewerProvider } from "@/viewer/ViewerContext";
import { Toolbar } from "@/viewer/Toolbar";
import { ModelTreePanel } from "@/viewer/ModelTreePanel";
import { PropertyPanel } from "@/viewer/PropertyPanel";
import { IssuePanel } from "@/viewer/IssuePanel";
import { DiffPanel } from "@/viewer/DiffPanel";
import "./ViewerPage.css";

export default function ViewerPage() {
  const { id } = useParams<{ id: string }>();
  const [reloadKey, setReloadKey] = useState(0);
  const [status, setStatus] = useState<ModelInfo["status"] | null>(null);
  const prevStatus = useRef<ModelInfo["status"] | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const check = () =>
      fetchModel(id)
        .then((m) => {
          if (!cancelled) setStatus(m.status);
        })
        .catch(() => {});
    check();
    const timer = setInterval(check, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [id]);

  useEffect(() => {
    if (prevStatus.current === "converting" && status === "ready") {
      setReloadKey((k) => k + 1);
    }
    prevStatus.current = status;
  }, [status]);

  if (!id) {
    return (
      <div className="viewer-page">
        <div className="viewer-status viewer-error">
          <p>缺少模型 ID</p>
          <Link to="/">返回模型库</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="viewer-page">
      <ViewerProvider key={reloadKey} modelId={id}>
        <Toolbar id={id} />
        <ModelTreePanel />
        <PropertyPanel modelId={id} />
        <IssuePanel modelId={id} />
        <DiffPanel modelId={id} />
      </ViewerProvider>
    </div>
  );
}
