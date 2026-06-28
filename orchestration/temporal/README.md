# orchestration/temporal/ — coordination (SEUL point de couplage Temporal)

**Le seul endroit** du repo qui importe le SDK Temporal. Si on change d'orchestrateur, on **jette ce dossier** ;
`core/`, `platform/` et `contracts/` survivent — c'est le **test de réversibilité**
(cf. [`../../docs/structure-projet.md`](../../docs/structure-projet.md) §1 & §5).

| Sous-dossier | Contenu | Notion Temporal |
|---|---|---|
| `workflows-go/` | orchestration déterministe — **toujours Go** | Workflow |
| `activities/` | une enveloppe **mince** par moteur de `core/`, dans **le langage du moteur** | Activity |
| `worker-bootstrap/` | un point de démarrage **par langage** présent ; poll des Task Queues | Worker · Task Queue |

**Règles structurantes :**
- **Langage de l'enveloppe = langage du moteur** (appel in-process direct à `core/`). Le Workflow reste **Go** quel
  que soit le langage des Activities ; le routage inter-langages passe par la **Task Queue**, pas par un appel direct.
- **Un Worker par langage** (un Worker Temporal est mono-langage).
- Les enveloppes sont **minces** : traduire la commande → appeler `core/` → remonter le résultat. **Aucune logique
  métier ici.**
