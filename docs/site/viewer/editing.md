# IFC 属性编辑

属性编辑分两阶段：**override（显示层）→ 真改（写回 IFC）**。

## 第一阶段：属性 override

属性面板中白名单字段可编辑，白名单恰好为：

`Name`、`Description`、`Classification`、`FireRating`、`Comments`

- 编辑保存后作为 override 覆盖显示值，**不修改 IFC 本体**，被覆盖字段带修改标记。
- 空字符串 = 清除该字段的 override。
- 每次修改逐字段写入一条 change log（`operation=update`，`author=local-user`，`provenance={source:"UI"}`），可在修改历史 tab 查看。
- 相关 API：`GET /api/v1/models/{id}/overrides`、`PUT /api/v1/models/{id}/entities/{entityId}/properties`、`GET /api/v1/models/{id}/changes`。

## 第二阶段：override 迁移为真改

`POST /api/v1/models/{id}/overrides/migrate` 把当前全部 override 回放为真实 IFC 修改：

- 每个实体先 PUT pending，再一次性 commit（`operation=migrate`），生成新的版本快照。
- 成功字段清除 override；失败字段保留 override，并在响应 `failed` 中带原因。
- 有任何成功即触发 XKT 重转。

## 真改编辑流（pending → commit）

真改编辑是两阶段事务：

1. **PUT pending**：把 `fields`（直接属性）与 `psets`（属性集，不存在则创建）应用到内存模型并记为 pending；**不落盘**。先全量校验再应用——任一校验失败则零副作用。
2. **POST commit**：全部 pending 原子落盘（tmp + rename，持每模型锁）→ 生成版本快照 → 追加编辑历史 → 清空 pending。

经浏览器（Go 代理）commit 时，Go server 还会：把 entries 展开写入 change log、用 IfcDiff 补充 diff 字段、把模型置为 `converting` 并排队重转 XKT——完成后前端自动重载。

要点：

- pending 每次变更原子落盘（`models/{id}/pending.json`），edit-service 重启后自动恢复；history 与版本快照不受影响。
- 重复 commit（无 pending）返回 409。
- 多请求并发由每模型一把锁串行化。

接口契约见 [IFC 编辑 API](/reference/edit-api)。
