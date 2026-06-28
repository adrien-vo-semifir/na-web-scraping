// Package acquisitionv1 contient les types du contrat d'acquisition.
//
// Ces types sont l'équivalent Go des messages Protobuf de contracts/proto/*.proto
// (package acquisition.v1). Ils sont normalement générés par `buf generate` ; comme
// buf/protoc ne sont pas disponibles dans cet environnement, ils sont écrits à la
// main en restant fidèles aux .proto (mêmes champs, mêmes valeurs d'enum, noms de
// champs JSON en snake_case identiques au proto3 JSON mapping).
//
// ZÉRO dépendance Temporal (cf. docs/structure-projet.md §1 & §3) : ce paquet est le
// vocabulaire partagé et ne connaît pas l'orchestrateur.
package acquisitionv1

import (
	"fmt"
	"strconv"
)

// AcquisitionMode — mode d'acquisition d'une ressource (command.proto).
type AcquisitionMode int32

const (
	AcquisitionMode_ACQUISITION_MODE_UNSPECIFIED AcquisitionMode = 0
	AcquisitionMode_STATIC                       AcquisitionMode = 1 // HTTP statique (transport)
	AcquisitionMode_BROWSER                      AcquisitionMode = 2 // rendu navigateur
	AcquisitionMode_FILE                         AcquisitionMode = 3 // téléchargement de fichier
)

var acquisitionModeNames = map[AcquisitionMode]string{
	AcquisitionMode_ACQUISITION_MODE_UNSPECIFIED: "ACQUISITION_MODE_UNSPECIFIED",
	AcquisitionMode_STATIC:                       "STATIC",
	AcquisitionMode_BROWSER:                      "BROWSER",
	AcquisitionMode_FILE:                         "FILE",
}

func (m AcquisitionMode) String() string {
	if s, ok := acquisitionModeNames[m]; ok {
		return s
	}
	return "AcquisitionMode(" + strconv.Itoa(int(m)) + ")"
}

// MarshalJSON encode l'enum sous sa forme nominale (proto3 JSON mapping).
func (m AcquisitionMode) MarshalJSON() ([]byte, error) {
	return []byte(strconv.Quote(m.String())), nil
}

// FinalState — état final normalisé d'une acquisition (result.proto).
type FinalState int32

const (
	FinalState_FINAL_STATE_UNSPECIFIED FinalState = 0
	FinalState_SUCCESS                 FinalState = 1
	FinalState_UNCHANGED               FinalState = 2 // 304 / contenu identique
	FinalState_RETRYABLE               FinalState = 3 // échec transitoire
	FinalState_PERMANENT               FinalState = 4 // échec définitif
	FinalState_BLOCKED                 FinalState = 5 // protection / WAF / challenge
)

var finalStateNames = map[FinalState]string{
	FinalState_FINAL_STATE_UNSPECIFIED: "FINAL_STATE_UNSPECIFIED",
	FinalState_SUCCESS:                 "SUCCESS",
	FinalState_UNCHANGED:               "UNCHANGED",
	FinalState_RETRYABLE:               "RETRYABLE",
	FinalState_PERMANENT:               "PERMANENT",
	FinalState_BLOCKED:                 "BLOCKED",
}

func (s FinalState) String() string {
	if n, ok := finalStateNames[s]; ok {
		return n
	}
	return "FinalState(" + strconv.Itoa(int(s)) + ")"
}

// MarshalJSON encode l'enum sous sa forme nominale (proto3 JSON mapping).
func (s FinalState) MarshalJSON() ([]byte, error) {
	return []byte(strconv.Quote(s.String())), nil
}

// ArtifactKind — nature d'un artefact brut produit par un moteur (artifact.proto).
type ArtifactKind int32

const (
	ArtifactKind_ARTIFACT_KIND_UNSPECIFIED ArtifactKind = 0
	ArtifactKind_RAW_RESPONSE              ArtifactKind = 1 // réponse HTTP brute
	ArtifactKind_RENDERED_DOCUMENT         ArtifactKind = 2 // document rendu (DOM après JS)
	ArtifactKind_PAGE_SNAPSHOT             ArtifactKind = 3 // capture (snapshot / screenshot)
	ArtifactKind_DOWNLOADED_FILE           ArtifactKind = 4 // fichier téléchargé
	ArtifactKind_HTTP_EXCHANGE             ArtifactKind = 5 // échange HTTP sérialisé
)

var artifactKindNames = map[ArtifactKind]string{
	ArtifactKind_ARTIFACT_KIND_UNSPECIFIED: "ARTIFACT_KIND_UNSPECIFIED",
	ArtifactKind_RAW_RESPONSE:              "RAW_RESPONSE",
	ArtifactKind_RENDERED_DOCUMENT:         "RENDERED_DOCUMENT",
	ArtifactKind_PAGE_SNAPSHOT:             "PAGE_SNAPSHOT",
	ArtifactKind_DOWNLOADED_FILE:           "DOWNLOADED_FILE",
	ArtifactKind_HTTP_EXCHANGE:             "HTTP_EXCHANGE",
}

func (k ArtifactKind) String() string {
	if n, ok := artifactKindNames[k]; ok {
		return n
	}
	return "ArtifactKind(" + strconv.Itoa(int(k)) + ")"
}

// MarshalJSON encode l'enum sous sa forme nominale (proto3 JSON mapping).
func (k ArtifactKind) MarshalJSON() ([]byte, error) {
	return []byte(strconv.Quote(k.String())), nil
}

// unmarshalEnumJSON décode un enum depuis sa forme nominale ("STATIC") OU numérique (1),
// symétrique de MarshalJSON. Indispensable au round-trip JSON des payloads — notamment
// l'entrée de Workflow Temporal sérialisée puis désérialisée par le data converter.
func unmarshalEnumJSON[E ~int32](data []byte, names map[E]string, dst *E, typ string) error {
	s := string(data)
	if s == "null" {
		return nil // conserve la valeur zéro (UNSPECIFIED)
	}
	if n, err := strconv.Atoi(s); err == nil { // forme numérique proto3
		*dst = E(n)
		return nil
	}
	name, err := strconv.Unquote(s) // forme nominale "STATIC"
	if err != nil {
		return fmt.Errorf("%s: JSON invalide %s: %w", typ, s, err)
	}
	for v, n := range names {
		if n == name {
			*dst = v
			return nil
		}
	}
	return fmt.Errorf("%s: valeur d'enum inconnue %q", typ, name)
}

// UnmarshalJSON — symétrique de MarshalJSON (forme nominale ou numérique).
func (m *AcquisitionMode) UnmarshalJSON(data []byte) error {
	return unmarshalEnumJSON(data, acquisitionModeNames, m, "AcquisitionMode")
}

// UnmarshalJSON — symétrique de MarshalJSON (forme nominale ou numérique).
func (s *FinalState) UnmarshalJSON(data []byte) error {
	return unmarshalEnumJSON(data, finalStateNames, s, "FinalState")
}

// UnmarshalJSON — symétrique de MarshalJSON (forme nominale ou numérique).
func (k *ArtifactKind) UnmarshalJSON(data []byte) error {
	return unmarshalEnumJSON(data, artifactKindNames, k, "ArtifactKind")
}

// Verify interface satisfaction at compile time.
var (
	_ fmt.Stringer = AcquisitionMode(0)
	_ fmt.Stringer = FinalState(0)
	_ fmt.Stringer = ArtifactKind(0)
)
