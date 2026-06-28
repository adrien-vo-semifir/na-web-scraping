// Package activities contient les enveloppes d'Activity Temporal du module, en Go.
//
// Une enveloppe d'Activity est MINCE par conception (docs/structure-projet.md §3.3) :
// elle traduit la commande, sélectionne le Sink, appelle la composition métier
// (platform/acquire, qui enchaîne core/ + storage), et remonte le résultat. Toute la
// logique d'acquisition vit dans core/ ; toute l'I/O vit dans platform/. Cette couche
// est le SEUL endroit, avec le reste d'orchestration/temporal/, autorisé à connaître
// l'orchestrateur — et encore, ici on n'importe le SDK que pour le log d'Activity.
package activities

import (
	"context"
	"fmt"
	"os"
	"strings"

	"go.temporal.io/sdk/activity"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
	"github.com/adrien-vo-semifir/na-web-scraping/platform/acquire"
	"github.com/adrien-vo-semifir/na-web-scraping/platform/storage"
)

// AcquireActivity est l'enveloppe d'Activity du moteur HTTP statique.
//
// Elle construit le Sink selon l'environnement (SINK = local | s3, défaut local) puis
// délègue à acquire.Run (fetch → validation → écriture du brut + manifest). Le résultat
// est le AcquisitionResult, sérialisable par le data converter de Temporal (JSON).
//
// L'erreur retournée est une erreur applicative classique ; la politique de reprise
// (retries) est définie côté Workflow, pas ici.
func AcquireActivity(ctx context.Context, cmd *acquisitionv1.AcquisitionCommand) (*acquisitionv1.AcquisitionResult, error) {
	if cmd == nil {
		return nil, fmt.Errorf("AcquireActivity: commande nil")
	}

	// Log d'Activity (no-op hors contexte Temporal, ex. tests) — seul usage du SDK ici.
	if logger := activity.GetLogger(ctx); logger != nil {
		logger.Info("acquisition démarrée", "url", cmd.URL, "acquisition_id", cmd.AcquisitionId())
	}

	sink, err := buildSink(ctx)
	if err != nil {
		return nil, fmt.Errorf("AcquireActivity: initialisation du sink: %w", err)
	}

	result, err := acquire.Run(ctx, sink, cmd)
	if err != nil {
		return nil, fmt.Errorf("AcquireActivity: %w", err)
	}
	return result, nil
}

// buildSink choisit le Sink selon la variable d'environnement SINK (local | s3).
func buildSink(ctx context.Context) (storage.Sink, error) {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("SINK"))) {
	case "", "local":
		return storage.NewLocalSink(), nil
	case "s3":
		return storage.NewS3Sink(ctx)
	default:
		return nil, fmt.Errorf("SINK inconnu %q (attendu: local | s3)", os.Getenv("SINK"))
	}
}
