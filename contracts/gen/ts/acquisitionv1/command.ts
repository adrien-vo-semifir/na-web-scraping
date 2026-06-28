import { createHash } from "node:crypto";
import { AcquisitionMode } from "./enums.js";

// AcquisitionCommand — entrée du système (command.proto).
//
// acquisition_id n'est PAS un champ du message : il est dérivé (url + configuration_version)
// côté code via acquisitionId(), pour garantir l'idempotence. Clés JSON snake_case, fidèles
// à la génération Go (contracts/gen/go/acquisitionv1/command.go).
export interface AcquisitionCommand {
  url: string;
  source?: string; // identifiant logique de la source (optionnel)
  dataset?: string; // jeu de données cible (optionnel)
  mode?: AcquisitionMode; //
  configuration_version?: string; // version de configuration (idempotence)
  headers?: Record<string, string>; // en-têtes additionnels (optionnel)
}

// acquisitionId dérive l'identifiant idempotent d'une acquisition à partir de l'URL et de
// la version de configuration : sha256(url + "|" + configuration_version) tronqué aux 16
// premiers caractères hexadécimaux.
//
// Deux commandes ayant la même URL et la même version de configuration produisent le même
// acquisition_id (idempotence), et donc la même clé objet en stockage. Strictement
// équivalent à AcquisitionCommand.AcquisitionId() côté Go.
export function acquisitionId(cmd: AcquisitionCommand): string {
  const configurationVersion = cmd.configuration_version ?? "";
  const sum = createHash("sha256")
    .update(cmd.url + "|" + configurationVersion)
    .digest("hex");
  return sum.slice(0, 16);
}
