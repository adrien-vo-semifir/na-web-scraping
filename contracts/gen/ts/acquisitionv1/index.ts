// Barrel du paquet acquisitionv1 (TS) — vocabulaire partagé du contrat d'acquisition.
//
// Équivalent TypeScript des messages Protobuf de contracts/proto/*.proto, fidèle à la
// génération Go de référence (contracts/gen/go/acquisitionv1). ZÉRO dépendance Temporal.
export { AcquisitionMode, FinalState, ArtifactKind } from "./enums.js";
export type { HttpExchange } from "./http_exchange.js";
export type { Artifact } from "./artifact.js";
export type { AcquisitionCommand } from "./command.js";
export { acquisitionId } from "./command.js";
export type { AcquisitionResult } from "./result.js";
