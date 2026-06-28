// HttpExchange — échange HTTP brut capturé (requête + réponse complètes), capacité
// transverse du module (http_exchange.proto ; cf. docs/architecture/06-validation-artefacts.md).
//
// Les clés JSON sont en snake_case, identiques au proto3 JSON mapping et à la génération
// Go (contracts/gen/go/acquisitionv1/http_exchange.go).
export interface HttpExchange {
  method: string;
  url: string;
  final_url: string; // après redirections
  status: number; // int32
  request_headers: Record<string, string>;
  response_headers: Record<string, string>;
  timings: Record<string, number>; // dns / tls / ttfb / total (ms), double
  protocol: string; // HTTP/1.1, HTTP/2, HTTP/3
}
