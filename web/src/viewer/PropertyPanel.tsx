// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// PropertyPanel：只读属性展示（L1 直改端点已 410 退役，编辑统一走 script-as-source）。
// 选中构件可「定位脚本」：guid → locate → DesignPanel 脚本编辑器跳行；
// miss / 请求失败降级为非阻断只读提示（契约违规属 bug，不弹错误）。

import { useEffect, useState } from "react";
import type { MetaObject } from "@xeokit/xeokit-sdk";
import { locateScript } from "@/api/client";
import { useViewer } from "./ViewerContext";
import { useViewerStore } from "./store";
import { applyOverrides } from "./overrides";
import "./PropertyPanel.css";

export function PropertyPanel({ modelId }: { modelId: string }) {
  const ctx = useViewer();
  const selectedId = useViewerStore((s) => s.selectedId);
  const overrides = useViewerStore((s) => s.overrides);
  const loadOverrides = useViewerStore((s) => s.loadOverrides);
  const requestScriptJump = useViewerStore((s) => s.requestScriptJump);

  const [query, setQuery] = useState("");
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);

  useEffect(() => {
    loadOverrides(modelId).catch(() => {});
  }, [modelId, loadOverrides]);

  useEffect(() => {
    setToggled({});
    setQuery("");
    setNotice(null);
    setLocating(false);
  }, [modelId, selectedId]);

  const metaModel = ctx?.metaModel ?? null;
  const metaObjects = metaModel
    ? (metaModel.metaObjects as unknown as Record<string, MetaObject>)
    : null;
  const metaObject =
    selectedId && metaObjects ? (metaObjects[selectedId] ?? null) : null;

  const entity = metaObject
    ? applyOverrides(
        metaObject as unknown as Parameters<typeof applyOverrides>[0],
        (selectedId && overrides[selectedId]) || {}
      )
    : null;

  const q = query.trim().toLowerCase();
  const searching = q !== "";

  const isOpen = (id: string, index: number) =>
    searching || (id in toggled ? toggled[id] : index === 0);

  const matches = (name: string, value: unknown) =>
    name.toLowerCase().includes(q) ||
    (value != null && String(value).toLowerCase().includes(q));

  const locate = () => {
    if (!selectedId || locating) return;
    setLocating(true);
    setNotice(null);
    locateScript(modelId, selectedId)
      .then((res) => {
        if (res.found && res.line != null) {
          requestScriptJump({ line: res.line, origin: res.origin, paramsKeys: res.paramsKeys });
          setNotice(
            res.origin === "traced"
              ? `已定位到脚本第 ${res.line} 行；该构件由运行期逻辑生成，请在脚本编辑器中手动修改`
              : `已定位到脚本第 ${res.line} 行`
          );
        } else if (res.stale) {
          setNotice("脚本有未运行的修改，调用点定位已过期；请先运行脚本，属性只读");
        } else {
          setNotice("该构件没有脚本调用点（非脚本生成），属性只读；可在脚本编辑器中手动修改");
        }
      })
      .catch(() => setNotice("脚本定位不可用，属性只读"))
      .finally(() => setLocating(false));
  };

  return (
    <aside className="property-panel">
      <h2>属性</h2>
      {!entity && <p className="property-empty">点击构件查看属性</p>}
      {entity && (
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
            <dd>{entity.name || "（未命名）"}</dd>
            <dt>类型</dt>
            <dd>{entity.type}</dd>
          </dl>
          <button
            type="button"
            className="locate-script-btn"
            disabled={locating}
            onClick={locate}
          >
            {locating ? "定位中…" : "定位脚本"}
          </button>
          {notice && <p className="property-notice">{notice}</p>}
          {entity.propertySets.map((pset, index) => {
            const props = (pset.properties ?? []).filter(
              (p) => !searching || matches(p.name, p.value) || pset.name.toLowerCase().includes(q)
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
                      {props.map((prop, i) => {
                        const overridden =
                          (selectedId && overrides[selectedId]?.[prop.name]) !== undefined;
                        return (
                          <tr
                            key={`${prop.name}-${i}`}
                            className={overridden ? "overridden" : ""}
                          >
                            <td className="property-name">
                              {overridden && (
                                <span className="override-dot" title="历史 override" />
                              )}
                              {prop.name}
                            </td>
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
                        );
                      })}
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
