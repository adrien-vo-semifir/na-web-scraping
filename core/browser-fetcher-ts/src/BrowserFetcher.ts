// BrowserFetcher est un moteur d'acquisition par RENDU NAVIGATEUR (Playwright/Chromium).
//
// Il expose une fonction simple « commande → résultat » : fetch ouvre une page Chromium
// headless, navigue vers l'URL (page.goto avec waitUntil), récupère le HTML rendu (DOM
// après exécution du JS) via page.content(), et capture l'échange HTTP brut (HttpExchange)
// depuis la réponse principale (status, en-têtes requête/réponse, protocole, timings).
//
// Cœur métier — N'IMPORTE JAMAIS le SDK Temporal (cf. docs/structure-projet.md §1).
// Appelable directement (runner src/acquire.ts) ET, à terme, via une Activity Temporal.
//
// Équivalent navigateur du moteur Go core/http-fetcher-go : même forme de FetchResult,
// même HttpExchange, mode BROWSER au lieu de STATIC.

import { chromium } from "playwright";
import type { Browser, Page, Request, Response } from "playwright";
import { AcquisitionMode } from "../../../contracts/gen/ts/acquisitionv1/enums.js";
import type { AcquisitionCommand } from "../../../contracts/gen/ts/acquisitionv1/command.js";
import type { HttpExchange } from "../../../contracts/gen/ts/acquisitionv1/http_exchange.js";

// DEFAULT_TIMEOUT_MS — délai maximal d'une acquisition (navigation + rendu), en ms.
// Aligné sur DefaultTimeout (30 s) du moteur Go.
export const DEFAULT_TIMEOUT_MS = 30_000;

// DEFAULT_USER_AGENT — agent par défaut si la commande n'en fournit pas.
// Aligné sur DefaultUserAgent du moteur Go (na-web-scraping/0.1 (+acquisition; POC)).
export const DEFAULT_USER_AGENT = "na-web-scraping/0.1 (+acquisition; POC)";

// DEFAULT_WAIT_UNTIL — condition d'attente de page.goto. "load" attend l'événement load
// (document + sous-ressources) ; suffisant et déterministe pour le POC.
const DEFAULT_WAIT_UNTIL: "load" | "domcontentloaded" | "networkidle" | "commit" = "load";

// FetchResult — sortie du moteur navigateur, agnostique de l'orchestrateur et du stockage.
//
// body porte le HTML rendu (l'artefact RENDERED_DOCUMENT / réponse) ; exchange porte
// l'échange HTTP capturé de la réponse principale. status/contentType/finalUrl sont des
// raccourcis pratiques. Forme identique au FetchResult Go (core/http-fetcher-go).
export interface FetchResult {
  body: Buffer;
  exchange: HttpExchange;
  status: number;
  contentType: string;
  finalUrl: string;
  mode: AcquisitionMode;
}

// fetch acquiert la ressource désignée par cmd.url par rendu navigateur (Chromium headless).
//
// Comportement :
//   - lance Chromium headless, applique le User-Agent (commande ou défaut) et les en-têtes
//     additionnels de la commande (cmd.headers) ;
//   - page.goto(url, { waitUntil }) avec timeout DEFAULT_TIMEOUT_MS ;
//   - récupère le HTML rendu via page.content() (DOM sérialisé après exécution du JS) ;
//   - capture l'HttpExchange de la réponse PRINCIPALE : méthode, URL initiale/finale,
//     statut, en-têtes requête/réponse, protocole, timings (connect/ttfb/total en ms) ;
//   - content_type forcé à "text/html" (le rendu produit toujours un document HTML).
//
// Le navigateur est systématiquement fermé (finally). Aucune I/O disque : moteur pur.
export async function fetch(cmd: AcquisitionCommand): Promise<FetchResult> {
  if (!cmd) {
    throw new Error("browserfetcher: commande nil");
  }
  if (!cmd.url || cmd.url.trim() === "") {
    throw new Error("browserfetcher: url vide");
  }

  const start = Date.now();
  let browser: Browser | undefined;

  try {
    browser = await chromium.launch({ headless: true });

    const userAgent =
      pickHeader(cmd.headers, "user-agent") ?? DEFAULT_USER_AGENT;

    // Les en-têtes additionnels de la commande (hors User-Agent, géré nativement) sont
    // appliqués à toutes les requêtes du contexte, comme le fait applyHeaders côté Go.
    const extraHTTPHeaders = headersWithoutUserAgent(cmd.headers);

    const context = await browser.newContext({
      userAgent,
      ...(Object.keys(extraHTTPHeaders).length > 0
        ? { extraHTTPHeaders }
        : {}),
    });
    const page: Page = await context.newPage();
    page.setDefaultNavigationTimeout(DEFAULT_TIMEOUT_MS);

    const response: Response | null = await page.goto(cmd.url, {
      waitUntil: DEFAULT_WAIT_UNTIL,
      timeout: DEFAULT_TIMEOUT_MS,
    });

    if (response === null) {
      // Navigation sans réponse réseau (ex. about:blank, redirection capturée par le SW).
      throw new Error(
        `browserfetcher: aucune réponse réseau pour ${cmd.url}`,
      );
    }

    // HTML rendu : DOM sérialisé après exécution du JavaScript (page.content()).
    const html = await page.content();
    const ttfb = Date.now();

    const request: Request = response.request();
    const finalUrl = response.url();
    const status = response.status();

    const requestHeaders = await safeAllHeaders(() => request.allHeaders());
    // L'intention applicative (User-Agent effectif) reste capturée même si le transport
    // l'a normalisé : on garantit sa présence comme le snapshot Go côté requête.
    if (!hasHeaderCI(requestHeaders, "user-agent")) {
      requestHeaders["user-agent"] = userAgent;
    }
    const responseHeaders = await safeAllHeaders(() => response.allHeaders());

    const body = Buffer.from(html, "utf-8");
    const total = Date.now();

    const exchange: HttpExchange = {
      method: request.method(),
      url: cmd.url,
      final_url: finalUrl,
      status,
      request_headers: requestHeaders,
      response_headers: responseHeaders,
      timings: buildTimings(start, ttfb, total),
      protocol: protocolFromHeaders(responseHeaders),
    };

    return {
      body,
      exchange,
      status,
      // Le rendu navigateur produit toujours un document HTML (DOM sérialisé).
      contentType: "text/html",
      finalUrl,
      mode: AcquisitionMode.BROWSER,
    };
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

// pickHeader recherche (insensible à la casse) la valeur d'un en-tête dans la map fournie.
function pickHeader(
  headers: Record<string, string> | undefined,
  name: string,
): string | undefined {
  if (!headers) {
    return undefined;
  }
  const target = name.toLowerCase();
  for (const [k, v] of Object.entries(headers)) {
    if (k.toLowerCase() === target) {
      return v;
    }
  }
  return undefined;
}

// headersWithoutUserAgent renvoie une copie des en-têtes de la commande sans le User-Agent
// (déjà appliqué via l'option userAgent du contexte, pour éviter un doublon contradictoire).
function headersWithoutUserAgent(
  headers: Record<string, string> | undefined,
): Record<string, string> {
  const out: Record<string, string> = {};
  if (!headers) {
    return out;
  }
  for (const [k, v] of Object.entries(headers)) {
    if (k.toLowerCase() === "user-agent") {
      continue;
    }
    out[k] = v;
  }
  return out;
}

// hasHeaderCI indique si un en-tête (insensible à la casse) est présent dans la map.
function hasHeaderCI(headers: Record<string, string>, name: string): boolean {
  const target = name.toLowerCase();
  return Object.keys(headers).some((k) => k.toLowerCase() === target);
}

// safeAllHeaders exécute un accès aux en-têtes Playwright (asynchrone) et renvoie une map
// vide en cas d'échec, pour ne jamais faire échouer l'acquisition sur la seule capture des
// métadonnées d'échange.
async function safeAllHeaders(
  fn: () => Promise<Record<string, string>>,
): Promise<Record<string, string>> {
  try {
    return await fn();
  } catch {
    return {};
  }
}

// protocolFromHeaders dérive le protocole applicatif. Playwright n'expose pas directement
// la version HTTP de la réponse principale ; on s'appuie sur des indices d'en-têtes, avec
// un défaut HTTP/1.1 (champ informatif, homogène avec le moteur Go). HTTP/2+ ne renvoie pas
// d'en-tête de version, donc l'absence d'indice n'est pas concluante : défaut conservateur.
function protocolFromHeaders(responseHeaders: Record<string, string>): string {
  // Certains proxies/CDN ajoutent un en-tête de version explicite.
  for (const [k, v] of Object.entries(responseHeaders)) {
    const key = k.toLowerCase();
    if (key === "x-firefox-spdy" || key === ":protocol") {
      if (v) {
        return v;
      }
    }
  }
  return "HTTP/1.1";
}

// buildTimings calcule les durées clés en millisecondes (number/double), conformément au
// champ `timings` de HttpExchange. Le rendu navigateur ne donne pas accès aux phases bas
// niveau (dns/tls) de la réponse principale de façon fiable : on expose ttfb (jusqu'à la
// récupération du contenu) et total (jusqu'à la sérialisation), mesurés depuis le début,
// référence homogène avec le moteur Go.
function buildTimings(
  start: number,
  ttfb: number,
  total: number,
): Record<string, number> {
  const t: Record<string, number> = {};
  if (ttfb >= start) {
    t["ttfb"] = ttfb - start;
  }
  if (total >= start) {
    t["total"] = total - start;
  }
  return t;
}
