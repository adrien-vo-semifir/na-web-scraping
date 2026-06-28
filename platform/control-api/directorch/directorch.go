// Package directorch fournit une implémentation « directe » (sans orchestrateur) de la
// frontière server.Orchestrator de l'API de contrôle.
//
// RÉVERSIBILITÉ (docs/structure-projet.md §1 & §7) : ce paquet vit sous platform/ et est
// strictement Temporal-FREE. Il n'importe JAMAIS le SDK Temporal — il exécute la tranche
// d'acquisition EN PROCESSUS via platform/acquire (fetch → validation → écriture du brut),
// exactement comme le runner maison cmd/acquire et l'enveloppe d'Activity Temporal.
//
// Rôle : repli (fallback) du composition root de l'API. Il permet de lancer et de tester
// l'API SANS dépendre d'un frontend Temporal (utile au POC, en dev, ou si l'orchestrateur
// est indisponible). En production, le composition root injecte plutôt l'implémentation
// Temporal (orchestration/temporal/orchestrator), qui exécute l'acquisition de façon
// durable, idempotente et avec reprises — qualités absentes de ce repli synchrone.
package directorch

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
	"github.com/adrien-vo-semifir/na-web-scraping/platform/acquire"
	"github.com/adrien-vo-semifir/na-web-scraping/platform/storage"
)

// Orchestrator est un server.Orchestrator qui exécute l'acquisition en processus, sans
// passer par un orchestrateur externe. Sa méthode Submit satisfait structurellement
// l'interface attendue par platform/control-api/server (interfaces implicites de Go).
type Orchestrator struct {
	sink storage.Sink
}

// New construit le repli avec un Sink injecté (le composition root choisit local ou S3).
func New(sink storage.Sink) *Orchestrator {
	return &Orchestrator{sink: sink}
}

// NewFromEnv construit le repli en sélectionnant le Sink selon la variable d'environnement
// SINK (local | s3, défaut local) — même convention que l'enveloppe d'Activity Temporal,
// de sorte que les deux chemins écrivent le brut de façon identique.
func NewFromEnv(ctx context.Context) (*Orchestrator, error) {
	sink, err := buildSink(ctx)
	if err != nil {
		return nil, fmt.Errorf("directorch: initialisation du sink: %w", err)
	}
	return New(sink), nil
}

// Submit exécute l'acquisition de manière SYNCHRONE et renvoie l'acquisition_id comme
// handle de suivi. Contrairement à l'implémentation Temporal (déclenchement asynchrone +
// reprises durables), tout se fait dans l'appel : à son retour, le brut est écrit.
//
// L'erreur n'est remontée que pour un échec TECHNIQUE (fetch/écriture impossibles) ; un
// état final métier dégradé (BLOCKED, RETRYABLE, PERMANENT) n'est PAS une erreur de
// soumission — il est journalisé et le handle est tout de même renvoyé, l'acquisition
// ayant bien été tentée et tracée. L'appelant peut consulter le manifest pour le détail.
func (o *Orchestrator) Submit(ctx context.Context, cmd *acquisitionv1.AcquisitionCommand) (string, error) {
	if cmd == nil {
		return "", fmt.Errorf("directorch: commande nil")
	}
	if o.sink == nil {
		return "", fmt.Errorf("directorch: sink non initialisé")
	}

	// Borne de sécurité : une soumission directe ne doit pas pendre indéfiniment.
	runCtx, cancel := context.WithTimeout(ctx, 5*time.Minute)
	defer cancel()

	result, err := acquire.Run(runCtx, o.sink, cmd)
	if err != nil {
		return "", fmt.Errorf("directorch: acquisition %q: %w", cmd.URL, err)
	}

	log.Printf("directorch: acquisition terminée (acquisition_id=%s, état=%s, artefacts=%d)",
		result.AcquisitionId, result.FinalState, len(result.Artifacts))

	return result.AcquisitionId, nil
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
