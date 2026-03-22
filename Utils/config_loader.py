"""
config_loader.py
----------------
Utilitaire pour charger les fichiers de configuration JSON.

Chaque agent peut utiliser un modèle différent.
Il suffit de lui passer le nom du fichier config correspondant.

Exemple d'utilisation :
    config = load_config("config_local")
    # → charge Config/config_local.json
"""

import json
from pathlib import Path

# Chemin absolu vers le dossier Config/
# Path(__file__) = ce fichier (Utils/config_loader.py)
# .parent       = dossier Utils/
# .parent       = racine du projet
# / "Config"    = dossier Config/
CONFIG_DIR = Path(__file__).parent.parent / "Config"


def load_config(config_name: str) -> dict:
    """
    Charge un fichier de configuration JSON depuis le dossier Config/.

    Args:
        config_name: Nom du fichier sans l'extension .json
                     Ex: "config_local" → lit Config/config_local.json

    Returns:
        dict: Le contenu du fichier JSON sous forme de dictionnaire.

    Raises:
        FileNotFoundError: Si le fichier de config n'existe pas.
    """
    config_path = CONFIG_DIR / f"{config_name}.json"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config introuvable : {config_path}\n"
            f"Fichiers disponibles : {list(CONFIG_DIR.glob('*.json'))}"
        )

    with open(config_path, encoding="utf-8") as f:
        return json.load(f)
