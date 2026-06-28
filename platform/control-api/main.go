// Command control-api est le point d'entrée REST des commandes d'acquisition, et le
// COMPOSITION ROOT de l'API : c'est ici, et seulement ici côté API, que la logique
// métier (platform/control-api/server, agnostique de l'orchestrateur) est câblée à
// l'implémentation concrète de l'orchestrateur (orchestration/temporal/orchestrator).
//
// RÉVERSIBILITÉ (docs/structure-projet.md §1 & §7) : ce main référence
// orchestration/temporal pour le wiring, mais n'importe PAS le SDK d'orchestration
// directement — son usage est entièrement encapsulé dans le paquet orchestrator
// (qui, lui, vit sous orchestration/temporal/). Le serveur (server.Server) ne connaît
// que l'interface server.Orchestrator ; on pourrait injecter une autre implémentation
// (ou un faux pour les tests) sans toucher au métier.
//
// Configuration par environnement :
//
//	API_ADDR          adresse d'écoute HTTP        (défaut :8000)
//	TEMPORAL_ADDRESS  adresse du frontend Temporal (défaut localhost:7233)
//	TASK_QUEUE        Task Queue cible             (défaut "acquisition")
package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/adrien-vo-semifir/na-web-scraping/orchestration/temporal/orchestrator"
	server "github.com/adrien-vo-semifir/na-web-scraping/platform/control-api/server"
)

const (
	defaultAPIAddr         = ":8000"
	defaultTemporalAddress = "localhost:7233"
	defaultTaskQueue       = "acquisition"
)

func main() {
	apiAddr := envOr("API_ADDR", defaultAPIAddr)
	temporalAddr := envOr("TEMPORAL_ADDRESS", defaultTemporalAddress)
	taskQueue := envOr("TASK_QUEUE", defaultTaskQueue)

	// --- Composition : orchestrateur concret (encapsule le client Temporal) → serveur. ---
	orch, closeOrch, err := orchestrator.Dial(temporalAddr, taskQueue)
	if err != nil {
		log.Fatalf("control-api: %v", err)
	}
	defer closeOrch()

	// L'implémentation concrète est injectée derrière l'interface server.Orchestrator.
	var o server.Orchestrator = orch
	srv := server.New(o)

	httpServer := &http.Server{
		Addr:              apiAddr,
		Handler:           srv.Handler(),
		ReadHeaderTimeout: 10 * time.Second,
	}

	// Arrêt gracieux sur SIGINT/SIGTERM.
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	go func() {
		log.Printf("control-api: écoute sur %s (temporal=%s, task_queue=%s)", apiAddr, temporalAddr, taskQueue)
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("control-api: serveur HTTP: %v", err)
		}
	}()

	<-ctx.Done()
	log.Printf("control-api: arrêt demandé, fermeture…")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := httpServer.Shutdown(shutdownCtx); err != nil {
		log.Printf("control-api: arrêt non gracieux: %v", err)
	}
}

func envOr(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}
