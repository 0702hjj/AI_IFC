# Issue 与 3D Pin

## 创建 Issue

1. 选中构件。
2. 在底部 Issue 面板点「新建 Issue」，填写标题（必填）与评论。
3. 创建时自动携带当前相机视角与画布截图；Issue 出现在列表中，3D 钉覆盖在构件上。

## 状态流转

`open` → `checking` → `resolved`，可在列表中切换。Issue id 格式 `i_` + 12 位小写 hex。

## 3D Pin

- 每个带 entityId 的 Issue 对应一个 HTML 钉，实时投影到构件位置；构件不可见或钉在屏幕外时自动隐藏。
- 点击钉或列表条目：恢复创建时的相机视角、选中构件并高亮该 Issue。

## 修改历史

底部面板提供「Issues / 修改历史」双 tab。修改历史展示 change log（时间、实体、字段、old → new、author），按时间倒序；直改链路退役后属性面板已只读，此处主要承载历史记录回看。

## 接口契约

Issue CRUD 与截图静态服务见 [Viewer REST API](/reference/rest-api)。
