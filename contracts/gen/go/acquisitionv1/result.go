package acquisitionv1

import "time"

// AcquisitionResult — sortie du système (result.proto).
//
// observed_at correspond à google.protobuf.Timestamp dans le .proto ; ici un
// time.Time (UTC), qui se sérialise en RFC3339 — équivalent du proto3 JSON mapping
// d'un Timestamp.
type AcquisitionResult struct {
	AcquisitionId string          `json:"acquisition_id"`
	FinalState    FinalState      `json:"final_state"`
	Mode          AcquisitionMode `json:"mode,omitempty"`
	Artifacts     []*Artifact     `json:"artifacts,omitempty"`
	HttpExchange  *HttpExchange   `json:"http_exchange,omitempty"`
	ObservedAt    time.Time       `json:"observed_at"`
	Error         string          `json:"error,omitempty"`
}
