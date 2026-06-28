// Écriture du brut produit par le moteur navigateur : artefacts (HTML rendu, échange HTTP
// sérialisé) + manifest JSON décrivant l'acquisition (= AcquisitionResult).
//
// Équivalent TypeScript (local, dev) de platform/storage (sink.go + local.go + store.go).
// N'IMPORTE JAMAIS Temporal. Le sink local reproduit la clé objet comme arborescence de
// dossiers sous une racine (DATA_DIR, défaut ./data) et renvoie une URI file://.

import { mkdir, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { ArtifactKind } from "../../../contracts/gen/ts/acquisitionv1/enums.js";
import type { Artifact } from "../../../contracts/gen/ts/acquisitionv1/artifact.js";
import { FinalState } from "../../../contracts/gen/ts/acquisitionv1/enums.js";
import {
  acquisitionId,
  type AcquisitionCommand,
} from "../../../contracts/gen/ts/acquisitionv1/command.js";
import type { AcquisitionResult } from "../../../contracts/gen/ts/acquisitionv1/result.js";
import type { FetchResult } from "./BrowserFetcher.js";
import { objectKey, sha256Hex } from "./validate.js";

// Noms d'objets standard d'une acquisition, relatifs au préfixe d'acquisition.
// Identiques à platform/storage (store.go).
export const NAME_RESPONSE = "response.bin"; // corps brut / HTML rendu
export const NAME_HTTP_EXCHANGE = "http_exchange.json"; // échange HTTP sérialisé
export const NAME_MANIFEST = "manifest.json"; // manifest JSON (= AcquisitionResult)

// DEFAULT_DATA_DIR — racine locale par défaut si DATA_DIR n'est pas défini (aligné Go).
export const DEFAULT_DATA_DIR = "./data";

// Blob — un artefact prêt à être écrit : nom (dernier segment de la clé objet), contenu,
// type MIME et nature (ArtifactKind). Équivalent du Blob Go.
export interface Blob {
  name: string;
  data: Buffer;
  contentType: string;
  kind: ArtifactKind;
}

// Sink — frontière d'écriture du brut : un magasin d'objets adressés par clé. Write dépose
// `data` sous la clé `key` et renvoie l'URI absolue de l'objet écrit. Équivalent de
// l'interface Sink Go (storage/sink.go).
export interface Sink {
  write(
    key: string,
    data: Buffer,
    contentType: string,
    meta: Record<string, string>,
  ): Promise<string>;
}

// LocalSink écrit les objets sous une racine du système de fichiers, en reproduisant la clé
// comme arborescence de dossiers (équivalent de LocalSink Go, local.go). Les métadonnées
// n'ont pas d'équivalent natif sur disque : elles sont ignorées (portées par le manifest).
export class LocalSink implements Sink {
  readonly root: string;

  constructor(root?: string) {
    const r = (root ?? process.env["DATA_DIR"] ?? "").trim();
    this.root = r === "" ? DEFAULT_DATA_DIR : r;
  }

  async write(
    key: string,
    data: Buffer,
    _contentType: string,
    _meta: Record<string, string>,
  ): Promise<string> {
    const root = this.root.trim() === "" ? DEFAULT_DATA_DIR : this.root;

    // La clé est une suite de segments séparés par '/'. On la transforme en chemin natif
    // sous root, sans jamais permettre de remonter au-dessus de root.
    const rel = key.replace(/^\/+/, "").split("/").join(sep);
    const dest = join(root, rel);

    const absRoot = resolve(root);
    const absDest = resolve(dest);

    // Garde-fou anti-évasion d'arborescence (la clé ne doit pas sortir de root).
    if (absDest !== absRoot && !absDest.startsWith(absRoot + sep)) {
      throw new Error(
        `storage(local): clé ${JSON.stringify(key)} sort de la racine ${JSON.stringify(absRoot)}`,
      );
    }

    await mkdir(dirname(absDest), { recursive: true });
    await writeFile(absDest, data);

    return fileURI(absDest);
  }
}

// fileURI construit une URI file:// portable à partir d'un chemin absolu (gère le préfixe
// Windows : file:///D:/...). Équivalent de fileURI Go.
function fileURI(abs: string): string {
  const p = isAbsolute(abs) ? abs : resolve(abs);
  return pathToFileURL(p).toString();
}

// blobsFromFetch construit la liste standard d'artefacts d'une acquisition navigateur à
// partir d'un FetchResult : le HTML rendu (RENDERED_DOCUMENT) et l'échange HTTP sérialisé en
// JSON (HTTP_EXCHANGE). Équivalent de BlobsFromFetch Go, adapté au mode navigateur
// (RENDERED_DOCUMENT = DOM après JS, cf. artifact.proto) plutôt que RAW_RESPONSE.
export function blobsFromFetch(res: FetchResult): Blob[] {
  if (!res) {
    throw new Error("storage: FetchResult nil");
  }

  const contentType =
    res.contentType && res.contentType !== ""
      ? res.contentType
      : "application/octet-stream";

  const blobs: Blob[] = [
    {
      name: NAME_RESPONSE,
      data: res.body,
      contentType,
      kind: ArtifactKind.RENDERED_DOCUMENT,
    },
  ];

  if (res.exchange) {
    const exchangeJSON = Buffer.from(
      JSON.stringify(res.exchange, null, 2),
      "utf-8",
    );
    blobs.push({
      name: NAME_HTTP_EXCHANGE,
      data: exchangeJSON,
      contentType: "application/json",
      kind: ArtifactKind.HTTP_EXCHANGE,
    });
  }

  return blobs;
}

// storeResult écrit le brut d'une acquisition et son manifest, puis renvoie le
// AcquisitionResult complet (artefacts avec clé/URI/taille/empreinte renseignées).
// Déroulé identique à StoreResult Go (store.go) :
//   1. chaque Blob est écrit via le Sink sous sa clé objet (objectKey) ;
//   2. les métadonnées d'Artifact sont calculées (sha256, taille, clé, URI) ;
//   3. le AcquisitionResult est assemblé (état final, mode, échange, observed_at UTC) ;
//   4. le manifest (ce même résultat, en JSON) est écrit comme dernier objet.
export async function storeResult(
  sink: Sink,
  cmd: AcquisitionCommand,
  res: FetchResult,
  blobs: Blob[],
  finalState: FinalState,
  reasons: string[],
): Promise<AcquisitionResult> {
  if (!sink) {
    throw new Error("storage: sink nil");
  }
  if (!cmd) {
    throw new Error("storage: commande nil");
  }
  if (!res) {
    throw new Error("storage: FetchResult nil");
  }

  const observedAt = new Date().toISOString();

  const artifacts: Artifact[] = [];
  for (const b of blobs) {
    const key = objectKey(cmd, b.name);
    const uri = await sink.write(
      key,
      b.data,
      b.contentType,
      manifestMeta(cmd, finalState),
    );
    artifacts.push({
      kind: b.kind,
      content_type: b.contentType,
      size: b.data.length,
      sha256: sha256Hex(b.data),
      key,
      uri,
    });
  }

  const error = joinReasons(finalState, reasons);
  const result: AcquisitionResult = {
    acquisition_id: acquisitionId(cmd),
    final_state: finalState,
    mode: res.mode,
    artifacts,
    http_exchange: res.exchange,
    observed_at: observedAt,
    // `error` omis quand vide (proto3 JSON / omitempty Go), renseigné sinon.
    ...(error !== "" ? { error } : {}),
  };

  // Le manifest décrit l'acquisition complète : on l'écrit comme dernier objet, sous la même
  // arborescence (raw/.../<acquisition_id>/manifest.json).
  const manifestJSON = Buffer.from(JSON.stringify(result, null, 2), "utf-8");
  const manifestKey = objectKey(cmd, NAME_MANIFEST);
  await sink.write(
    manifestKey,
    manifestJSON,
    "application/json",
    manifestMeta(cmd, finalState),
  );

  return result;
}

// manifestMeta produit les métadonnées objet attachées à chaque écriture (équivalent Go).
function manifestMeta(
  cmd: AcquisitionCommand,
  state: FinalState,
): Record<string, string> {
  return {
    "acquisition-id": acquisitionId(cmd),
    "final-state": state,
  };
}

// joinReasons ne remonte des raisons dans le champ error que pour les états non-succès, afin
// que `error` reste vide quand tout va bien (proto3 JSON : champ omis). Équivalent Go.
function joinReasons(state: FinalState, reasons: string[]): string {
  if (state === FinalState.SUCCESS || state === FinalState.UNCHANGED) {
    return "";
  }
  if (reasons.length === 0) {
    return "";
  }
  return reasons.join("; ");
}
