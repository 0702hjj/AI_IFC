// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// fs_backend.go：M2-0 打地基——官方 filesystem middleware 的收敛适配（D12）。
//
// 官方 filesystem middleware（adk/middlewares/filesystem）注入文件工具组
// （ls/read_file/write_file/edit_file/glob/grep）+ execute，但 Backend 非空即
// 全挂（无开关单独禁用 write/edit）。领域收敛红线（api_regulation：禁止任意
// 文件写）要求我们做一层薄包装：
//
//   - Backend = fsReadOnlyBackend（包住 local backend）：读方法透传，Write/Edit 拒绝
//   - StreamingShell = local backend（/bin/sh -c）+ ValidateCommand 白名单：
//     打地基最小集 = aiplan / aidxfv3 系列 CLI（skill 捆绑命令），其余拒绝
//
// skill CLI 产出（plan.json/DXF 等）由命令自身写盘（走 /bin/sh -c），
// 不经过 Backend.Write——所以只读包装不影响 skill 脚本执行闭环。
package agent

import (
	"context"
	"fmt"
	"strings"

	"github.com/cloudwego/eino/adk/filesystem"
)

// skillCommandAllowlist 是 execute 命令白名单（默认 = dist 正式集合的 CLI 入口：
// aiplan / aidxfv3 / aiifc）。可经 SetSkillCommandAllowlist 配置化（第二层：对齐已接入
// skill 集合）；正式 skill 命令面（完整子命令枚举）后续按 machine_contract 细化。
var skillCommandAllowlist = []string{"aiplan", "aidxfv3", "aiifc"}

// SetSkillCommandAllowlist 覆盖 execute 命令白名单（装配时调用，来自 server 配置）。
// 空列表 = 全部拒绝（execute 不可用）。
func SetSkillCommandAllowlist(names []string) {
	if len(names) == 0 {
		skillCommandAllowlist = []string{}
		return
	}
	out := make([]string, 0, len(names))
	seen := map[string]bool{}
	for _, n := range names {
		if n == "" || seen[n] {
			continue
		}
		seen[n] = true
		out = append(out, n)
	}
	skillCommandAllowlist = out
}

// validateSkillCommand 是 local backend 的 ValidateCommand 回调：
// 只放行白名单命令（按第一个 token 精确匹配），其余拒绝（领域收敛单点）。
func validateSkillCommand(cmd string) error {
	c := strings.TrimSpace(cmd)
	if c == "" {
		return fmt.Errorf("命令为空")
	}
	name := strings.Fields(c)[0]
	for _, allow := range skillCommandAllowlist {
		if name == allow {
			return nil
		}
	}
	return fmt.Errorf("命令不在白名单（打地基阶段仅允许 %s）：%s", strings.Join(skillCommandAllowlist, "/"), cmd)
}

// fsReadOnlyBackend 是 filesystem.Backend 的只读包装：
// 读方法（LsInfo/Read/GrepRaw/GlobInfo）透传 local backend；
// Write/Edit 拒绝（领域收敛：模型不能任意写文件；skill CLI 产物由命令自身落盘）。
type fsReadOnlyBackend struct {
	inner filesystem.Backend
}

func (b *fsReadOnlyBackend) LsInfo(ctx context.Context, req *filesystem.LsInfoRequest) ([]filesystem.FileInfo, error) {
	return b.inner.LsInfo(ctx, req)
}

func (b *fsReadOnlyBackend) Read(ctx context.Context, req *filesystem.ReadRequest) (*filesystem.FileContent, error) {
	return b.inner.Read(ctx, req)
}

func (b *fsReadOnlyBackend) GrepRaw(ctx context.Context, req *filesystem.GrepRequest) ([]filesystem.GrepMatch, error) {
	return b.inner.GrepRaw(ctx, req)
}

func (b *fsReadOnlyBackend) GlobInfo(ctx context.Context, req *filesystem.GlobInfoRequest) ([]filesystem.FileInfo, error) {
	return b.inner.GlobInfo(ctx, req)
}

// Write 拒绝：领域收敛红线——模型不持任意文件写能力（skill CLI 产物经 execute 自身落盘）。
func (b *fsReadOnlyBackend) Write(_ context.Context, _ *filesystem.WriteRequest) error {
	return fmt.Errorf("领域收敛：filesystem 只读——模型禁止直接写文件（skill 产物经 CLI 落盘）")
}

// Edit 拒绝：同上（任意文件改写也不允许）。
func (b *fsReadOnlyBackend) Edit(_ context.Context, _ *filesystem.EditRequest) error {
	return fmt.Errorf("领域收敛：filesystem 只读——模型禁止直接改写文件（skill 产物经 CLI 落盘）")
}
