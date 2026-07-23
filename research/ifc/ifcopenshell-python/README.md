# ifcopenshell-python 官方文档离线镜像

- 来源:<https://docs.ifcopenshell.org/ifcopenshell-python.html>(IfcOpenShell 0.8.5 文档,Sphinx/Furo 生成)
- 扒取日期:2026-07-23
- 方式:`wget --recursive --page-requisites --convert-links`,白名单限定 `ifcopenshell-python/` 子树 + 共享静态资源,图片链接已改写为本地 `_images/` 相对路径

## 页面清单(10 页)

| 文件 | 内容 |
|---|---|
| `ifcopenshell-python.html` | 章节落地页(目录) |
| `installation.html` | 安装 |
| `hello_world.html` | Hello World 入门 |
| `geometry_creation.html` | **几何创建完整教程**(skill MODELING_WORKFLOWS 的主要素材) |
| `geometry_processing.html` | 几何处理/网格/属性提取 |
| `geometry_tree.html` | 几何树遍历 |
| `code_examples.html` | 代码示例集 |
| `schema_querying.html` | schema 内省查询 |
| `selector_syntax.html` | 选择器语法(接地/查询用) |
| `validation.html` | IFC 校验(validate) |

## 用途

任务线 2 构建 `AI_IFC/skills/ai_ifc/` 时,`references/MODELING_WORKFLOWS.md` 优先以本镜像的
`geometry_creation.html` 为素材(与源码内 `geometry_creation.rst` 互为印证),离线可读。

注意:本站该章节的真实 URL 是 `ifcopenshell-python.html` 落地页 + `ifcopenshell-python/` 子目录,
`/ifcopenshell-python/`(带尾斜杠的目录索引)本身返回 404。
