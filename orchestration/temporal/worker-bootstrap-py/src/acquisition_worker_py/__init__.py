"""Worker bootstrap Python : composition root du Worker furtif (Task Queue acquisition-py).

Point de démarrage du langage Python de la couche d'orchestration
(docs/structure-projet.md §3.3). Un Worker Temporal est mono-langage : ce bootstrap
porte l'Activity Python ``AcquireActivity`` (moteur HTTP statique furtif) et poll la
Task Queue ``acquisition-py``. Le Worker Go porte les Workflows et l'Activity Go ; le
routage inter-langages passe par la Task Queue, pas par un appel direct entre Workers.
"""

from .worker import NAMESPACE, TASK_QUEUE, main, run

__all__ = ["main", "run", "TASK_QUEUE", "NAMESPACE"]
