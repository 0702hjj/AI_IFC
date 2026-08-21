// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// skeleton_script_test.go：骨架脚本满足 edit-service 脚本契约（PARAMS/build/__main__）。
package api

import (
	"strings"
	"testing"
)

func TestSkeletonScriptsContract(t *testing.T) {
	cases := map[string]string{
		"ifc": skeletonIFCScript,
		"dxf": skeletonDXFScript,
	}
	for kind, script := range cases {
		if !strings.HasPrefix(script, "PARAMS = {") {
			t.Errorf("%s 骨架脚本缺 PARAMS 顶层字面量", kind)
		}
		if !strings.Contains(script, "def build(params, out_path):") {
			t.Errorf("%s 骨架脚本缺 build(params, out_path) 入口", kind)
		}
		if !strings.Contains(script, `if __name__ == "__main__":`) {
			t.Errorf("%s 骨架脚本缺 __main__ 调用", kind)
		}
		if !strings.Contains(script, "{title}") {
			t.Errorf("%s 骨架脚本缺 {title} 占位符（initModel 填充）", kind)
		}
	}
	// 骨架结构对齐旧 skeletonIFC/skeletonDXF
	if !strings.Contains(skeletonIFCScript, "IfcProject") || !strings.Contains(skeletonIFCScript, "context.add_context") {
		t.Error("ifc 骨架脚本缺 IfcProject/几何上下文构建")
	}
	if !strings.Contains(skeletonDXFScript, "ezdxf.new") || !strings.Contains(skeletonDXFScript, "AC1009") {
		t.Error("dxf 骨架脚本缺空图纸（HEADER AC1009 + 空 ENTITIES）")
	}
}
