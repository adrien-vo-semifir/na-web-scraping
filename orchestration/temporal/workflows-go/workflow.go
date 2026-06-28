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
	activities "github.com/adrien-vo-semifir/na-web-scraping/orchestration/temporal/activities/http-activity-go"
)

// AcquisitionWorkflow orchestre l'acquisition d'une ressource : il exécute l'Activity
// d'acquisition HTTP statique avec un timeout StartToClose de 5 minutes et une politique
// de reprise plafonnée à 3 tentatives.
//
// Déterminisme : aucune I/O ici. Le Workflow ne fait qu'appeler l'Activity et renvoyer
// son résultat ; tout le travail concret (fetch, validation, écriture) est dans
// l'Activity → core/ + platform/.
func AcquisitionWorkflow(ctx workflow.Context, cmd *acquisitionv1.AcquisitionCommand) (*acquisitionv1.AcquisitionResult, error) {
	opts := workflow.ActivityOptions{
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
	if err := workflow.ExecuteActivity(ctx, activities.AcquireActivity, cmd).Get(ctx, &result); err != nil {
		return nil, err
	}
	return &result, nil
}
