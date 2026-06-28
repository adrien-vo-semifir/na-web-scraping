// Package shared regroupe les utilitaires techniques communs aux moteurs de core/ :
// validation technique du résultat, empreinte de contenu, dérivation de la clé objet.
//
// Cœur métier — N'IMPORTE JAMAIS le SDK Temporal (cf. docs/structure-projet.md §1).
package shared

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
	"time"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
	httpfetcher "github.com/adrien-vo-semifir/na-web-scraping/core/http-fetcher-go"
)

// Sha256Hex renvoie l'empreinte SHA-256 du contenu, en hexadécimal minuscule.
// Utilisé pour la déduplication et le contrôle d'intégrité des artefacts.
func Sha256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

// ObjectKey construit la clé objet d'un artefact selon la convention du lac :
//
//	raw/<source>/<dataset>/<YYYY-MM-DD>/<acquisition_id>/<name>
//
// La date (UTC) est celle du jour d'acquisition. `source` et `dataset` absents sont
// remplacés par "_" pour garder une arborescence stable et non vide.
func ObjectKey(cmd *acquisitionv1.AcquisitionCommand, name string) string {
	source := segment(cmd.Source)
	dataset := segment(cmd.Dataset)
	day := time.Now().UTC().Format("2006-01-02")
	return strings.Join([]string{
		"raw",
		source,
		dataset,
		day,
		cmd.AcquisitionId(),
		name,
	}, "/")
}

// segment normalise un fragment de clé : valeur vide -> "_", sinon nettoyée des
// séparateurs de chemin pour éviter toute injection de niveau d'arborescence.
func segment(s string) string {
	s = strings.TrimSpace(s)
	if s == "" {
		return "_"
	}
	s = strings.ReplaceAll(s, "/", "_")
	s = strings.ReplaceAll(s, "\\", "_")
	return s
}

// Validate applique la validation TECHNIQUE d'un résultat d'acquisition et renvoie
// l'état final normalisé accompagné des raisons (diagnostic).
//
// Règles (POC, transport HTTP) :
//   - 403 ou 429                       -> BLOCKED (protection / WAF / rate-limit)
//   - corps ressemblant à un challenge -> BLOCKED (CAPTCHA / JS challenge / interstitiel)
//   - 5xx                              -> RETRYABLE (échec transitoire côté serveur)
//   - autres 4xx                       -> PERMANENT (échec définitif côté requête)
//   - 2xx/3xx sans challenge           -> SUCCESS
//
// reasons est toujours renseigné (au moins un message décrivant la décision).
func Validate(res *httpfetcher.FetchResult) (acquisitionv1.FinalState, []string) {
	if res == nil {
		return acquisitionv1.FinalState_PERMANENT, []string{"résultat nil"}
	}

	var reasons []string
	status := res.Status

	switch {
	case status == 403 || status == 429:
		reasons = append(reasons, fmt.Sprintf("statut %d (protection / limitation)", status))
		return acquisitionv1.FinalState_BLOCKED, reasons

	case isChallenge(res):
		reasons = append(reasons, "corps de réponse détecté comme page de challenge (CAPTCHA / JS challenge)")
		return acquisitionv1.FinalState_BLOCKED, reasons

	case status >= 500:
		reasons = append(reasons, fmt.Sprintf("statut %d (erreur serveur, transitoire)", status))
		return acquisitionv1.FinalState_RETRYABLE, reasons

	case status >= 400:
		reasons = append(reasons, fmt.Sprintf("statut %d (erreur de requête, définitive)", status))
		return acquisitionv1.FinalState_PERMANENT, reasons

	default:
		reasons = append(reasons, fmt.Sprintf("statut %d, contenu accepté", status))
		return acquisitionv1.FinalState_SUCCESS, reasons
	}
}

// challengeMarkers — signatures textuelles fréquentes de pages de protection.
// Liste indicative (POC) ; l'inventaire CAPTCHA complet vit dans docs/audit-captcha/.
var challengeMarkers = []string{
	"cf-challenge",            // Cloudflare
	"cf_chl_opt",              // Cloudflare challenge
	"just a moment...",        // Cloudflare interstitiel
	"checking your browser",   // anti-bot générique
	"attention required",      // Cloudflare 1020 / WAF
	"verifying you are human", // challenge générique
	"enable javascript and cookies",
	"_incapsula_resource", // Imperva / Incapsula
	"distil_r_captcha",    // Distil Networks
	"px-captcha", // PerimeterX
	"datadome",   // DataDome
	// NB : "g-recaptcha"/"h-captcha" volontairement EXCLUS — un widget CAPTCHA sur un
	// formulaire légitime n'est PAS une page de blocage (faux positif observé sur semifir.com).
}

// isChallenge applique une heuristique simple sur un corps HTML court : un petit
// document HTML contenant un marqueur connu est traité comme un challenge.
//
// Heuristique volontairement conservatrice (POC) : ne déclenche que sur des corps
// HTML de taille modérée pour éviter les faux positifs sur de gros documents légitimes.
func isChallenge(res *httpfetcher.FetchResult) bool {
	ct := strings.ToLower(res.ContentType)
	isHTML := strings.Contains(ct, "text/html") || ct == ""
	if !isHTML {
		return false
	}
	// Un challenge est typiquement une page COURTE (interstitiel). Au-delà de 64 Kio, on
	// considère qu'il s'agit d'un contenu réel — un gros document légitime peut contenir
	// un widget reCAPTCHA/hCaptcha sans pour autant être une page de blocage.
	const maxChallengeBytes = 64 * 1024
	if len(res.Body) == 0 || len(res.Body) > maxChallengeBytes {
		return false
	}
	lower := strings.ToLower(string(res.Body))
	for _, m := range challengeMarkers {
		if strings.Contains(lower, m) {
			return true
		}
	}
	return false
}
