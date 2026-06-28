import { AcquisitionMode, FinalState } from "./enums.js";
import type { Artifact } from "./artifact.js";
import type { HttpExchange } from "./http_exchange.js";

// AcquisitionResult — sortie du système (result.proto).
//
// observed_at correspond à google.protobuf.Timestamp dans le .proto ; ici une string
// RFC3339 (UTC), équivalent du proto3 JSON mapping d'un Timestamp et de la sérialisation Go
// d'un time.Time UTC. Clés JSON snake_case, fidèles à la génération Go
// (contracts/gen/go/acquisitionv1/result.go).
export interface AcquisitionResult {
  acquisition_id: string;
  final_state: FinalState;
  mode?: AcquisitionMode; // défini dans enums.ts (command.proto)
  artifacts?: Artifact[];
  http_exchange?: HttpExchange;
  observed_at: string; // RFC3339 / ISO-8601 UTC
  error?: string;
}
