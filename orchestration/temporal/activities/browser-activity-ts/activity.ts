// Enveloppe d'Activity Temporal du moteur navigateur (core/browser-fetcher-ts).
//
// Une enveloppe d'Activity est MINCE par conception (docs/structure-projet.md §3.3) :
// elle reconstruit la commande, appelle la composition métier de core/ (fetch →
// validation → écriture du brut + manifest), et remonte le résultat. Toute la logique
// d'acquisition vit dans core/ ; cette couche est, avec le reste d'orchestration/temporal/,
// le SEUL endroit autorisé à connaître l'orchestrateur — et encore, ici on n'importe le
// SDK que pour le log d'Activity (Context).
//
// Pendant TypeScript de l'enveloppe Go orchestration/temporal/activities/http-activity-go
// (AcquireActivity), pour le moteur BROWSER. Le routage inter-langages se fait par la
// Task Queue : le Workflow Go appelle ExecuteActivity("AcquireActivity", command,
// {taskQueue:"acquisition-ts"}) pour mode=BROWSER ; ce Worker TS poll cette queue.
//
// RÉVERSIBILITÉ : l'enveloppe importe le SDK Temporal (toléré sous orchestration/temporal/),
// mais le moteur (core/) n'en sait rien. Si l'on abandonne Temporal, on jette ce fichier
// sans toucher à core/browser-fetcher-ts.

import { Context } from "@temporalio/activity";

import type { AcquisitionCommand } from "../../../../contracts/gen/ts/acquisitionv1/command.js";
import { acquisitionId } from "../../../../contracts/gen/ts/acquisitionv1/command.js";
import type { AcquisitionResult } from "../../../../contracts/gen/ts/acquisitionv1/result.js";

import { fetch as browserFetch } from "../../../../core/browser-fetcher-ts/src/BrowserFetcher.js";
import { validate } from "../../../../core/browser-fetcher-ts/src/validate.js";
import {
  LocalSink,
  blobsFromFetch,
  storeResult,
} from "../../../../core/browser-fetcher-ts/src/storage.js";

// AcquireActivity est l'enveloppe d'Activity du moteur navigateur (Chromium/Playwright).
//
// CONVENTION IMPOSÉE : le nom d'enregistrement de cette Activity DOIT être "AcquireActivity"
// (le Workflow Go appelle ExecuteActivity("AcquireActivity", …)). En Temporal TypeScript, le
// nom d'enregistrement est la CLÉ de l'objet `activities` passé au Worker, pas le nom de la
// fonction — le worker-bootstrap enregistre donc { AcquireActivity }. On conserve néanmoins
// ce nom de fonction pour l'aligner sur la clé et sur l'enveloppe Go homonyme.
//
// Déroulé (identique à acquire.Run + StoreResult côté Go, et au runner core/acquire.ts) :
//   1. browserFetch — navigation + rendu + capture de l'échange (core, sans I/O disque) ;
//   2. validate     — état final normalisé (SUCCESS / BLOCKED / RETRYABLE / PERMANENT) ;
//   3. storeResult  — écriture des artefacts (HTML rendu + échange) et du manifest via le Sink.
//
// `command` arrive du data converter JSON sous la forme EXACTE du Go : champs snake_case
// (url, configuration_version, …) et enums en forme nominale ("BROWSER"). Les types du
// contrat (contracts/gen/ts) emploient ces mêmes clés snake_case et des string-enums : la
// désérialisation est donc directe (pas de remapping), et le AcquisitionResult ressort en
// JSON de MÊME forme (snake_case, enums nominales, observed_at RFC3339 "…Z").
//
// Le Sink est un LocalSink : DATA_DIR si défini (cf. NewLocalSink Go / LocalSink TS), sinon
// la racine ./data du worker (résolue par le bootstrap à la racine du module via cwd ou
// DATA_DIR). La MÊME convention de clé objet que le Go est garantie par objectKey/acquisitionId
// de core/, réutilisés tels quels.
export async function AcquireActivity(
  command: AcquisitionCommand,
): Promise<AcquisitionResult> {
  if (!command) {
    throw new Error("AcquireActivity: commande nil");
  }

  // Log d'Activity (no-op hors contexte Temporal, ex. test direct) — seul usage du SDK ici.
  try {
    Context.current().log.info("acquisition démarrée", {
      url: command.url,
      acquisition_id: acquisitionId(command),
    });
  } catch {
    // Hors contexte Temporal (appel direct), Context.current() lève : on l'ignore.
  }

  // Sink local : DATA_DIR (env) prioritaire, sinon ./data relatif au cwd du worker
  // (le bootstrap fixe ce cwd à la racine du module). Convention de clé identique au Go.
  const sink = new LocalSink();

  const fetched = await browserFetch(command);
  const { state, reasons } = validate(fetched);
  const blobs = blobsFromFetch(fetched);
  return storeResult(sink, command, fetched, blobs, state, reasons);
}
