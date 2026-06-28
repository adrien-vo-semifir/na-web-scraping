// Package workflows contient les Workflows Temporal du module, en Go.
//
// Un Workflow est du code d'orchestration DÉTERMINISTE (docs/structure-projet.md §3.3) :
// il décide qui s'exécute quand, avec quels timeouts et quelle politique de reprise,
// mais ne fait JAMAIS d'I/O directe (pas de réseau, pas de disque, pas d'horloge
// système hors API Temporal). Toute l'I/O est déléguée aux Activities.
package workflows

import (
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
)

// ActivityName est le nom d'enregistrement de l'Activity d'acquisition, PARTAGÉ par les
// workers de tous les langages (Go, TypeScript, Python). Le Workflow appelle l'Activity par
// ce NOM (et non par une référence de fonction Go) afin de pouvoir router vers un worker
// d'un autre langage via la Task Queue.
const ActivityName = "AcquireActivity"

// Task Queues par langage de moteur (couture polyglotte — un Worker par langage).
const (
	queueGo      = "acquisition"    // Go : net/http (mode STATIC)
	queueBrowser = "acquisition-ts" // TypeScript : Playwright (mode BROWSER)
	queueFurtif  = "acquisition-py" // Python : curl_cffi (STATIC + en-tête "furtif")
)

// AcquisitionWorkflow orchestre l'acquisition d'une ressource : il ROUTE l'Activity vers le
// worker du langage adapté (selon le mode / les en-têtes) puis l'exécute avec un timeout
// StartToClose de 5 minutes et une reprise plafonnée à 3 tentatives.
//
// Déterminisme : aucune I/O ici. Le Workflow ne fait que choisir la Task Queue, appeler
// l'Activity (par NOM) et renvoyer son résultat ; tout le travail concret (fetch, validation,
// écriture) est dans l'Activity → core/ + platform/, dans le langage du worker ciblé.
func AcquisitionWorkflow(ctx workflow.Context, cmd *acquisitionv1.AcquisitionCommand) (*acquisitionv1.AcquisitionResult, error) {
	opts := workflow.ActivityOptions{
		TaskQueue:           taskQueueFor(cmd),
		StartToCloseTimeout: 5 * time.Minute,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    time.Minute,
			MaximumAttempts:    3,
		},
	}
	ctx = workflow.WithActivityOptions(ctx, opts)

	var result acquisitionv1.AcquisitionResult
	if err := workflow.ExecuteActivity(ctx, ActivityName, cmd).Get(ctx, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

// taskQueueFor choisit la Task Queue — donc le worker (langage) — qui exécutera l'Activity :
//   - mode BROWSER                 → acquisition-ts (TypeScript, Playwright : rendu JS)
//   - en-tête "furtif" == "true"   → acquisition-py (Python, curl_cffi : impersonation TLS/JA3)
//   - mode STATIC (défaut)         → acquisition    (Go, net/http)
//
// Le Workflow reste en Go quelle que soit la cible : le routage inter-langages passe par la
// Task Queue, jamais par un appel direct (cf. docs/structure-projet.md §3.3).
func taskQueueFor(cmd *acquisitionv1.AcquisitionCommand) string {
	switch {
	case cmd.Mode == acquisitionv1.AcquisitionMode_BROWSER:
		return queueBrowser
	case cmd.Headers["furtif"] == "true":
		return queueFurtif
	default:
		return queueGo
	}
}
