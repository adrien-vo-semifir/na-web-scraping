// Package server est la logique métier de l'API de contrôle : un serveur HTTP qui
// reçoit les commandes d'acquisition et les soumet à un Orchestrator.
//
// RÉVERSIBILITÉ (docs/structure-projet.md §1) : ce paquet est Temporal-FREE. Il ne
// connaît que l'interface Orchestrator (définie ici, sans dépendance à l'orchestrateur).
// L'implémentation concrète (Temporal) est injectée par le main de composition
// (platform/control-api/main.go), jamais importée ici. Aucun import du SDK de
// l'orchestrateur ne doit apparaître dans ce paquet (garde-fou de réversibilité, §7).
package server

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
)

// Orchestrator est la frontière d'orchestration vue par l'API : soumettre une commande
// et obtenir un identifiant de suivi (workflow id, job id…). Définie côté métier, sans
// référence à un orchestrateur concret — c'est ce qui rend Temporal remplaçable.
type Orchestrator interface {
	Submit(ctx context.Context, cmd *acquisitionv1.AcquisitionCommand) (handle string, err error)
}

// Server expose les routes de l'API de contrôle. Il dépend d'un Orchestrator injecté.
type Server struct {
	orch Orchestrator
}

// New construit le serveur avec l'Orchestrator fourni (injection de dépendance).
func New(orch Orchestrator) *Server {
	return &Server{orch: orch}
}

// Handler renvoie le multiplexeur HTTP avec les routes enregistrées.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.handleHealthz)
	mux.HandleFunc("POST /acquisitions", s.handleAcquisitions)
	return mux
}

// acquisitionRequest — corps attendu de POST /acquisitions.
type acquisitionRequest struct {
	URL                  string `json:"url"`
	Source               string `json:"source,omitempty"`
	Dataset              string `json:"dataset,omitempty"`
	ConfigurationVersion string `json:"configuration_version,omitempty"`
}

// acquisitionResponse — corps renvoyé en cas de soumission acceptée.
type acquisitionResponse struct {
	AcquisitionID string `json:"acquisition_id"`
	Handle        string `json:"handle"`
	Status        string `json:"status"`
}

func (s *Server) handleHealthz(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) handleAcquisitions(w http.ResponseWriter, r *http.Request) {
	var req acquisitionRequest
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "corps JSON invalide: " + err.Error()})
		return
	}
	if strings.TrimSpace(req.URL) == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "champ 'url' obligatoire"})
		return
	}

	cmd := &acquisitionv1.AcquisitionCommand{
		URL:                  req.URL,
		Source:               defaulted(req.Source, "web"),
		Dataset:              defaulted(req.Dataset, "pages"),
		Mode:                 acquisitionv1.AcquisitionMode_STATIC,
		ConfigurationVersion: defaulted(req.ConfigurationVersion, "v1"),
	}

	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()

	handle, err := s.orch.Submit(ctx, cmd)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "soumission impossible: " + err.Error()})
		return
	}

	writeJSON(w, http.StatusAccepted, acquisitionResponse{
		AcquisitionID: cmd.AcquisitionId(),
		Handle:        handle,
		Status:        "accepted",
	})
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func defaulted(v, fallback string) string {
	if strings.TrimSpace(v) == "" {
		return fallback
	}
	return v
}
