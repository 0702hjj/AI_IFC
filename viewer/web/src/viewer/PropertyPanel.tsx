import { useEffect, useState } from "react";
import type { MetaObject } from "@xeokit/xeokit-sdk";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import "./PropertyPanel.css";

interface Prop {
  name: string;
  value: unknown;
  type?: string;
}

interface Pset {
  id: string;
  name: string;
  properties?: Prop[];
}

export function PropertyPanel() {
  const ctx = useViewer();
  const selectedId = useViewerStore((s) => s.selectedId);
  const [query, setQuery] = useState("");
  const [toggled, setToggled] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setToggled({});
    setQuery("");
  }, [selectedId]);

  const metaModel = ctx?.metaModel ?? null;
  const metaObjects = metaModel
    ? (metaModel.metaObjects as unknown as Record<string, MetaObject>)
    : null;
  const metaObject =
    selectedId && metaObjects ? (metaObjects[selectedId] ?? null) : null;

  const psets = (metaObject?.propertySets ?? []) as unknown as Pset[];
  const q = query.trim().toLowerCase();
  const searching = q !== "";

  const propMatches = (p: Prop) =>
    p.name.toLowerCase().includes(q) ||
    (p.value != null && String(p.value).toLowerCase().includes(q));

  const isOpen = (id: string, index: number) =>
    searching || (id in toggled ? toggled[id] : index === 0);

  return (
    <aside className="property-panel">
      <h2>属性</h2>
      {!metaObject && <p className="property-empty">点击构件查看属性</p>}
      {metaObject && (
        <div className="property-body">
          <input
            className="property-search"
            type="search"
            placeholder="搜索属性"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <dl className="property-summary">
            <dt>名称</dt>
            <dd>{metaObject.name || "（未命名）"}</dd>
            <dt>类型</dt>
            <dd>{metaObject.type}</dd>
          </dl>
          {psets.map((pset, index) => {
            const props = (pset.properties ?? []).filter(
              (p) => !searching || propMatches(p) || pset.name.toLowerCase().includes(q)
            );
            if (searching && props.length === 0) return null;
            return (
              <section key={pset.id} className="property-set">
                <h3
                  className="property-set-title"
                  onClick={() =>
                    setToggled((prev) => ({
                      ...prev,
                      [pset.id]: !isOpen(pset.id, index),
                    }))
                  }
                >
                  {isOpen(pset.id, index) ? "▾ " : "▸ "}
                  <span>{pset.name}</span>
                </h3>
                {isOpen(pset.id, index) && (
                  <table>
                    <tbody>
                      {props.map((prop, i) => (
                        <tr key={`${prop.name}-${i}`}>
                          <td className="property-name">{prop.name}</td>
                          <td className="property-value">
                            {prop.value == null ? "" : String(prop.value)}
                          </td>
                          <td className="property-copy">
                            <button
                              type="button"
                              className="property-copy-btn"
                              aria-label={`复制 ${prop.name}`}
                              onClick={() =>
                                navigator.clipboard.writeText(
                                  `${prop.name}: ${prop.value == null ? "" : String(prop.value)}`
                                )
                              }
                            >
                              复制
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            );
          })}
        </div>
      )}
    </aside>
  );
}
