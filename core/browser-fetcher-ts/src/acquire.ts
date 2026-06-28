// Runner MAISON du moteur navigateur, totalement indépendant de Temporal.
//
// Il exécute la tranche d'acquisition par rendu navigateur (fetch → validation → écriture du
// brut + manifest) directement, sans démarrer la plateforme ni l'orchestrateur. C'est la
// preuve concrète de la RÉVERSIBILITÉ (docs/structure-projet.md §1 & §3.1) : le moteur de
// core/ est appelable sans Temporal. Aucun import du SDK Temporal.
//
// Pendant TypeScript du runner Go cmd/acquire (main.go), pour le moteur BROWSER.
//
// Usage :
//   npx tsx src/acquire.ts --url https://example.com [--source web] [--dataset pages]
//                          [--config-version v1] [--data-dir ./data]
//
// Sortie : le AcquisitionResult en JSON sur stdout. Code de sortie : 0 si l'état final est
// SUCCESS/UNCHANGED, 1 sinon (BLOCKED / RETRYABLE / PERMANENT), 2 en cas d'erreur technique
// (paramètre invalide, échec de navigation, échec d'écriture).

import { AcquisitionMode } from "../../../contracts/gen/ts/acquisitionv1/enums.js";
import { FinalState } from "../../../contracts/gen/ts/acquisitionv1/enums.js";
import type { AcquisitionCommand } from "../../../contracts/gen/ts/acquisitionv1/command.js";
import type { AcquisitionResult } from "../../../contracts/gen/ts/acquisitionv1/result.js";
import { fetch as browserFetch } from "./BrowserFetcher.js";
import { validate } from "./validate.js";
import {
  LocalSink,
  blobsFromFetch,
  storeResult,
  type Sink,
} from "./storage.js";

// run câble la tranche d'acquisition de bout en bout, comme acquire.Run + StoreResult côté Go :
//   1. browserFetch — navigation + rendu + capture de l'échange (core, sans I/O disque) ;
//   2. validate     — état final normalisé (SUCCESS / BLOCKED / RETRYABLE / PERMANENT) ;
//   3. storeResult  — écriture des artefacts (HTML rendu + échange) et du manifest via le Sink.
async function run(
  sink: Sink,
  cmd: AcquisitionCommand,
): Promise<AcquisitionResult> {
  const fetched = await browserFetch(cmd);
  const { state, reasons } = validate(fetched);
  const blobs = blobsFromFetch(fetched);
  return storeResult(sink, cmd, fetched, blobs, state, reasons);
}

interface Args {
  url: string;
  source: string;
  dataset: string;
  configVersion: string;
  dataDir: string | undefined;
}

// parseArgs lit les drapeaux CLI (forme --flag value ou --flag=value). --url est obligatoire ;
// les autres ont des valeurs par défaut alignées sur le runner Go (web / pages / v1).
function parseArgs(argv: string[]): Args {
  const get = (names: string[]): string | undefined => {
    for (let i = 0; i < argv.length; i++) {
      const a = argv[i];
      for (const n of names) {
        if (a === n) {
          return argv[i + 1];
        }
        if (a !== undefined && a.startsWith(n + "=")) {
          return a.slice(n.length + 1);
        }
      }
    }
    return undefined;
  };

  return {
    url: (get(["--url", "-url"]) ?? "").trim(),
    source: (get(["--source", "-source"]) ?? "web").trim(),
    dataset: (get(["--dataset", "-dataset"]) ?? "pages").trim(),
    configVersion: (get(["--config-version", "-config-version"]) ?? "v1").trim(),
    dataDir: get(["--data-dir", "-data-dir"]),
  };
}

const USAGE =
  "usage: npx tsx src/acquire.ts --url <URL> [--source web] [--dataset pages] [--config-version v1] [--data-dir ./data]";

async function main(): Promise<number> {
  const args = parseArgs(process.argv.slice(2));

  if (args.url === "") {
    process.stderr.write("erreur: --url est obligatoire\n");
    process.stderr.write(USAGE + "\n");
    return 2;
  }

  // Sink local (disque) : reproduit la clé objet sous ./data (ou --data-dir / DATA_DIR).
  const sink = new LocalSink(args.dataDir);

  const cmd: AcquisitionCommand = {
    url: args.url,
    source: args.source,
    dataset: args.dataset,
    mode: AcquisitionMode.BROWSER,
    configuration_version: args.configVersion,
  };

  let result: AcquisitionResult;
  try {
    result = await run(sink, cmd);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`erreur: acquisition: ${msg}\n`);
    return 2;
  }

  process.stdout.write(JSON.stringify(result, null, 2) + "\n");

  switch (result.final_state) {
    case FinalState.SUCCESS:
    case FinalState.UNCHANGED:
      return 0;
    default:
      process.stderr.write(`état final non-succès: ${result.final_state}\n`);
      return 1;
  }
}

main()
  .then((code) => {
    process.exitCode = code;
  })
  .catch((err) => {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`erreur fatale: ${msg}\n`);
    process.exitCode = 2;
  });
