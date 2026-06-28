// Validation technique du résultat + dérivation de la clé objet + empreinte de contenu.
//
// Équivalent TypeScript de core/shared (shared.go) : mêmes règles de validation, même
// convention de clé objet, même empreinte SHA-256. Cœur métier — N'IMPORTE JAMAIS Temporal.

import { createHash } from "node:crypto";
import { FinalState } from "../../../contracts/gen/ts/acquisitionv1/enums.js";
import {
  acquisitionId,
  type AcquisitionCommand,
} from "../../../contracts/gen/ts/acquisitionv1/command.js";
import type { FetchResult } from "./BrowserFetcher.js";

// sha256Hex renvoie l'empreinte SHA-256 du contenu, en hexadécimal minuscule.
// Utilisé pour la déduplication et le contrôle d'intégrité des artefacts.
export function sha256Hex(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex");
}

// objectKey construit la clé objet d'un artefact selon la convention du lac :
//
//   raw/<source>/<dataset>/<YYYY-MM-DD>/<acquisition_id>/<name>
//
// La date (UTC) est celle du jour d'acquisition. `source` et `dataset` absents sont
// remplacés par "_" pour garder une arborescence stable et non vide. Strictement équivalent
// à shared.ObjectKey côté Go.
export function objectKey(cmd: AcquisitionCommand, name: string): string {
  const source = segment(cmd.source);
  const dataset = segment(cmd.dataset);
  const day = utcDay(new Date());
  return ["raw", source, dataset, day, acquisitionId(cmd), name].join("/");
}

// segment normalise un fragment de clé : valeur vide -> "_", sinon nettoyée des séparateurs
// de chemin pour éviter toute injection de niveau d'arborescence (équivalent Go `segment`).
function segment(s: string | undefined): string {
  let v = (s ?? "").trim();
  if (v === "") {
    return "_";
  }
  v = v.replace(/\//g, "_").replace(/\\/g, "_");
  return v;
}

// utcDay formate une date au format YYYY-MM-DD en UTC (équivalent du Format("2006-01-02")
// sur time.Now().UTC() côté Go).
function utcDay(d: Date): string {
  const yyyy = d.getUTCFullYear().toString().padStart(4, "0");
  const mm = (d.getUTCMonth() + 1).toString().padStart(2, "0");
  const dd = d.getUTCDate().toString().padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

// challengeMarkers — signatures textuelles fréquentes de pages de protection.
// Liste identique à core/shared (shared.go) ; l'inventaire CAPTCHA complet vit dans
// docs/audit-captcha/.
const challengeMarkers: string[] = [
  "cf-challenge", // Cloudflare
  "cf_chl_opt", // Cloudflare challenge
  "just a moment...", // Cloudflare interstitiel
  "checking your browser", // anti-bot générique
  "attention required", // Cloudflare 1020 / WAF
  "verifying you are human", // challenge générique
  "enable javascript and cookies",
  "_incapsula_resource", // Imperva / Incapsula
  "distil_r_captcha", // Distil Networks
  "px-captcha", // PerimeterX
  "g-recaptcha", // Google reCAPTCHA
  "h-captcha", // hCaptcha
  "datadome", // DataDome
];

// MAX_CHALLENGE_BYTES — au-delà de cette taille, on considère qu'un corps HTML est un
// contenu réel (et non un challenge), pour éviter les faux positifs. Aligné sur Go (256 Kio).
const MAX_CHALLENGE_BYTES = 256 * 1024;

// isChallenge applique une heuristique simple sur un corps HTML court : un petit document
// HTML contenant un marqueur connu est traité comme un challenge (équivalent Go `isChallenge`).
function isChallenge(res: FetchResult): boolean {
  const ct = res.contentType.toLowerCase();
  const isHTML = ct.includes("text/html") || ct === "";
  if (!isHTML) {
    return false;
  }
  if (res.body.length === 0 || res.body.length > MAX_CHALLENGE_BYTES) {
    return false;
  }
  const lower = res.body.toString("utf-8").toLowerCase();
  return challengeMarkers.some((m) => lower.includes(m));
}

// validate applique la validation TECHNIQUE d'un résultat d'acquisition et renvoie l'état
// final normalisé accompagné des raisons (diagnostic). Règles identiques à shared.Validate :
//   - 403 ou 429                       -> BLOCKED (protection / WAF / rate-limit)
//   - corps ressemblant à un challenge -> BLOCKED (CAPTCHA / JS challenge / interstitiel)
//   - 5xx                              -> RETRYABLE (échec transitoire côté serveur)
//   - autres 4xx                       -> PERMANENT (échec définitif côté requête)
//   - 2xx/3xx sans challenge           -> SUCCESS
export function validate(res: FetchResult | null): {
  state: FinalState;
  reasons: string[];
} {
  if (res === null) {
    return { state: FinalState.PERMANENT, reasons: ["résultat nil"] };
  }

  const status = res.status;

  if (status === 403 || status === 429) {
    return {
      state: FinalState.BLOCKED,
      reasons: [`statut ${status} (protection / limitation)`],
    };
  }
  if (isChallenge(res)) {
    return {
      state: FinalState.BLOCKED,
      reasons: [
        "corps de réponse détecté comme page de challenge (CAPTCHA / JS challenge)",
      ],
    };
  }
  if (status >= 500) {
    return {
      state: FinalState.RETRYABLE,
      reasons: [`statut ${status} (erreur serveur, transitoire)`],
    };
  }
  if (status >= 400) {
    return {
      state: FinalState.PERMANENT,
      reasons: [`statut ${status} (erreur de requête, définitive)`],
    };
  }
  return {
    state: FinalState.SUCCESS,
    reasons: [`statut ${status}, contenu accepté`],
  };
}
