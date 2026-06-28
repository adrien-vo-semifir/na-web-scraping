package acquisitionv1

// HttpExchange — échange HTTP brut capturé (requête + réponse complètes), capacité
// transverse du module (http_exchange.proto ; cf. docs/architecture/06-validation-artefacts.md).
type HttpExchange struct {
	Method          string             `json:"method,omitempty"`
	URL             string             `json:"url,omitempty"`
	FinalURL        string             `json:"final_url,omitempty"` // après redirections
	Status          int32              `json:"status,omitempty"`
	RequestHeaders  map[string]string  `json:"request_headers,omitempty"`
	ResponseHeaders map[string]string  `json:"response_headers,omitempty"`
	Timings         map[string]float64 `json:"timings,omitempty"`  // dns / tls / ttfb / total (ms)
	Protocol        string             `json:"protocol,omitempty"` // HTTP/1.1, HTTP/2, HTTP/3
}
