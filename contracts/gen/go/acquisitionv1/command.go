package acquisitionv1

import (
	"crypto/sha256"
	"encoding/hex"
)

// AcquisitionCommand — entrée du système (command.proto).
//
// acquisition_id n'est PAS un champ du message : il est dérivé (url + configuration_version)
// côté code via AcquisitionId(), pour garantir l'idempotence.
type AcquisitionCommand struct {
	URL                  string            `json:"url"`
	Source               string            `json:"source,omitempty"`                // identifiant logique de la source (optionnel)
	Dataset              string            `json:"dataset,omitempty"`               // jeu de données cible (optionnel)
	Mode                 AcquisitionMode   `json:"mode,omitempty"`                  //
	ConfigurationVersion string            `json:"configuration_version,omitempty"` // version de configuration (idempotence)
	Headers              map[string]string `json:"headers,omitempty"`               // en-têtes additionnels (optionnel)
}

// AcquisitionId dérive l'identifiant idempotent d'une acquisition à partir de
// l'URL et de la version de configuration : sha256(url + "|" + configuration_version)
// tronqué aux 16 premiers caractères hexadécimaux.
//
// Deux commandes ayant la même URL et la même version de configuration produisent
// le même acquisition_id (idempotence), et donc la même clé objet en stockage.
func (c *AcquisitionCommand) AcquisitionId() string {
	sum := sha256.Sum256([]byte(c.URL + "|" + c.ConfigurationVersion))
	return hex.EncodeToString(sum[:])[:16]
}
