// Package storage écrit le brut produit par les moteurs de core/ : artefacts
// (réponse HTTP, échange HTTP sérialisé) + manifest JSON décrivant l'acquisition.
//
// Infrastructure métier — N'IMPORTE JAMAIS le SDK Temporal (cf. docs/structure-projet.md
// §1 & §3.2). Deux implémentations de Sink sont fournies : LocalSink (disque, dev) et
// S3Sink (store objet S3 : SeaweedFS en POC, Ceph RGW en production). Le code appelant
// (runner cmd/acquire, Activity Temporal) dépend de l'interface Sink, jamais d'une impl.
package storage

// Sink est la frontière d'écriture du brut : un magasin d'objets adressés par clé.
//
// Write dépose `data` sous la clé `key` (convention de lac : voir shared.ObjectKey),
// avec son type MIME et des métadonnées libres, et renvoie l'URI absolue de l'objet
// écrit (file://… en local, s3://bucket/key sur S3). L'implémentation est responsable
// de la création des conteneurs intermédiaires (dossiers locaux, bucket S3 supposé
// existant).
type Sink interface {
	Write(key string, data []byte, contentType string, meta map[string]string) (uri string, err error)
}
