# 模型库与模型上传

模型库页是平台的入口：上传、列表、状态跟踪、重试、下载与删除。

## 上传

- 拖入或选择 `.ifc` 文件（≤200MB）；非 `.ifc` 扩展名与超限文件会被前端拦截，后端同样校验。
- 上传后模型进入 `converting` 状态，server 排队调用 converter 生成 XKT 与元数据；页面以 2 秒间隔轮询直到所有模型脱离 `converting`。
- 状态取值：`converting`（转换中）、`ready`（可用）、`failed`（转换失败，可重试）。

## 列表操作

- **重试**：`failed` 模型可重新入队转换。
- **下载**：下载原始 IFC 文件（未修改的上传版本）。
- **删除**：级联删除 IFC、XKT、元数据、状态文件以及该模型的 issues / changes / overrides。

## 相关 API

上传、列表、重试、下载、删除的接口契约见 [Viewer REST API](/reference/rest-api)。
