// Package acquire câble la tranche d'acquisition HTTP statique de bout en bout :
// fetch (core) → validation technique (core) → écriture du brut + manifest (platform).
//
// C'est la composition métier réutilisable, partagée par le runner maison
// (cmd/acquire) ET par l'enveloppe d'Activity Temporal — ce qui garantit que les deux
// chemins exécutent EXACTEMENT la même logique. Infrastructure métier :
// N'IMPORTE JAMAIS le SDK Temporal (cf. docs/structure-projet.md §1).
package acquire

import (
	"context"
	"fmt"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
	httpfetcher "github.com/adrien-vo-semifir/na-web-scraping/core/http-fetcher-go"
	"github.com/adrien-vo-semifir/na-web-scraping/core/shared"
	"github.com/adrien-vo-semifir/na-web-scraping/platform/storage"
)

// Run exécute une acquisition complète et renvoie son AcquisitionResult.
//
//  1. httpfetcher.Fetch — requête HTTP réelle + capture de l'échange (core, sans I/O disque) ;
//  2. shared.Validate   — état final normalisé (SUCCESS / BLOCKED / RETRYABLE / PERMANENT) ;
//  3. storage.StoreResult — écriture des artefacts (réponse + échange) et du manifest via le Sink.
//
// Toute l'I/O réseau et disque/S3 est concentrée ici (côté infrastructure). Le résultat
// décrit l'acquisition (artefacts avec clé/URI/empreinte, échange HTTP, état final).
func Run(ctx context.Context, sink storage.Sink, cmd *acquisitionv1.AcquisitionCommand) (*acquisitionv1.AcquisitionResult, error) {
	if sink == nil {
		return nil, fmt.Errorf("acquire: sink nil")
	}
	if cmd == nil {
		return nil, fmt.Errorf("acquire: commande nil")
	}

	fetched, err := httpfetcher.Fetch(ctx, cmd)
	if err != nil {
		return nil, fmt.Errorf("acquire: fetch %q: %w", cmd.URL, err)
	}

	finalState, reasons := shared.Validate(fetched)

	blobs, err := storage.BlobsFromFetch(fetched)
	if err != nil {
		return nil, fmt.Errorf("acquire: préparation des artefacts: %w", err)
	}

	result, err := storage.StoreResult(sink, cmd, fetched, blobs, finalState, reasons)
	if err != nil {
		return nil, fmt.Errorf("acquire: écriture du brut: %w", err)
	}

	return result, nil
}
