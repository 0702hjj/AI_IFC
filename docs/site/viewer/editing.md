# IFC 属性编辑

属性面板即改即存**真改 IFC**（pending → commit 两阶段）。属性 override 旁路已退出编辑路径，仅保留历史数据只读展示。

## 属性面板真改直通

选中构件后，属性面板按 `GET /api/v1/models/{id}/edit/entities/{guid}/editable-schema` 返回的类型化 schema 渲染表单：

- **直接属性**：字符串字段文本输入、int/float 数字输入、bool 复选框、枚举字段（如 `PredefinedType`）下拉合法值——枚举清单取自 ifcopenshell schema 声明；非法枚举值服务端 422 且不破坏模型。
- **pset 属性**：str/int/float/bool 标量属性同类型可编辑；非标量属性不进入表单。
- 保存即 `PUT /api/v1/models/{id}/edit/entities/{guid}`（pending，不落盘），面板出现「有未提交修改」提示；点**提交**走 commit 编排（版本快照 + change log + diff + XKT 重转），完成后前端自动重载。
- **删除构件**：按钮 + 确认 → `DELETE /api/v1/models/{id}/edit/entities/{guid}` 进 pending（开洞/填充、空间包含、类型关联、pset 级联清理），commit 后生效并体现在版本快照中。IfcProject 与空间结构元素（场地/建筑/楼层/空间）拒绝删除（422）。
- 编辑服务不可用时面板降级为只读模式；历史 override 仍以只读标记展示，新编辑不再产生 override。

## override 迁移为真改

历史遗留的 override 可经 `POST /api/v1/models/{id}/overrides/migrate` 回放为真实 IFC 修改：

- 每个实体先 PUT pending，再一次性 commit（`operation=migrate`），生成新的版本快照。
- 成功字段清除 override；失败字段保留 override，并在响应 `failed` 中带原因。
- 有任何成功即触发 XKT 重转。

## 真改编辑流（pending → commit）

真改编辑是两阶段事务：

1. **PUT pending**：把 `fields`（直接属性）与 `psets`（属性集，不存在则创建）应用到内存模型并记为 pending；**不落盘**。先全量校验（含枚举合法值）再应用——任一校验失败则零副作用。
2. **POST commit**：全部 pending 原子落盘（tmp + rename，持每模型锁）→ 生成版本快照 → 追加编辑历史 → 清空 pending。

经浏览器（Go 代理）commit 时，Go server 还会：把 entries 展开写入 change log、用 IfcDiff 补充 diff 字段、把模型置为 `converting` 并排队重转 XKT——完成后前端自动重载。

要点：

- pending 每次变更原子落盘（`models/{id}/pending.json`），edit-service 重启后自动恢复；history 与版本快照不受影响。
- 重复 commit（无 pending）返回 409。
- 多请求并发由每模型一把锁串行化。

接口契约见 [IFC 编辑 API](/reference/edit-api)。
