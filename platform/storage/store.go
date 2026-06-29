package storage

import (
	"encoding/json"
	"fmt"
	"time"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
	httpfetcher "github.com/adrien-vo-semifir/na-web-scraping/core/http-fetcher-go"
	"github.com/adrien-vo-semifir/na-web-scraping/core/shared"
)

// Noms d'objets standard d'une acquisition, relatifs au préfixe d'acquisition.
const (
	// NameResponse — corps brut de la réponse HTTP (artefact RAW_RESPONSE).
	NameResponse = "response.bin"
	// NameHTTPExchange — échange HTTP sérialisé (artefact HTTP_EXCHANGE).
	NameHTTPExchange = "http_exchange.json"
	// NameManifest — manifest JSON décrivant l'acquisition (= AcquisitionResult).
	NameManifest = "manifest.json"
)

// Blob est un artefact prêt à être écrit : un nom (dernier segment de la clé objet),
// son contenu, son type MIME et sa nature (ArtifactKind). StoreResult écrit chaque
// Blob via le Sink et renseigne les métadonnées d'Artifact correspondantes.
type Blob struct {
	Name        string
	Data        []byte
	ContentType string
	Kind        acquisitionv1.ArtifactKind
}

// BlobsFromFetch construit la liste standard d'artefacts d'une acquisition HTTP
// statique à partir d'un FetchResult : le corps brut (RAW_RESPONSE) et l'échange HTTP
// sérialisé en JSON (HTTP_EXCHANGE). C'est la composition par défaut utilisée par le
// runner et l'Activity ; d'autres moteurs (rendu, fichier) en ajouteraient d'autres.
func BlobsFromFetch(res *httpfetcher.FetchResult) ([]Blob, error) {
	if res == nil {
		return nil, fmt.Errorf("storage: FetchResult nil")
	}

	contentType := res.ContentType
	if contentType == "" {
		contentType = "application/octet-stream"
	}

	blobs := []Blob{
		{
			Name:        NameResponse,
			Data:        res.Body,
			ContentType: contentType,
			Kind:        acquisitionv1.ArtifactKind_RAW_RESPONSE,
		},
	}

	if res.Exchange != nil {
		exchangeJSON, err := json.MarshalIndent(res.Exchange, "", "  ")
		if err != nil {
			return nil, fmt.Errorf("storage: sérialisation de l'échange HTTP: %w", err)
		}
		blobs = append(blobs, Blob{
			Name:        NameHTTPExchange,
			Data:        exchangeJSON,
			ContentType: "application/json",
			Kind:        acquisitionv1.ArtifactKind_HTTP_EXCHANGE,
		})
	}

	return blobs, nil
}

// StoreResult écrit le brut d'une acquisition et son manifest, puis renvoie le
// AcquisitionResult complet (artefacts avec clé/URI/taille/empreinte renseignées).
//
// Déroulé :
//  1. chaque Blob est écrit via le Sink sous sa clé objet (shared.ObjectKey) ;
//  2. les métadonnées d'Artifact sont calculées (sha256, taille, clé, URI) ;
//  3. le AcquisitionResult est assemblé (état final, mode, échange, observed_at UTC) ;
//  4. le manifest (ce même résultat, en JSON) est écrit comme dernier objet.
//
// `finalState` et `reasons` proviennent de shared.Validate. L'écriture est faite ici
// (I/O), conformément à la frontière : le cœur (core/) ne touche jamais au disque/S3.
func StoreResult(
	sink Sink,
	cmd *acquisitionv1.AcquisitionCommand,
	res *httpfetcher.FetchResult,
	blobs []Blob,
	finalState acquisitionv1.FinalState,
	reasons []string,
) (*acquisitionv1.AcquisitionResult, error) {
	if sink == nil {
		return nil, fmt.Errorf("storage: sink nil")
	}
	if cmd == nil {
		return nil, fmt.Errorf("storage: commande nil")
	}
	if res == nil {
		return nil, fmt.Errorf("storage: FetchResult nil")
	}

	observedAt := time.Now().UTC()

	// Zone du lac selon l'issue : succès -> raw (source immuable) ; échec -> rejected (quarantaine).
	zone := shared.Zone(finalState)

	artifacts := make([]*acquisitionv1.Artifact, 0, len(blobs))
	for _, b := range blobs {
		key := shared.ObjectKey(cmd, zone, b.Name)
		uri, err := sink.Write(key, b.Data, b.ContentType, manifestMeta(cmd, finalState))
		if err != nil {
			return nil, fmt.Errorf("storage: écriture de l'artefact %q: %w", b.Name, err)
		}
		artifacts = append(artifacts, &acquisitionv1.Artifact{
			Kind:        b.Kind,
			ContentType: b.ContentType,
			Size:        int64(len(b.Data)),
			Sha256:      shared.Sha256Hex(b.Data),
			Key:         key,
			URI:         uri,
		})
	}

	result := &acquisitionv1.AcquisitionResult{
		AcquisitionId: cmd.AcquisitionId(),
		FinalState:    finalState,
		Mode:          res.Mode,
		Artifacts:     artifacts,
		HttpExchange:  res.Exchange,
		ObservedAt:    observedAt,
		Error:         joinReasons(finalState, reasons),
	}

	// Le manifest décrit l'acquisition complète : on l'écrit comme dernier objet,
	// sous la même zone que ses artefacts (<zone>/.../<acquisition_id>/manifest.json).
	manifestJSON, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("storage: sérialisation du manifest: %w", err)
	}
	manifestKey := shared.ObjectKey(cmd, zone, NameManifest)
	if _, err := sink.Write(manifestKey, manifestJSON, "application/json", manifestMeta(cmd, finalState)); err != nil {
		return nil, fmt.Errorf("storage: écriture du manifest: %w", err)
	}

	return result, nil
}

// manifestMeta produit les métadonnées objet attachées à chaque écriture (utiles
// côté S3 : x-amz-meta-*). Volontairement minimal et non-PII au POC.
func manifestMeta(cmd *acquisitionv1.AcquisitionCommand, state acquisitionv1.FinalState) map[string]string {
	return map[string]string{
		"acquisition-id": cmd.AcquisitionId(),
		"final-state":    state.String(),
	}
}

// joinReasons ne remonte des raisons dans le champ Error que pour les états non-succès,
// afin que `error` reste vide quand tout va bien (proto3 JSON : champ omis).
func joinReasons(state acquisitionv1.FinalState, reasons []string) string {
	if state == acquisitionv1.FinalState_SUCCESS || state == acquisitionv1.FinalState_UNCHANGED {
		return ""
	}
	if len(reasons) == 0 {
		return ""
	}
	out := reasons[0]
	for _, r := range reasons[1:] {
		out += "; " + r
	}
	return out
}
