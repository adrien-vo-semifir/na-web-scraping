package storage

import (
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)

// DefaultDataDir — racine locale par défaut si DATA_DIR n'est pas défini.
const DefaultDataDir = "./data"

// LocalSink écrit les objets sous une racine du système de fichiers, en reproduisant
// la clé comme arborescence de dossiers. C'est le sink de développement : un objet
// `raw/web/pages/2026-06-28/<id>/response.bin` devient un fichier du même chemin
// relatif sous Root.
type LocalSink struct {
	// Root est la racine d'écriture. Si vide, DefaultDataDir est utilisé.
	Root string
}

// NewLocalSink construit un LocalSink à partir de l'environnement : la racine est
// DATA_DIR si défini, sinon DefaultDataDir.
func NewLocalSink() *LocalSink {
	root := strings.TrimSpace(os.Getenv("DATA_DIR"))
	if root == "" {
		root = DefaultDataDir
	}
	return &LocalSink{Root: root}
}

// Write matérialise l'objet sur disque et renvoie son URI file://.
//
// Les métadonnées (meta) n'ont pas d'équivalent natif sur un système de fichiers ;
// elles sont ignorées par le LocalSink (elles restent portées par le manifest, qui
// est lui-même écrit comme un objet). Ce comportement est volontaire et documenté.
func (s *LocalSink) Write(key string, data []byte, contentType string, meta map[string]string) (string, error) {
	_ = contentType // non utilisé sur disque ; conservé pour l'homogénéité d'interface
	_ = meta        // idem : pas de métadonnées de fichier en local

	root := s.Root
	if strings.TrimSpace(root) == "" {
		root = DefaultDataDir
	}

	// La clé est une suite de segments séparés par '/'. On la transforme en chemin
	// natif sous Root, sans jamais permettre de remonter au-dessus de Root.
	rel := filepath.FromSlash(strings.TrimLeft(key, "/"))
	dest := filepath.Join(root, rel)

	absRoot, err := filepath.Abs(root)
	if err != nil {
		return "", fmt.Errorf("storage(local): racine %q invalide: %w", root, err)
	}
	absDest, err := filepath.Abs(dest)
	if err != nil {
		return "", fmt.Errorf("storage(local): destination %q invalide: %w", dest, err)
	}
	// Garde-fou anti-évasion d'arborescence (la clé ne doit pas sortir de Root).
	if absDest != absRoot && !strings.HasPrefix(absDest, absRoot+string(os.PathSeparator)) {
		return "", fmt.Errorf("storage(local): clé %q sort de la racine %q", key, absRoot)
	}

	if err := os.MkdirAll(filepath.Dir(absDest), 0o755); err != nil {
		return "", fmt.Errorf("storage(local): création du dossier pour %q: %w", key, err)
	}
	if err := os.WriteFile(absDest, data, 0o644); err != nil {
		return "", fmt.Errorf("storage(local): écriture de %q: %w", key, err)
	}

	return fileURI(absDest), nil
}

// fileURI construit une URI file:// portable à partir d'un chemin absolu (gère le
// préfixe Windows en ajoutant le '/' de tête attendu : file:///D:/...).
func fileURI(abs string) string {
	p := filepath.ToSlash(abs)
	if !strings.HasPrefix(p, "/") {
		p = "/" + p
	}
	u := url.URL{Scheme: "file", Path: p}
	return u.String()
}
