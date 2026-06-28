// Command control-api est le point d'entrée REST des commandes d'acquisition, et le
// COMPOSITION ROOT de l'API : c'est ici, et seulement ici côté API, que la logique
// métier (platform/control-api/server, agnostique de l'orchestrateur) est câblée à une
// implémentation concrète de l'interface server.Orchestrator.
//
// Deux implémentations sont câblées ici :
//
//   - Temporal (orchestration/temporal/orchestrator) — déclenchement durable, idempotent,
//     avec reprises : la voie nominale (production). C'est la qualité « base de prod ».
//   - Directe (platform/control-api/directorch) — exécution synchrone EN PROCESSUS via
//     platform/acquire, sans orchestrateur : un REPLI permettant de lancer et tester
//     l'API sans frontend Temporal (POC, dev, ou Temporal indisponible).
//
// Sélection par environnement (ORCHESTRATOR). En mode temporal, si la connexion au
// frontend échoue, on bascule automatiquement sur le repli direct plutôt que d'échouer :
// l'API reste disponible et testable. Le repli direct est Temporal-FREE.
//
// RÉVERSIBILITÉ (docs/structure-projet.md §1 & §7) : ce main référence
// orchestration/temporal pour le wiring, mais n'importe PAS le SDK d'orchestration
// directement — son usage est entièrement encapsulé dans le paquet orchestrator (qui,
// lui, vit sous orchestration/temporal/). Le serveur (server.Server) ne connaît que
// l'interface server.Orchestrator ; on injecte l'une ou l'autre implémentation (ou un
// faux pour les tests) sans toucher au métier.
//
// Configuration par environnement :
//
//	API_ADDR          adresse d'écoute HTTP            (défaut :8000)
//	ORCHESTRATOR      orchestrateur : temporal | direct (défaut temporal)
//	TEMPORAL_ADDRESS  adresse du frontend Temporal     (défaut localhost:7233)
//	TASK_QUEUE        Task Queue cible                 (défaut "acquisition")
//	SINK              sink du repli direct : local | s3 (défaut local)
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
	"github.com/adrien-vo-semifir/na-web-scraping/platform/control-api/directorch"
	server "github.com/adrien-vo-semifir/na-web-scraping/platform/control-api/server"
)

const (
	defaultAPIAddr         = ":8000"
	defaultOrchestrator    = "temporal"
	defaultTemporalAddress = "localhost:7233"
	defaultTaskQueue       = "acquisition"
)

func main() {
	apiAddr := envOr("API_ADDR", defaultAPIAddr)
	orchMode := strings.ToLower(envOr("ORCHESTRATOR", defaultOrchestrator))

	// --- Composition : sélection + construction de l'orchestrateur, injecté derrière
	// l'interface server.Orchestrator. Une fonction de fermeture (no-op pour le repli)
	// est renvoyée pour libérer d'éventuelles ressources (client Temporal).
	orch, closeOrch := buildOrchestrator(orchMode)
	defer closeOrch()

	srv := server.New(orch)

	httpServer := &http.Server{
		Addr:              apiAddr,
		Handler:           srv.Handler(),
		ReadHeaderTimeout: 10 * time.Second,
	}

	// Arrêt gracieux sur SIGINT/SIGTERM.
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	go func() {
		log.Printf("control-api: écoute sur %s", apiAddr)
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

// buildOrchestrator construit l'implémentation de server.Orchestrator selon le mode
// demandé, et renvoie une fonction de fermeture des ressources associées.
//
//   - "direct"   : repli synchrone en processus (Temporal-FREE), via platform/control-api/directorch.
//   - "temporal" : voie nominale ; en cas d'échec de connexion au frontend Temporal, on
//     bascule automatiquement sur le repli direct (l'API reste disponible).
//
// Le composition root est le seul endroit, côté API, à connaître les deux implémentations.
func buildOrchestrator(mode string) (server.Orchestrator, func()) {
	switch mode {
	case "direct":
		return buildDirect(), func() {}

	case "temporal", "":
		temporalAddr := envOr("TEMPORAL_ADDRESS", defaultTemporalAddress)
		taskQueue := envOr("TASK_QUEUE", defaultTaskQueue)

		orch, closeOrch, err := orchestrator.Dial(temporalAddr, taskQueue)
		if err != nil {
			log.Printf("control-api: connexion à Temporal impossible (%s): %v", temporalAddr, err)
			log.Printf("control-api: bascule sur l'orchestrateur direct (repli en processus)")
			return buildDirect(), func() {}
		}
		log.Printf("control-api: orchestrateur=temporal (temporal=%s, task_queue=%s)", temporalAddr, taskQueue)
		return orch, closeOrch

	default:
		log.Fatalf("control-api: ORCHESTRATOR inconnu %q (attendu: temporal | direct)", mode)
		return nil, nil // inatteignable (log.Fatalf termine le processus)
	}
}

// buildDirect construit l'orchestrateur de repli (Temporal-FREE). Un échec d'init du Sink
// est fatal : le repli ne peut pas fonctionner sans destination d'écriture du brut.
func buildDirect() server.Orchestrator {
	orch, err := directorch.NewFromEnv(context.Background())
	if err != nil {
		log.Fatalf("control-api: initialisation de l'orchestrateur direct: %v", err)
	}
	log.Printf("control-api: orchestrateur=direct (sink=%s)", envOr("SINK", "local"))
	return orch
}

func envOr(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}
