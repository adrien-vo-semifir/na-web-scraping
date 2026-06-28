// Command acquire est un RUNNER MAISON, totalement indépendant de Temporal.
//
// Il exécute la tranche d'acquisition (fetch → validation → écriture du brut + manifest)
// directement, sans démarrer la plateforme ni l'orchestrateur. C'est la preuve concrète
// de la RÉVERSIBILITÉ (docs/structure-projet.md §1 & §3.1) : le cœur (core/) et
// l'infrastructure (platform/) sont appelables sans Temporal. Aucun import du SDK Temporal.
//
// Usage :
//
//	go run ./cmd/acquire -url https://example.com [-sink local|s3] [-source web] [-dataset pages]
//
// Sortie : le AcquisitionResult en JSON sur stdout. Code de sortie : 0 si l'état final
// est SUCCESS/UNCHANGED, 1 sinon (BLOCKED / RETRYABLE / PERMANENT), 2 en cas d'erreur
// technique (paramètre invalide, échec réseau, échec d'écriture).
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
	"github.com/adrien-vo-semifir/na-web-scraping/platform/acquire"
	"github.com/adrien-vo-semifir/na-web-scraping/platform/storage"
)

func main() {
	os.Exit(run())
}

func run() int {
	var (
		urlFlag     = flag.String("url", "", "URL à acquérir (obligatoire)")
		sinkFlag    = flag.String("sink", "local", "destination du brut : local | s3")
		sourceFlag  = flag.String("source", "web", "identifiant logique de la source")
		datasetFlag = flag.String("dataset", "pages", "jeu de données cible")
		cfgVerFlag  = flag.String("config-version", "v1", "version de configuration (idempotence)")
	)
	flag.Parse()

	if strings.TrimSpace(*urlFlag) == "" {
		fmt.Fprintln(os.Stderr, "erreur: -url est obligatoire")
		flag.Usage()
		return 2
	}

	ctx := context.Background()

	sink, err := buildSink(ctx, *sinkFlag)
	if err != nil {
		fmt.Fprintf(os.Stderr, "erreur: initialisation du sink %q: %v\n", *sinkFlag, err)
		return 2
	}

	cmd := &acquisitionv1.AcquisitionCommand{
		URL:                  *urlFlag,
		Source:               *sourceFlag,
		Dataset:              *datasetFlag,
		Mode:                 acquisitionv1.AcquisitionMode_STATIC,
		ConfigurationVersion: *cfgVerFlag,
	}

	result, err := acquire.Run(ctx, sink, cmd)
	if err != nil {
		fmt.Fprintf(os.Stderr, "erreur: acquisition: %v\n", err)
		return 2
	}

	out, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "erreur: sérialisation du résultat: %v\n", err)
		return 2
	}
	fmt.Println(string(out))

	switch result.FinalState {
	case acquisitionv1.FinalState_SUCCESS, acquisitionv1.FinalState_UNCHANGED:
		return 0
	default:
		fmt.Fprintf(os.Stderr, "état final non-succès: %s\n", result.FinalState)
		return 1
	}
}

// buildSink instancie le Sink demandé. "local" écrit sous DATA_DIR (défaut ./data) ;
// "s3" vise un store compatible S3 configuré par l'environnement (S3_ENDPOINT…).
func buildSink(ctx context.Context, kind string) (storage.Sink, error) {
	switch strings.ToLower(strings.TrimSpace(kind)) {
	case "", "local":
		return storage.NewLocalSink(), nil
	case "s3":
		return storage.NewS3Sink(ctx)
	default:
		return nil, fmt.Errorf("sink inconnu %q (attendu: local | s3)", kind)
	}
}
