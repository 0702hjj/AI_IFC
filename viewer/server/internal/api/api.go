package api

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"
	"path/filepath"
	"regexp"
	"strings"

	"ifcviewer/server/internal/change"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/issue"
	"ifcviewer/server/internal/store"
)

const (
	codeInvalidType = 40001
	codeTooLarge    = 40002
	codeNotFound    = 40400
	codeInternal    = 50000
)

type envelope struct {
	Code    int         `json:"code"`
	Message string      `json:"message"`
	Data    interface{} `json:"data"`
}

type handler struct {
	st        *store.Store
	q         *convert.Queue
	iss       issue.Store
	chg       change.Store
	maxUpload int64
}

func NewHandler(st *store.Store, q *convert.Queue, iss issue.Store, chg change.Store, maxUploadBytes int64) http.Handler {
	h := &handler{st: st, q: q, iss: iss, chg: chg, maxUpload: maxUploadBytes}
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/models", h.upload)
	mux.HandleFunc("GET /api/models", h.list)
	mux.HandleFunc("GET /api/models/{id}", h.get)
	mux.HandleFunc("POST /api/models/{id}/retry", h.retry)
	mux.HandleFunc("DELETE /api/models/{id}", h.delete)
	mux.HandleFunc("GET /api/models/{id}/download", h.download)
	mux.HandleFunc("GET /models/{id}/model.xkt", h.serveModelFile("model.xkt"))
	mux.HandleFunc("GET /models/{id}/metadata.json", h.serveModelFile("metadata.json"))
	mux.HandleFunc("GET /api/models/{id}/issues", h.listIssues)
	mux.HandleFunc("POST /api/models/{id}/issues", h.createIssue)
	mux.HandleFunc("PATCH /api/models/{id}/issues/{issueId}", h.updateIssue)
	mux.HandleFunc("DELETE /api/models/{id}/issues/{issueId}", h.deleteIssue)
	mux.HandleFunc("GET /models/{id}/issues/{file}", h.serveIssueFile)
	mux.HandleFunc("GET /api/models/{id}/changes", h.listChanges)
	return cors(mux)
}

func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func writeJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	json.NewEncoder(w).Encode(envelope{Code: 0, Message: "ok", Data: data})
}

func writeErr(w http.ResponseWriter, httpStatus, code int, msg string) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(httpStatus)
	json.NewEncoder(w).Encode(envelope{Code: code, Message: msg, Data: nil})
}

func (h *handler) modelOrErr(w http.ResponseWriter, id string) *store.Model {
	m, err := h.st.Get(id)
	if errors.Is(err, store.ErrNotFound) || errors.Is(err, store.ErrInvalidID) {
		writeErr(w, http.StatusNotFound, codeNotFound, "model not found")
		return nil
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return nil
	}
	return m
}

func (h *handler) upload(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, h.maxUpload)
	if err := r.ParseMultipartForm(h.maxUpload); err != nil {
		writeErr(w, http.StatusBadRequest, codeTooLarge, "file exceeds size limit")
		return
	}
	file, fh, err := r.FormFile("file")
	if err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "missing file field")
		return
	}
	defer file.Close()
	if !strings.EqualFold(filepath.Ext(fh.Filename), ".ifc") {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "only .ifc files are allowed")
		return
	}
	m, err := h.st.Create(fh.Filename, fh.Size, file)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	h.q.Enqueue(m.ID)
	writeJSON(w, m)
}

func (h *handler) list(w http.ResponseWriter, r *http.Request) {
	models, err := h.st.List()
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	if models == nil {
		models = []*store.Model{}
	}
	writeJSON(w, models)
}

func (h *handler) get(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	writeJSON(w, m)
}

func (h *handler) retry(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	if m.Status != "failed" {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "only failed models can be retried")
		return
	}
	if err := h.st.SetStatus(m.ID, "converting", ""); err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	h.q.Enqueue(m.ID)
	m, err := h.st.Get(m.ID)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	writeJSON(w, m)
}

func (h *handler) delete(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	if err := h.st.Delete(m.ID); err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	writeJSON(w, nil)
}

func (h *handler) download(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	w.Header().Set("Content-Disposition", "attachment; filename*=UTF-8''"+url.PathEscape(m.Name))
	http.ServeFile(w, r, h.st.IFCPath(m.ID))
}

func (h *handler) serveModelFile(name string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		m := h.modelOrErr(w, r.PathValue("id"))
		if m == nil {
			return
		}
		http.ServeFile(w, r, filepath.Join(h.st.ModelDir(m.ID), name))
	}
}

const maxIssueUpload = 6 << 20 // 6MB
const maxScreenshot = 5 << 20  // 5MB

var issueFilePattern = regexp.MustCompile(`^i_[0-9a-f]{12}\.png$`)

func (h *handler) listIssues(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	issues, err := h.iss.List(m.ID)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	if issues == nil {
		issues = []*issue.Issue{}
	}
	writeJSON(w, issues)
}

func (h *handler) createIssue(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, maxIssueUpload)
	if err := r.ParseMultipartForm(maxIssueUpload); err != nil {
		writeErr(w, http.StatusBadRequest, codeTooLarge, "request exceeds size limit")
		return
	}
	raw := r.FormValue("issue")
	if raw == "" {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "missing issue field")
		return
	}
	var in issue.Issue
	if err := json.Unmarshal([]byte(raw), &in); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid issue json")
		return
	}
	var png []byte
	if file, _, err := r.FormFile("screenshot"); err == nil {
		defer file.Close()
		data, err := io.ReadAll(io.LimitReader(file, maxScreenshot+1))
		if err != nil || len(data) > maxScreenshot {
			writeErr(w, http.StatusBadRequest, codeTooLarge, "screenshot exceeds 5MB")
			return
		}
		if http.DetectContentType(data) != "image/png" {
			writeErr(w, http.StatusBadRequest, codeInvalidType, "screenshot must be png")
			return
		}
		png = data
	}
	created, err := h.iss.Create(m.ID, &in)
	if errors.Is(err, issue.ErrEmptyTitle) || errors.Is(err, issue.ErrInvalidStatus) {
		writeErr(w, http.StatusBadRequest, codeInvalidType, err.Error())
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	if png != nil {
		if _, err := h.iss.SaveScreenshot(m.ID, created.ID, png); err != nil {
			writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
			return
		}
		created.Screenshot = "issues/" + created.ID + ".png"
	}
	writeJSON(w, created)
}

func (h *handler) updateIssue(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	var patch issue.IssuePatch
	if err := json.NewDecoder(r.Body).Decode(&patch); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid json body")
		return
	}
	got, err := h.iss.Update(m.ID, r.PathValue("issueId"), patch)
	if errors.Is(err, issue.ErrNotFound) || errors.Is(err, issue.ErrInvalidID) {
		writeErr(w, http.StatusNotFound, codeNotFound, "issue not found")
		return
	}
	if errors.Is(err, issue.ErrInvalidStatus) || errors.Is(err, issue.ErrEmptyTitle) {
		writeErr(w, http.StatusBadRequest, codeInvalidType, err.Error())
		return
	}
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	writeJSON(w, got)
}

func (h *handler) deleteIssue(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	if err := h.iss.Delete(m.ID, r.PathValue("issueId")); err != nil {
		if errors.Is(err, issue.ErrNotFound) || errors.Is(err, issue.ErrInvalidID) {
			writeErr(w, http.StatusNotFound, codeNotFound, "issue not found")
			return
		}
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	writeJSON(w, nil)
}

func (h *handler) serveIssueFile(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	file := r.PathValue("file")
	if !issueFilePattern.MatchString(file) {
		writeErr(w, http.StatusNotFound, codeNotFound, "file not found")
		return
	}
	http.ServeFile(w, r, filepath.Join(h.st.ModelDir(m.ID), "issues", file))
}

func (h *handler) listChanges(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	entries, err := h.chg.List(m.ID)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		return
	}
	if entries == nil {
		entries = []*change.Entry{}
	}
	writeJSON(w, entries)
}
