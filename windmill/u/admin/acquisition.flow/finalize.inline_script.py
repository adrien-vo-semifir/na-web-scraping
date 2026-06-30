# Le dernier élément de la boucle = le rang RETENU (chosen) -> résultat unique de l'acquisition.
def main(attempts: list = None):
    if attempts and isinstance(attempts[-1], dict):
        return attempts[-1]
    return {"final_state": "PERMANENT", "error": "aucun rang exécuté"}