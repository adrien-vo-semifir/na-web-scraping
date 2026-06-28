// Package orchestrator est l'implémentation Temporal de la frontière d'orchestration
// consommée par l'API de contrôle (platform/control-api/server.Orchestrator).
//
// Il vit sous orchestration/temporal/ : c'est le SEUL endroit autorisé à importer le
// SDK Temporal (docs/structure-projet.md §1). Il ne dépend PAS du paquet server : il
// expose une méthode Submit dont la signature satisfait l'interface attendue de façon
// structurelle (interfaces implicites de Go), si bien que le couplage va bien dans le
// sens platform → (interface), jamais orchestration → platform.
package orchestrator

import (
	"context"
	"fmt"

	"go.temporal.io/sdk/client"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
	workflows "github.com/adrien-vo-semifir/na-web-scraping/orchestration/temporal/workflows-go"
)

// TemporalOrchestrator soumet les commandes d'acquisition en démarrant le Workflow
// AcquisitionWorkflow sur une Task Queue Temporal.
type TemporalOrchestrator struct {
	client    client.Client
	taskQueue string
}

// New construit l'orchestrateur à partir d'un client Temporal déjà connecté et de la
// Task Queue cible. Le client appartient à l'appelant (composition root) qui le ferme.
func New(c client.Client, taskQueue string) *TemporalOrchestrator {
	return &TemporalOrchestrator{client: c, taskQueue: taskQueue}
}

// Dial connecte un client Temporal à `address` et renvoie l'orchestrateur prêt à
// l'emploi, accompagné d'une fonction de fermeture du client.
//
// Ce constructeur encapsule l'usage du SDK Temporal afin que les composition roots
// situés hors de orchestration/temporal/ (ex. platform/control-api/main.go) n'aient
// jamais à importer "go.temporal.io/sdk" directement : ils dépendent de ce paquet,
// préservant le garde-fou de réversibilité (docs/structure-projet.md §1 & §7).
func Dial(address, taskQueue string) (*TemporalOrchestrator, func(), error) {
	c, err := client.Dial(client.Options{HostPort: address})
	if err != nil {
		return nil, nil, fmt.Errorf("orchestrator: connexion à Temporal (%s): %w", address, err)
	}
	return New(c, taskQueue), c.Close, nil
}

// Submit démarre (de façon idempotente) le Workflow d'acquisition et renvoie son
// Workflow ID comme handle de suivi.
//
// Le Workflow ID est dérivé de l'acquisition_id (url + configuration_version) : un
// même couple ne lance pas deux Workflows concurrents (idempotence du déclenchement).
func (o *TemporalOrchestrator) Submit(ctx context.Context, cmd *acquisitionv1.AcquisitionCommand) (string, error) {
	if cmd == nil {
		return "", fmt.Errorf("orchestrator: commande nil")
	}
	opts := client.StartWorkflowOptions{
		ID:        "acquisition-" + cmd.AcquisitionId(),
		TaskQueue: o.taskQueue,
	}
	we, err := o.client.ExecuteWorkflow(ctx, opts, workflows.AcquisitionWorkflow, cmd)
	if err != nil {
		return "", fmt.Errorf("orchestrator: démarrage du Workflow: %w", err)
	}
	return we.GetID(), nil
}
