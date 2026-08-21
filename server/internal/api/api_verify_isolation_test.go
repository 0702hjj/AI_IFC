// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

// W-0024 校验隔离契约测试（机器强制）。
//
// AGENTS.md「校验与业务隔离」硬规则：业务规则校验归 domain 包的 validate()/Valid*()
// + 哨兵错误；handler 只做 解码 → 调用 → errors.Is 翻译。本测试用 go/ast 解析
// 本包 handler 源码，断言 handler（注册路由的方法）体内不得内联业务规则 writeErr。
//
// 判定：直接写在 handler 体内的 writeErr 调用，按状态码区分——
//   - http.StatusBadRequest（400）= 请求形状校验，豁免；
//   - 其他状态码（404/409/422/500/502/410）= 违规。
//
// writeEditErr / writeChatErr / modelOrErr / sessionOrErr 等「错误翻译 helper」不算违规
// （它们是翻译层，writeErr 的调用点不在 handler 体内，不在本测试扫描范围）。
//
// 机器强制的目标是「新代码不得违规」：存量违规以显式 verifyIsolationAllowlist 登记
// （保证 CI 绿），新 handler 内联非 400 writeErr 不在白名单 → 变红。

import (
	"go/ast"
	"go/parser"
	"go/token"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"testing"
)

// writeErrCall 是一次 handler 内联 writeErr 调用（函数名 + 状态码 + 行号）。
type writeErrCall struct {
	funcName string
	status   int
	line     int
}

// handlerBody 是一个待扫描的 handler 体：方法/闭包工厂用方法名，内联闭包用路由
// pattern（无方法名，如 "GET /api/v1/closure"）。
type handlerBody struct {
	name string
	body ast.Node
}

// httpStatusNameCode 是 net/http 状态码常量名 → 数值映射（自足，不依赖 type-checker）。
var httpStatusNameCode = map[string]int{
	"StatusOK":                            200,
	"StatusCreated":                       201,
	"StatusAccepted":                      202,
	"StatusNoContent":                     204,
	"StatusResetContent":                  205,
	"StatusPartialContent":                206,
	"StatusMultipleChoices":               300,
	"StatusMovedPermanently":              301,
	"StatusFound":                         302,
	"StatusSeeOther":                      303,
	"StatusNotModified":                   304,
	"StatusTemporaryRedirect":             307,
	"StatusPermanentRedirect":             308,
	"StatusBadRequest":                    400,
	"StatusUnauthorized":                  401,
	"StatusPaymentRequired":               402,
	"StatusForbidden":                     403,
	"StatusNotFound":                      404,
	"StatusMethodNotAllowed":              405,
	"StatusNotAcceptable":                 406,
	"StatusProxyAuthRequired":             407,
	"StatusRequestTimeout":                408,
	"StatusConflict":                      409,
	"StatusGone":                          410,
	"StatusLengthRequired":                411,
	"StatusPreconditionFailed":            412,
	"StatusRequestEntityTooLarge":         413,
	"StatusRequestURITooLong":             414,
	"StatusUnsupportedMediaType":          415,
	"StatusRequestedRangeNotSatisfiable":  416,
	"StatusExpectationFailed":             417,
	"StatusTeapot":                        418,
	"StatusMisdirectedRequest":            421,
	"StatusUnprocessableEntity":           422,
	"StatusLocked":                        423,
	"StatusFailedDependency":              424,
	"StatusUpgradeRequired":               426,
	"StatusPreconditionRequired":          428,
	"StatusTooManyRequests":               429,
	"StatusRequestHeaderFieldsTooLarge":   431,
	"StatusUnavailableForLegalReasons":    451,
	"StatusInternalServerError":           500,
	"StatusNotImplemented":                501,
	"StatusBadGateway":                    502,
	"StatusServiceUnavailable":            503,
	"StatusGatewayTimeout":                504,
	"StatusHTTPVersionNotSupported":       505,
	"StatusVariantAlsoNegotiates":         506,
	"StatusInsufficientStorage":           507,
	"StatusLoopDetected":                  508,
	"StatusNotExtended":                   510,
	"StatusNetworkAuthenticationRequired": 511,
}

// 存量违规白名单（机器强制目标：新代码不得违规；存量以显式登记收容）。
// 归属：api.go / chat 模块 handler 内联的非 400 writeErr（多为 5xx 内部错误透传 /
// 领域状态 404），无专项 deadline，随触碰 handler 收拢（W-0024 存量推开）。
//
// 新增 handler 内联非 400 writeErr → 本测试变红。
var verifyIsolationAllowlist = map[string][]int{
	"upload":              {http.StatusInternalServerError},
	"list":                {http.StatusInternalServerError},
	"retry":               {http.StatusInternalServerError},
	"delete":              {http.StatusInternalServerError},
	"listIssues":          {http.StatusInternalServerError},
	"createIssue":         {http.StatusInternalServerError},
	"updateIssue":         {http.StatusNotFound, http.StatusInternalServerError},
	"deleteIssue":         {http.StatusNotFound, http.StatusInternalServerError},
	"serveIssueFile":      {http.StatusNotFound},
	"listOverrides":       {http.StatusInternalServerError},
	"putEntityProperties": {http.StatusInternalServerError},
	"listChanges":         {http.StatusInternalServerError},
	"events":              {http.StatusInternalServerError},
	"createProject":       {http.StatusInternalServerError},
	"putPlanFile":         {http.StatusInternalServerError}, // 写盘 IO 透传（PlanStore.Put）
	"deleteProject":       {http.StatusInternalServerError}, // Ps.Delete 存储错误透传（404 归 projectOrErr helper）
}

// statusArgCode 从 http.StatusXxx 常量选择器解析状态码；无法静态判定返回 0（跳过）。
func statusArgCode(arg ast.Expr) int {
	sel, ok := arg.(*ast.SelectorExpr)
	if !ok {
		return 0
	}
	x, ok := sel.X.(*ast.Ident)
	if !ok || x.Name != "http" {
		return 0
	}
	return httpStatusNameCode[sel.Sel.Name]
}

// inlineWriteErrCalls 扫描一组 Go 源文件，返回注册路由的 handler 体内
// 直接调用的 writeErr（非 400 状态码，即可静态判定的违规点）。
//
// handler 判定：在 HandleFunc 调用中被引用的方法（h.upload）、闭包工厂
// （h.scriptPost(...) / h.serveModelFile(...)），或内联闭包（mux.HandleFunc(path,
// func(w, r){...})）。嵌套闭包（handler 工厂返回的 FuncLit）视为 handler 代码的
// 一部分一并检查；内联闭包 handler 以路由 pattern 字符串为名（无方法名）。
func inlineWriteErrCalls(files []string) ([]writeErrCall, error) {
	fset := token.NewFileSet()
	funcs := map[string]*ast.FuncDecl{}
	var handlerBodies []handlerBody
	seen := map[string]bool{}
	var trees []*ast.File
	for _, f := range files {
		src, err := os.ReadFile(f)
		if err != nil {
			return nil, err
		}
		tree, err := parser.ParseFile(fset, f, src, 0)
		if err != nil {
			return nil, err
		}
		trees = append(trees, tree)
		for _, decl := range tree.Decls {
			if fd, ok := decl.(*ast.FuncDecl); ok {
				funcs[fd.Name.Name] = fd
			}
		}
	}
	// addHandler 去重登记一个 handler 体（方法/闭包工厂按方法名，闭包按 pattern）。
	addHandler := func(name string, body ast.Node) {
		if seen[name] {
			return
		}
		seen[name] = true
		handlerBodies = append(handlerBodies, handlerBody{name: name, body: body})
	}
	for _, tree := range trees {
		ast.Inspect(tree, func(n ast.Node) bool {
			call, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}
			sel, ok := call.Fun.(*ast.SelectorExpr)
			if !ok || sel.Sel.Name != "HandleFunc" || len(call.Args) < 2 {
				return true
			}
			if lit, ok := call.Args[1].(*ast.FuncLit); ok {
				// 内联闭包 handler：mux.HandleFunc("GET /api/v1/x", func(w, r){...})
				pattern := ""
				if s, ok := call.Args[0].(*ast.BasicLit); ok && s.Kind == token.STRING {
					if v, err := strconv.Unquote(s.Value); err == nil {
						pattern = v
					}
				}
				if pattern == "" {
					pattern = "<closure>"
				}
				addHandler(pattern, lit)
				return true
			}
			switch a := call.Args[1].(type) {
			case *ast.SelectorExpr: // h.upload
				if fd := funcs[a.Sel.Name]; fd != nil {
					addHandler(a.Sel.Name, fd)
				}
			case *ast.CallExpr: // h.scriptPost("undo")
				if s, ok := a.Fun.(*ast.SelectorExpr); ok {
					if fd := funcs[s.Sel.Name]; fd != nil {
						addHandler(s.Sel.Name, fd)
					}
				}
			}
			return true
		})
	}
	var out []writeErrCall
	for _, h := range handlerBodies {
		ast.Inspect(h.body, func(n ast.Node) bool {
			call, ok := n.(*ast.CallExpr)
			if !ok {
				return true
			}
			// writeErr 是包级函数，调用形态为 writeErr(w, ...)（Ident）；sel.Sel.Name
			// 兜底 pkg.writeErr 形态。
			var fn string
			switch f := call.Fun.(type) {
			case *ast.Ident:
				fn = f.Name
			case *ast.SelectorExpr:
				fn = f.Sel.Name
			}
			if fn != "writeErr" || len(call.Args) < 2 {
				return true
			}
			if status := statusArgCode(call.Args[1]); status != 0 && status != http.StatusBadRequest {
				out = append(out, writeErrCall{
					funcName: h.name, status: status, line: fset.Position(call.Pos()).Line,
				})
			}
			return true
		})
	}
	return out, nil
}

// apiSourceFiles 返回本包全部非测试 Go 源文件。
func apiSourceFiles() ([]string, error) {
	matches, err := filepath.Glob("*.go")
	if err != nil {
		return nil, err
	}
	var files []string
	for _, m := range matches {
		if strings.HasSuffix(m, "_test.go") {
			continue
		}
		files = append(files, m)
	}
	sort.Strings(files)
	return files, nil
}

func TestHandlersDoNotInlineBusinessWriteErr(t *testing.T) {
	files, err := apiSourceFiles()
	if err != nil {
		t.Fatal(err)
	}
	calls, err := inlineWriteErrCalls(files)
	if err != nil {
		t.Fatal(err)
	}
	var unlisted []string
	for _, c := range calls {
		allowed := false
		for _, st := range verifyIsolationAllowlist[c.funcName] {
			if st == c.status {
				allowed = true
				break
			}
		}
		if !allowed {
			unlisted = append(unlisted, strings.Join([]string{
				c.funcName, http.StatusText(c.status), "line", strconv.Itoa(c.line),
			}, " "))
		}
	}
	if len(unlisted) > 0 {
		t.Fatalf("handler 内联业务规则 writeErr 未登记白名单（新违规）:\n%s", strings.Join(unlisted, "\n"))
	}
}

func TestVerifyIsolationAllowlistMatchesRealViolations(t *testing.T) {
	files, err := apiSourceFiles()
	if err != nil {
		t.Fatal(err)
	}
	calls, err := inlineWriteErrCalls(files)
	if err != nil {
		t.Fatal(err)
	}
	real := map[string][]int{}
	for _, c := range calls {
		real[c.funcName] = append(real[c.funcName], c.status)
	}
	if got, want := normalizeSts(real), normalizeSts(verifyIsolationAllowlist); !reflect.DeepEqual(got, want) {
		t.Fatalf("白名单与实际违规不一致（收拢 handler 后请同步更新白名单）:\ngot  =%v\nallowlist=%v", got, want)
	}
}

// normalizeSts 排序去重（每个函数一组状态码），供白名单对账。
func normalizeSts(in map[string][]int) map[string][]int {
	out := map[string][]int{}
	for f, sts := range in {
		seen := map[int]bool{}
		var uniq []int
		for _, s := range sts {
			if !seen[s] {
				seen[s] = true
				uniq = append(uniq, s)
			}
		}
		sort.Ints(uniq)
		out[f] = uniq
	}
	return out
}

// --- 自证：检查逻辑有区分力（对违规样例断言会变红）---

func TestCheckerDetectsInlineBusinessWriteErr(t *testing.T) {
	dir := t.TempDir()
	files := map[string]string{
		"viol.go": `package api

import "net/http"

func (h *handler) badHandler(w http.ResponseWriter, r *http.Request) {
	writeErr(w, http.StatusNotFound, codeNotFound, "model not found")
}

func (h *handler) registerBad(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/bad", h.badHandler)
}
`,
		"ok400.go": `package api

import "net/http"

func (h *handler) shapeHandler(w http.ResponseWriter, r *http.Request) {
	writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid json body")
}

func (h *handler) registerShape(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/shape", h.shapeHandler)
}
`,
		"trans.go": `package api

import "net/http"

func (h *handler) proxyHandler(w http.ResponseWriter, r *http.Request) {
	writeEditErr(w, someErr)
}

func (h *handler) registerTrans(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/trans", h.proxyHandler)
}
`,
	}
	var paths []string
	for name, body := range files {
		p := filepath.Join(dir, name)
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
		paths = append(paths, p)
	}
	calls, err := inlineWriteErrCalls(paths)
	if err != nil {
		t.Fatal(err)
	}
	var got404 bool
	var gotExempt []string
	for _, c := range calls {
		switch c.funcName {
		case "badHandler":
			if c.status == http.StatusNotFound {
				got404 = true
			}
		default:
			gotExempt = append(gotExempt, c.funcName)
		}
	}
	if !got404 {
		t.Fatalf("自证失败：handler 内联 writeErr 404 未被检出（calls=%+v）", calls)
	}
	if len(gotExempt) > 0 {
		t.Fatalf("自证失败：请求形状校验 400 / 翻译 helper 被误报（calls=%+v）", calls)
	}
}

func TestCheckerDetectsClosureHandlerWriteErr(t *testing.T) {
	// 自证：mux.HandleFunc(path, func(w, r){...}) 内联闭包 handler 也必须被扫描
	// （W-0024 逃逸补丁：此前只扫注册为方法引用的 handler，闭包形态可绕过）。
	dir := t.TempDir()
	files := map[string]string{
		"clos.go": `package api

import "net/http"

func (h *handler) registerClosure(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/closure", func(w http.ResponseWriter, r *http.Request) {
		writeErr(w, http.StatusNotFound, codeNotFound, "closure model not found")
	})
}
`,
		"closok.go": `package api

import "net/http"

func (h *handler) registerClosureOk(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/closure-ok", func(w http.ResponseWriter, r *http.Request) {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid json body")
	})
}
`,
		"clostrans.go": `package api

import "net/http"

func (h *handler) registerClosureTrans(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/closure-trans", func(w http.ResponseWriter, r *http.Request) {
		writeEditErr(w, someErr)
	})
}
`,
	}
	var paths []string
	for name, body := range files {
		p := filepath.Join(dir, name)
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
		paths = append(paths, p)
	}
	calls, err := inlineWriteErrCalls(paths)
	if err != nil {
		t.Fatal(err)
	}
	var got404 bool
	for _, c := range calls {
		if c.funcName == "GET /api/v1/closure" && c.status == http.StatusNotFound {
			got404 = true
		}
		if c.funcName == "GET /api/v1/closure-ok" || c.funcName == "GET /api/v1/closure-trans" {
			t.Fatalf("自证失败：闭包 handler 400 / 翻译 helper 被误报（calls=%+v）", calls)
		}
	}
	if !got404 {
		t.Fatalf("自证失败：内联闭包 handler 的 writeErr 404 未被检出（calls=%+v）", calls)
	}
}
