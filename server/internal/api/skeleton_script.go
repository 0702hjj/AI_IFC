// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// skeleton_script.go：模型初始化骨架脚本模板（script-as-source 初始化）。
// 骨架脚本 = 满足 edit-service 脚本契约（PARAMS 顶层字面量 + build(params, out_path) +
// __main__ 调 build）的最小可构建脚本——沙箱执行生成最小骨架模型（v1），后续 agent
// 在骨架上增量深化（stage→run→save）。骨架内容对齐旧 skeletonIFC/skeletonDXF：
//   IFC：IfcProject + 几何上下文 + 单位（最小聚合树，无 storey）
//   DXF：空图纸（HEADER + 空 ENTITIES）
// 自包含（不依赖 skills script_lib——沙箱内不保证 skills 引用路径）。
package api

// skeletonIFCScript 是 IFC 骨架构建脚本（最小 ifcopenshell 骨架）。
// 占位符 {title} 由 initModel 填充（project title；globalId 由 ifcopenshell 派生）。
const skeletonIFCScript = `PARAMS = {"title": "{title}"}

import ifcopenshell
import ifcopenshell.api


def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    # 顺序契约：先建 IfcProject，再单位/几何上下文（assign_unit 依赖 IfcProject 存在）
    ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject",
                         name=params["title"])
    ifcopenshell.api.run("unit.assign_unit", model)
    m3d = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    ifcopenshell.api.run("context.add_context", model, context_type="Model",
                         context_identifier="Body", target_view="MODEL_VIEW", parent=m3d)
    model.write(out_path)


if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1] if len(sys.argv) > 1 else "model.ifc")
`

// skeletonDXFScript 是 DXF 骨架构建脚本（最小 ezdxf 空图纸）。
// 占位符 {title} 由 initModel 填充（写入图纸 header 的 title 属性）。
const skeletonDXFScript = `PARAMS = {"title": "{title}"}

import ezdxf


def build(params, out_path):
    doc = ezdxf.new()
    doc.header["$ACADVER"] = "AC1009"
    doc.saveas(out_path)


if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1] if len(sys.argv) > 1 else "model.dxf")
`
