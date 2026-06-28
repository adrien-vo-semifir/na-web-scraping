// Command starter déclenche une exécution du Workflow d'acquisition (pour tester /
// piloter manuellement un run). Composition root côté client Temporal.
//
// Usage :
//
//	go run ./orchestration/temporal/starter -url https://example.com [-source web] [-dataset pages]
//
// Configuration par environnement :
//
//	TEMPORAL_ADDRESS  adresse du frontend Temporal (défaut localhost:7233)
//	TASK_QUEUE        Task Queue cible            (défaut "acquisition")
//
// Par défaut, le starter attend le résultat du Workflow et l'imprime en JSON. Avec
// -async, il se contente de démarrer le Workflow et d'afficher ses identifiants.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"strings"

	"go.temporal.io/sdk/client"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
	workflows "github.com/adrien-vo-semifir/na-web-scraping/orchestration/temporal/workflows-go"
)

const (
	defaultTemporalAddress = "localhost:7233"
	defaultTaskQueue       = "acquisition"
)

func main() {
	os.Exit(run())
}

func run() int {
	var (
		urlFlag     = flag.String("url", "", "URL à acquérir (obligatoire)")
		sourceFlag  = flag.String("source", "web", "identifiant logique de la source")
		datasetFlag = flag.String("dataset", "pages", "jeu de données cible")
		cfgVerFlag  = flag.String("config-version", "v1", "version de configuration (idempotence)")
		browserFlag = flag.Bool("browser", false, "mode navigateur → route vers le worker TS (Playwright)")
		furtifFlag  = flag.Bool("furtif", false, "transport furtif → route vers le worker Python (curl_cffi)")
		asyncFlag   = flag.Bool("async", false, "ne pas attendre le résultat du Workflow")
	)
	flag.Parse()

	if strings.TrimSpace(*urlFlag) == "" {
		fmt.Fprintln(os.Stderr, "erreur: -url est obligatoire")
		flag.Usage()
		return 2
	}

	address := envOr("TEMPORAL_ADDRESS", defaultTemporalAddress)
	taskQueue := envOr("TASK_QUEUE", defaultTaskQueue)

	c, err := client.Dial(client.Options{HostPort: address})
	if err != nil {
		log.Printf("starter: connexion à Temporal (%s): %v", address, err)
		return 2
	}
	defer c.Close()

	cmd := &acquisitionv1.AcquisitionCommand{
		URL:                  *urlFlag,
		Source:               *sourceFlag,
		Dataset:              *datasetFlag,
		Mode:                 acquisitionv1.AcquisitionMode_STATIC,
		ConfigurationVersion: *cfgVerFlag,
	}
	if *browserFlag {
		cmd.Mode = acquisitionv1.AcquisitionMode_BROWSER // → worker TS (acquisition-ts)
	}
	if *furtifFlag {
		cmd.Headers = map[string]string{"furtif": "true"} // → worker Python (acquisition-py)
	}

	// Workflow ID déterministe = acquisition_id → garantit l'idempotence du déclenchement
	// (un même couple url+config_version ne lance pas deux Workflows concurrents).
	opts := client.StartWorkflowOptions{
		ID:        "acquisition-" + cmd.AcquisitionId(),
		TaskQueue: taskQueue,
	}

	ctx := context.Background()
	we, err := c.ExecuteWorkflow(ctx, opts, workflows.AcquisitionWorkflow, cmd)
	if err != nil {
		log.Printf("starter: démarrage du Workflow: %v", err)
		return 2
	}
	log.Printf("starter: Workflow démarré (workflow_id=%s, run_id=%s)", we.GetID(), we.GetRunID())

	if *asyncFlag {
		return 0
	}

	var result acquisitionv1.AcquisitionResult
	if err := we.Get(ctx, &result); err != nil {
		log.Printf("starter: exécution du Workflow: %v", err)
		return 1
	}

	out, err := json.MarshalIndent(&result, "", "  ")
	if err != nil {
		log.Printf("starter: sérialisation du résultat: %v", err)
		return 2
	}
	fmt.Println(string(out))

	switch result.FinalState {
	case acquisitionv1.FinalState_SUCCESS, acquisitionv1.FinalState_UNCHANGED:
		return 0
	default:
		return 1
	}
}

func envOr(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}
