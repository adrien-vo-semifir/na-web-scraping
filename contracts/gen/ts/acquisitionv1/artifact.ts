import { ArtifactKind } from "./enums.js";

// Artifact — métadonnées d'un artefact déposé dans le store objet (S3 / Ceph RGW)
// (artifact.proto). Clés JSON snake_case, fidèles à la génération Go
// (contracts/gen/go/acquisitionv1/artifact.go).
export interface Artifact {
  kind: ArtifactKind;
  content_type: string;
  size: number; // int64
  sha256: string; // empreinte de contenu (dédup / intégrité)
  key: string; // raw/<source>/<dataset>/<run_date>/<acquisition_id>/<name>
  uri: string; // s3://bucket/key (optionnel)
}
