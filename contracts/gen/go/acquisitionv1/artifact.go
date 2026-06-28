package acquisitionv1

// Artifact — métadonnées d'un artefact déposé dans le store objet (S3 / Ceph RGW)
// (artifact.proto).
type Artifact struct {
	Kind        ArtifactKind `json:"kind,omitempty"`
	ContentType string       `json:"content_type,omitempty"`
	Size        int64        `json:"size,omitempty"`
	Sha256      string       `json:"sha256,omitempty"` // empreinte de contenu (dédup / intégrité)
	Key         string       `json:"key,omitempty"`    // raw/<source>/<dataset>/<run_date>/<acquisition_id>/<name>
	URI         string       `json:"uri,omitempty"`    // s3://bucket/key (optionnel)
}
