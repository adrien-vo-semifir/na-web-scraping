// Package acquisitionv1 (TS) contient les types du contrat d'acquisition.
//
// Ces types sont l'équivalent TypeScript des messages Protobuf de
// contracts/proto/*.proto (package acquisition.v1). Ils sont normalement générés par
// `buf generate` ; comme buf/protoc ne sont pas disponibles dans cet environnement, ils
// sont écrits à la main en restant fidèles aux .proto ET à la génération Go de référence
// (contracts/gen/go/acquisitionv1) : mêmes champs, mêmes valeurs d'enum, noms de champs
// JSON en snake_case identiques au proto3 JSON mapping, enums sérialisées sous leur forme
// nominale (string).
//
// ZÉRO dépendance Temporal (cf. docs/structure-projet.md §1 & §3) : ce paquet est le
// vocabulaire partagé et ne connaît pas l'orchestrateur.

// AcquisitionMode — mode d'acquisition d'une ressource (command.proto).
//
// Représenté par sa forme nominale (string), conformément au proto3 JSON mapping et à la
// sérialisation Go (MarshalJSON renvoie le nom de l'enum).
export enum AcquisitionMode {
  ACQUISITION_MODE_UNSPECIFIED = "ACQUISITION_MODE_UNSPECIFIED",
  STATIC = "STATIC", // HTTP statique (transport)
  BROWSER = "BROWSER", // rendu navigateur
  FILE = "FILE", // téléchargement de fichier
}

// FinalState — état final normalisé d'une acquisition (result.proto).
export enum FinalState {
  FINAL_STATE_UNSPECIFIED = "FINAL_STATE_UNSPECIFIED",
  SUCCESS = "SUCCESS",
  UNCHANGED = "UNCHANGED", // 304 / contenu identique
  RETRYABLE = "RETRYABLE", // échec transitoire
  PERMANENT = "PERMANENT", // échec définitif
  BLOCKED = "BLOCKED", // protection / WAF / challenge
}

// ArtifactKind — nature d'un artefact brut produit par un moteur (artifact.proto).
export enum ArtifactKind {
  ARTIFACT_KIND_UNSPECIFIED = "ARTIFACT_KIND_UNSPECIFIED",
  RAW_RESPONSE = "RAW_RESPONSE", // réponse HTTP brute
  RENDERED_DOCUMENT = "RENDERED_DOCUMENT", // document rendu (DOM après JS)
  PAGE_SNAPSHOT = "PAGE_SNAPSHOT", // capture (snapshot / screenshot)
  DOWNLOADED_FILE = "DOWNLOADED_FILE", // fichier téléchargé
  HTTP_EXCHANGE = "HTTP_EXCHANGE", // échange HTTP sérialisé
}
