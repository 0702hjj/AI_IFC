import type { MetaObject } from "@xeokit/xeokit-sdk";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import "./PropertyPanel.css";

export function PropertyPanel() {
  const ctx = useViewer();
  const selectedId = useViewerStore((s) => s.selectedId);

  const metaModel = ctx?.metaModel ?? null;
  const metaObjects = metaModel
    ? (metaModel.metaObjects as unknown as Record<string, MetaObject>)
    : null;
  const metaObject =
    selectedId && metaObjects ? (metaObjects[selectedId] ?? null) : null;

  return (
    <aside className="property-panel">
      <h2>属性</h2>
      {!metaObject && <p className="property-empty">点击构件查看属性</p>}
      {metaObject && (
        <div className="property-body">
          <dl className="property-summary">
            <dt>名称</dt>
            <dd>{metaObject.name || "（未命名）"}</dd>
            <dt>类型</dt>
            <dd>{metaObject.type}</dd>
          </dl>
          {(metaObject.propertySets ?? []).map((pset) => (
            <section key={pset.id} className="property-set">
              <h3>{pset.name}</h3>
              <table>
                <tbody>
                  {(pset.properties ?? []).map((prop, i) => (
                    <tr key={`${prop.name}-${i}`}>
                      <td className="property-name">{prop.name}</td>
                      <td className="property-value">
                        {prop.value == null ? "" : String(prop.value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      )}
    </aside>
  );
}
