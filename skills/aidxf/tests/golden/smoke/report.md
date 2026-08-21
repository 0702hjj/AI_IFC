# smoke report

## S0 预处理
- [x] preprocess 产出 derived/（floors.json + house.json）
- [x] 轮廓级摄取校验通过

## S1 骨架
- [x] skeleton.json 过 schema/normalize/check
- [ ] 【断点① 人工确认】骨架方案（自动化冒烟标记待确认）

## S2 房间
- [x] rooms.json 过 schema/normalize/check
- [ ] 【断点② 人工确认】房间方案（自动化冒烟标记待确认）
- [x] reconcile 对账通过（画出来的 = 声明的）

## S4 交付
- [x] 每 zone 注册平台模型（init_model+script 工具链）+ building.json 记 modelId

## 结论
自动化冒烟全闸门绿；两次人工断点确认待人工执行。
