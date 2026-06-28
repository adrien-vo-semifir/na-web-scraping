// Command worker-bootstrap démarre le Worker Go : il poll la Task Queue d'acquisition,
// porte le(s) Workflow(s) Go et l'Activity Go d'acquisition HTTP statique.
//
// Composition root de la couche d'orchestration (docs/structure-projet.md §3.3) : c'est
// l'un des rares mains autorisés à câbler ensemble Temporal et le code métier. Le
// Worker Temporal est mono-langage ; ce bootstrap est celui du langage Go.
//
// Configuration par environnement :
//
//	TEMPORAL_ADDRESS  adresse du frontend Temporal (défaut localhost:7233)
//	TASK_QUEUE        Task Queue à poller        (défaut "acquisition")
//	SINK              destination du brut : local | s3 (lu par l'Activity)
package main

import (
	"log"
	"os"
	"strings"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"

	activities "github.com/adrien-vo-semifir/na-web-scraping/orchestration/temporal/activities/http-activity-go"
	workflows "github.com/adrien-vo-semifir/na-web-scraping/orchestration/temporal/workflows-go"
)

const (
	defaultTemporalAddress = "localhost:7233"
	defaultTaskQueue       = "acquisition"
)

func main() {
	address := envOr("TEMPORAL_ADDRESS", defaultTemporalAddress)
	taskQueue := envOr("TASK_QUEUE", defaultTaskQueue)

	c, err := client.Dial(client.Options{HostPort: address})
	if err != nil {
		log.Fatalf("worker-bootstrap: connexion à Temporal (%s): %v", address, err)
	}
	defer c.Close()

	w := worker.New(c, taskQueue, worker.Options{})
	w.RegisterWorkflow(workflows.AcquisitionWorkflow)
	w.RegisterActivity(activities.AcquireActivity)

	log.Printf("worker-bootstrap: Worker Go démarré (temporal=%s, task_queue=%s)", address, taskQueue)
	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatalf("worker-bootstrap: arrêt du Worker: %v", err)
	}
}

func envOr(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}
