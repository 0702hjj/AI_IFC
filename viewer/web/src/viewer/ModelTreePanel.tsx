import { useEffect, useMemo, useState } from "react";
import type { MetaObject } from "@xeokit/xeokit-sdk";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import { buildTree, filterTree, typeCounts, type MetaObjectLite, type TreeNode } from "./tree-utils";
import "./tree.css";

export function ModelTreePanel() {
  const ctx = useViewer();
  const selectedId = useViewerStore((s) => s.selectedId);
  const setSelected = useViewerStore((s) => s.setSelected);
  const hiddenIds = useViewerStore((s) => s.hiddenIds);
  const toggleHidden = useViewerStore((s) => s.toggleHidden);

  const [query, setQuery] = useState("");
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const objects = useMemo<MetaObjectLite[]>(() => {
    if (!ctx?.metaModel) return [];
    const rec = ctx.metaModel.metaObjects as unknown as Record<string, MetaObject>;
    return Object.values(rec).map((o) => ({
      id: o.id,
      name: o.name ?? "",
      type: o.type,
      parent: (o as unknown as { parent?: string | null }).parent ?? null,
    }));
  }, [ctx]);

  const tree = useMemo(() => buildTree(objects), [objects]);
  const counts = useMemo(() => typeCounts(objects), [objects]);
  const filtering = query.trim() !== "" || activeTypes.size > 0;
  const visible = useMemo(
    () => (filtering ? filterTree(tree, query, activeTypes) : tree),
    [tree, query, activeTypes, filtering]
  );

  useEffect(() => {
    const ids: string[] = [];
    const walk = (nodes: TreeNode[]) => {
      for (const n of nodes) {
        ids.push(n.id);
        walk(n.children);
      }
    };
    walk(tree);
    setExpanded(new Set(ids));
  }, [tree]);

  if (!ctx) return null;
  const hidden = new Set(hiddenIds);

  const toggleType = (t: string) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  const renderNode = (node: TreeNode, depth: number) => {
    const isOpen = filtering || expanded.has(node.id);
    return (
      <li key={node.id} className={hidden.has(node.id) ? "tree-hidden" : ""}>
        <div className="tree-row" style={{ paddingLeft: depth * 16 }}>
          {node.children.length > 0 && !filtering ? (
            <button
              type="button"
              className="tree-toggle"
              aria-label={isOpen ? "折叠" : "展开"}
              onClick={() =>
                setExpanded((prev) => {
                  const next = new Set(prev);
                  if (next.has(node.id)) next.delete(node.id);
                  else next.add(node.id);
                  return next;
                })
              }
            >
              {isOpen ? "▾" : "▸"}
            </button>
          ) : (
            <span className="tree-toggle-placeholder" />
          )}
          <button
            type="button"
            className="tree-hide-btn"
            aria-label={hidden.has(node.id) ? "显示" : "隐藏"}
            onClick={() => toggleHidden(node.id)}
          >
            {hidden.has(node.id) ? "🚫" : "👁"}
          </button>
          <span
            className={`tree-title${selectedId === node.id ? " selected" : ""}`}
            onClick={() => {
              setSelected(node.id);
              ctx.viewer.cameraFlight.flyTo({ component: node.id });
            }}
          >
            {node.name || node.id}
            <em className="tree-type">{node.type}</em>
          </span>
        </div>
        {isOpen && node.children.length > 0 && (
          <ul>{node.children.map((c) => renderNode(c, depth + 1))}</ul>
        )}
      </li>
    );
  };

  return (
    <aside className="tree-panel">
      <input
        className="tree-search"
        type="search"
        placeholder="搜索名称或类型"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <details className="tree-type-filter">
        <summary>类型过滤{activeTypes.size > 0 ? `（${activeTypes.size}）` : ""}</summary>
        <div className="tree-type-list">
          {counts.map(([t, n]) => (
            <label key={t}>
              <input
                type="checkbox"
                checked={activeTypes.has(t)}
                onChange={() => toggleType(t)}
                aria-label={t}
              />
              {t}（{n}）
            </label>
          ))}
        </div>
      </details>
      <ul className="tree-root">{visible.map((n) => renderNode(n, 0))}</ul>
    </aside>
  );
}
