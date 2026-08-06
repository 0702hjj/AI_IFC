---
name: step-04-deliver
description: Write building.json (floor↔DXF map + non-geometric metadata + checksums) alongside the DXF set and report.
---

# Step 4: 交付落盘

## 输入
- 全部 canonical DXF（来自 step3）
- plan.json（floors 的 name / height_mm）
- `references/plan_contract.md` §2

## 执行
1. 在输出目录写 `building.json`（最小集，字段见契约 §2）：
   - `floors[]`：name、dxf 相对路径、elevation_mm（由 height_mm 累加）、
     height_mm、sha256（**canon 之后**的字节哈希）
   - `metadata`：DXF 承载不了的建筑信息——材质、构造做法、occupancy、
     竖向关系说明。想不出写什么就写空对象 + notes，**不许口头传递**。
2. 一致性自检：building.json 每个 `dxf` 路径存在、sha256 与实际文件一致、
   floors 与 plan.json 一致。
3. 向用户报告：输出目录、每层文件、验证摘要（FAIL/WARN 计数与豁免理由）、
   building.json 位置。

## 输出
- `<输出目录>/building.json` + 全部 DXF

## 完成条件
building.json 自检全过。bim 阶段此后只读 building.json + DXF，不读本 skill 的
任何中间态。
