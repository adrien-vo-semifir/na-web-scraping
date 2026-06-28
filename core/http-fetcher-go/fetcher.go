// Package httpfetcher est un moteur d'acquisition HTTP statique (transport).
//
// Il expose une fonction simple « commande → résultat » : Fetch effectue une requête
// GET réelle via net/http, suit les redirections, et capture l'échange HTTP brut
// (HttpExchange) avec ses timings (dns / tls / ttfb / total).
//
// Cœur métier — N'IMPORTE JAMAIS le SDK Temporal (cf. docs/structure-projet.md §1).
// Appelable directement (runner cmd/acquire) ET via une Activity Temporal.
package httpfetcher

import (
	"context"
	"crypto/tls"
	"fmt"
	"io"
	"net/http"
	"net/http/httptrace"
	"strings"
	"time"

	acquisitionv1 "github.com/adrien-vo-semifir/na-web-scraping/contracts/gen/go/acquisitionv1"
)

// DefaultTimeout — délai maximal d'une acquisition (connexion + lecture du corps).
const DefaultTimeout = 30 * time.Second

// DefaultUserAgent — agent par défaut si la commande n'en fournit pas.
const DefaultUserAgent = "na-web-scraping/0.1 (+acquisition; POC)"

// FetchResult — sortie du moteur HTTP, agnostique de l'orchestrateur et du stockage.
//
// Body porte le corps brut de la réponse (l'artefact RAW_RESPONSE) ; Exchange porte
// l'échange HTTP capturé. Status/ContentType/FinalURL sont des raccourcis pratiques.
type FetchResult struct {
	Body        []byte
	Exchange    *acquisitionv1.HttpExchange
	Status      int
	ContentType string
	FinalURL    string
	Mode        acquisitionv1.AcquisitionMode
}

// Fetch acquiert la ressource désignée par cmd.URL en HTTP statique.
//
// Comportement :
//   - méthode GET, redirections suivies (jusqu'à 10, défaut net/http) ;
//   - en-têtes additionnels de la commande appliqués (cmd.Headers), User-Agent par défaut sinon ;
//   - timeout via DefaultTimeout, combiné au context fourni ;
//   - capture de l'HttpExchange : méthode, URL initiale/finale, statut, en-têtes req/resp,
//     protocole, et timings dns/tls/ttfb/total en millisecondes.
//
// Aucune I/O disque ni dépendance externe : ce moteur est pur transport.
func Fetch(ctx context.Context, cmd *acquisitionv1.AcquisitionCommand) (*FetchResult, error) {
	if cmd == nil {
		return nil, fmt.Errorf("httpfetcher: commande nil")
	}
	if strings.TrimSpace(cmd.URL) == "" {
		return nil, fmt.Errorf("httpfetcher: url vide")
	}

	ctx, cancel := context.WithTimeout(ctx, DefaultTimeout)
	defer cancel()

	// Mesures de timing via httptrace. Les instants sont relatifs à `start`.
	var (
		start             = time.Now()
		dnsStart          time.Time
		dnsDone           time.Time
		tlsStart          time.Time
		tlsDone           time.Time
		firstResponseByte time.Time
		gotConn           time.Time
	)
	trace := &httptrace.ClientTrace{
		DNSStart:             func(httptrace.DNSStartInfo) { dnsStart = time.Now() },
		DNSDone:              func(httptrace.DNSDoneInfo) { dnsDone = time.Now() },
		TLSHandshakeStart:    func() { tlsStart = time.Now() },
		TLSHandshakeDone:     func(tls.ConnectionState, error) { tlsDone = time.Now() },
		GotConn:              func(httptrace.GotConnInfo) { gotConn = time.Now() },
		GotFirstResponseByte: func() { firstResponseByte = time.Now() },
	}
	ctx = httptrace.WithClientTrace(ctx, trace)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, cmd.URL, nil)
	if err != nil {
		return nil, fmt.Errorf("httpfetcher: construction de la requête %q: %w", cmd.URL, err)
	}
	applyHeaders(req, cmd.Headers)

	// Snapshot des en-têtes de requête AVANT envoi (le transport peut en ajouter,
	// mais on capture l'intention applicative de façon déterministe).
	requestHeaders := flattenHeaders(req.Header)
	if req.Header.Get("Host") == "" && req.Host != "" {
		requestHeaders["Host"] = req.Host
	}

	client := &http.Client{
		// Pas de timeout global ici : le context (WithTimeout) le porte déjà, ce qui
		// permet l'annulation coopérative et la propagation depuis l'appelant/Activity.
		Transport: defaultTransport(),
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("httpfetcher: requête %q: %w", cmd.URL, err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("httpfetcher: lecture du corps de %q: %w", cmd.URL, err)
	}
	total := time.Now()

	finalURL := cmd.URL
	if resp.Request != nil && resp.Request.URL != nil {
		finalURL = resp.Request.URL.String()
	}
	contentType := resp.Header.Get("Content-Type")

	exchange := &acquisitionv1.HttpExchange{
		Method:          http.MethodGet,
		URL:             cmd.URL,
		FinalURL:        finalURL,
		Status:          int32(resp.StatusCode),
		RequestHeaders:  requestHeaders,
		ResponseHeaders: flattenHeaders(resp.Header),
		Protocol:        resp.Proto,
		Timings:         buildTimings(start, dnsStart, dnsDone, tlsStart, tlsDone, gotConn, firstResponseByte, total),
	}

	return &FetchResult{
		Body:        body,
		Exchange:    exchange,
		Status:      resp.StatusCode,
		ContentType: contentType,
		FinalURL:    finalURL,
		Mode:        acquisitionv1.AcquisitionMode_STATIC,
	}, nil
}

// applyHeaders applique les en-têtes de la commande puis garantit un User-Agent.
func applyHeaders(req *http.Request, headers map[string]string) {
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	if req.Header.Get("User-Agent") == "" {
		req.Header.Set("User-Agent", DefaultUserAgent)
	}
}

// defaultTransport renvoie un transport explicite (timeouts de connexion bornés)
// dérivé du transport par défaut, pour un comportement reproductible.
func defaultTransport() *http.Transport {
	t := http.DefaultTransport.(*http.Transport).Clone()
	t.TLSHandshakeTimeout = 10 * time.Second
	t.ResponseHeaderTimeout = 20 * time.Second
	t.ExpectContinueTimeout = 1 * time.Second
	return t
}

// flattenHeaders aplatit http.Header (multi-valeurs) en map[string]string. Les
// valeurs multiples sont jointes par ", " (sémantique HTTP des en-têtes répétés).
func flattenHeaders(h http.Header) map[string]string {
	out := make(map[string]string, len(h))
	for k, vs := range h {
		out[k] = strings.Join(vs, ", ")
	}
	return out
}

// buildTimings calcule les durées clés en millisecondes (float64), conformément au
// champ `timings` de HttpExchange. Une phase non observée (ex. pas de TLS en HTTP)
// est simplement omise.
func buildTimings(start, dnsStart, dnsDone, tlsStart, tlsDone, gotConn, firstByte, total time.Time) map[string]float64 {
	ms := func(d time.Duration) float64 { return float64(d) / float64(time.Millisecond) }
	t := make(map[string]float64, 5)

	if !dnsStart.IsZero() && !dnsDone.IsZero() {
		t["dns"] = ms(dnsDone.Sub(dnsStart))
	}
	if !tlsStart.IsZero() && !tlsDone.IsZero() {
		t["tls"] = ms(tlsDone.Sub(tlsStart))
	}
	if !gotConn.IsZero() {
		// Délai d'obtention d'une connexion utilisable (DNS + connexion + TLS éventuel),
		// mesuré depuis le début de la requête.
		t["connect"] = ms(gotConn.Sub(start))
	}
	if !firstByte.IsZero() {
		// TTFB mesuré depuis le début de la requête (référence homogène avec `total`).
		t["ttfb"] = ms(firstByte.Sub(start))
	}
	if !total.IsZero() {
		t["total"] = ms(total.Sub(start))
	}
	return t
}
