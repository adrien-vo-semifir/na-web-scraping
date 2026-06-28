// Worker bootstrap TypeScript : démarre le Worker TS qui poll la Task Queue du moteur
// navigateur et exécute l'Activity d'acquisition par rendu (core/browser-fetcher-ts).
//
// Composition root de la couche d'orchestration côté TypeScript (docs/structure-projet.md
// §3.3) : c'est l'un des rares mains autorisés à câbler ensemble Temporal et le code métier.
// Un Worker Temporal est mono-langage ; ce bootstrap est celui du langage TS. Le Worker Go
// (worker-bootstrap/main.go) porte les Workflows et l'Activity Go ; CE Worker TS porte
// l'Activity navigateur et poll SA Task Queue. Le routage inter-langages passe par la
// Task Queue (le Workflow Go cible "acquisition-ts" pour mode=BROWSER), pas par un appel
// direct entre Workers.
//
// CONVENTIONS IMPOSÉES (le Workflow Go s'y conforme, NE PAS les changer) :
//   - Nom d'activité enregistré : "AcquireActivity"  (clé de l'objet `activities`)
//   - Task Queue                : "acquisition-ts"
//   - Namespace                 : "default"
//   - Data converter            : JSON par défaut (snake_case, enums nominales)
//
// Configuration par environnement :
//   TEMPORAL_ADDRESS  adresse du frontend Temporal (défaut 127.0.0.1:7233)
//   DATA_DIR          racine d'écriture du brut (défaut : ./data à la racine du module)
//
// Lancement :  npx tsx orchestration/temporal/worker-bootstrap-ts/worker.ts

import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { NativeConnection, Worker } from "@temporalio/worker";

import { AcquireActivity } from "../activities/browser-activity-ts/activity.js";

// TASK_QUEUE — Task Queue du Worker TS. Valeur IMPOSÉE par la convention de routage : le
// Workflow Go appelle ExecuteActivity("AcquireActivity", command, {taskQueue:"acquisition-ts"})
// pour mode=BROWSER. Ne pas paramétrer par env afin de garder le contrat figé.
const TASK_QUEUE = "acquisition-ts";

// NAMESPACE — namespace Temporal. "default" est créé d'office par temporalio/auto-setup
// (cf. compose.yaml), comme côté Go.
const NAMESPACE = "default";

// DEFAULT_TEMPORAL_ADDRESS — frontend Temporal local du POC (cf. compose.yaml, port 7233).
const DEFAULT_TEMPORAL_ADDRESS = "127.0.0.1:7233";

// moduleRoot remonte de orchestration/temporal/worker-bootstrap-ts/ jusqu'à la racine du
// module (web-scraping). Le LocalSink de l'Activity écrit sous `./data` RELATIF au cwd du
// process (même convention que NewLocalSink Go) : on fixe donc le cwd à la racine du module
// pour que le brut atterrisse dans modules/web-scraping/data, quel que soit le répertoire
// depuis lequel `npx tsx …/worker.ts` est lancé. DATA_DIR (env) reste prioritaire et inchangé.
const here = dirname(fileURLToPath(import.meta.url));
const moduleRoot = resolve(here, "..", "..", "..");

async function main(): Promise<void> {
  // Aligne le cwd sur la racine du module : le Sink local de l'Activity dérive `./data`
  // de ce cwd (sauf si DATA_DIR est défini, auquel cas il prime).
  process.chdir(moduleRoot);

  const address = process.env["TEMPORAL_ADDRESS"] ?? DEFAULT_TEMPORAL_ADDRESS;

  // Connexion native (gRPC) au frontend Temporal. La fermeture est gérée à l'arrêt.
  const connection = await NativeConnection.connect({ address });

  try {
    // Data converter JSON par défaut (non surchargé) : le `command` reçu est du JSON à la
    // forme Go (snake_case, enums nominales) et le AcquisitionResult ressort à l'identique.
    const worker = await Worker.create({
      connection,
      namespace: NAMESPACE,
      taskQueue: TASK_QUEUE,
      // Le nom D'ENREGISTREMENT de l'Activity est la CLÉ ci-dessous : "AcquireActivity",
      // exactement ce qu'attend le Workflow Go. (Le nom de la fonction importée coïncide.)
      activities: { AcquireActivity },
    });

    // eslint-disable-next-line no-console
    console.log(
      `worker-bootstrap-ts: Worker TS démarré (temporal=${address}, namespace=${NAMESPACE}, task_queue=${TASK_QUEUE}, activity=AcquireActivity, data_dir=${process.env["DATA_DIR"] ?? resolve(moduleRoot, "data")})`,
    );

    // worker.run() bloque jusqu'à réception d'un signal d'arrêt (SIGINT/SIGTERM, gérés
    // nativement par le SDK) puis effectue un arrêt propre (drain des tâches en cours).
    await worker.run();
  } finally {
    await connection.close();
  }
}

main().catch((err) => {
  const msg = err instanceof Error ? err.stack ?? err.message : String(err);
  // eslint-disable-next-line no-console
  console.error(`worker-bootstrap-ts: arrêt sur erreur:\n${msg}`);
  process.exitCode = 1;
});
