"""Enveloppe d'Activity Temporal du moteur HTTP statique FURTIF, en Python.

Pendant Python de l'enveloppe Go ``orchestration/temporal/activities/http-activity-go``
(``AcquireActivity``) et de l'enveloppe TS ``http-activity-ts`` : même nom d'Activity,
même contrat JSON, autre moteur. Ici le moteur est ``core/http-fetcher-py`` en mode
FURTIF (curl_cffi, ``impersonate="chrome"``), car ce Worker porte le transport furtif.

Le routage inter-langages passe par la Task Queue : le Workflow Go appelle
``ExecuteActivity("AcquireActivity", command, {taskQueue:"acquisition-py"})`` pour les
acquisitions furtives (mode=STATIC + en-tête furtif) ; ce Worker Python poll
``acquisition-py``.
"""

from .activity import ACTIVITY_NAME, AcquireActivity

__all__ = ["AcquireActivity", "ACTIVITY_NAME"]
