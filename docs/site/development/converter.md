# IFC Converter

`viewer/converter/`：Node CLI，基于 web-ifc + xeokit-convert，把 IFC 转为 XKT 几何与语义元数据，由 server 以子进程方式调用，无需常驻。

## 用法

```bash
node convert.js <input.ifc> <outDir>
```

产出：

- `model.xkt`：二进制几何。
- `metadata.json`：xeokit 标准元模型（空间结构树 + 属性集）。

成功时 stdout 末行输出 `{"ok":true,...}`；参数缺失退出码 2，转换失败退出码 1（stderr 报错）。

## 语义提取

- `lib/metadata.js` 用 web-ifc 遍历空间结构；`metaObject id = IFC GlobalId`（fallback `e<expressID>`）；pset 合成 id `pset_<expressID>_<n>`。
- convert.js 内置校验：XKT 实体 id 与 metaModel id 必须一致，不一致直接报错退出。
- 重转触发：上传、retry、commit 编排、override 迁移（经 Go 队列；对运行中的同 id 任务做 dirty 重跑，保证最新内容最终被转换）。

## 测试

```bash
cd viewer/converter
npm install
npm test    # node:test 集成测试：真实 IFC 样例（buildingSMART 官方 fixture）转换快照
```
