import { Link, useParams } from "react-router-dom";
import { ViewerProvider } from "@/viewer/ViewerContext";
import { ModelTreePanel } from "@/viewer/ModelTreePanel";
import { PropertyPanel } from "@/viewer/PropertyPanel";
import "./ViewerPage.css";

export default function ViewerPage() {
  const { id } = useParams<{ id: string }>();

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
      <ViewerProvider modelId={id}>
        <ModelTreePanel />
        <PropertyPanel />
      </ViewerProvider>
    </div>
  );
}
