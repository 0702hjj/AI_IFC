package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"path/filepath"
	"strings"

	"ifcviewer/server/internal/convert"
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
	maxUpload int64
}

func NewHandler(st *store.Store, q *convert.Queue, maxUploadBytes int64) http.Handler {
	h := &handler{st: st, q: q, maxUpload: maxUploadBytes}
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/models", h.upload)
	mux.HandleFunc("GET /api/models", h.list)
	mux.HandleFunc("GET /api/models/{id}", h.get)
	mux.HandleFunc("POST /api/models/{id}/retry", h.retry)
	mux.HandleFunc("DELETE /api/models/{id}", h.delete)
	mux.HandleFunc("GET /api/models/{id}/download", h.download)
	mux.HandleFunc("GET /models/{id}/model.xkt", h.serveModelFile("model.xkt"))
	mux.HandleFunc("GET /models/{id}/metadata.json", h.serveModelFile("metadata.json"))
	return cors(mux)
}

func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
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
