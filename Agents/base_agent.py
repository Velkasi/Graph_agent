"""
base_agent.py
-------------
Classe de base partagée par tous les agents du projet.

Rôle : éviter de répéter le code de connexion au modèle dans chaque agent.
Chaque agent hérite de BaseAgent et lui passe son fichier de config.

Schéma d'héritage :
    BaseAgent  ←  AgentMeteo
    BaseAgent  ←  AgentAutre
    BaseAgent  ←  ...

Exemple d'utilisation (dans un agent enfant) :
    class AgentMeteo(BaseAgent):
        def __init__(self):
            super().__init__("config_local")
            # self.llm est maintenant disponible
"""

from langchain_openai import ChatOpenAI
from Utils.config_loader import load_config


class BaseAgent:
    """
    Classe de base pour tous les agents.

    Responsabilité unique : charger la config et initialiser la connexion
    au modèle LLM (via l'API compatible OpenAI du serveur local).

    Attributs:
        llm (ChatOpenAI): Instance du modèle prête à l'emploi.
        config (dict): La config brute chargée depuis le JSON.
    """

    def __init__(self, config_name: str):
        """
        Initialise le LLM à partir d'un fichier de configuration.

        Args:
            config_name: Nom du fichier config (sans .json)
                         Ex: "config_local" utilise Config/config_local.json
        """
        # 1. Charger la configuration
        self.config = load_config(config_name)

        # 2. Créer la connexion au modèle
        # ChatOpenAI = client LangChain compatible avec l'API OpenAI.
        # On lui passe notre serveur local à la place d'OpenAI.
        # Le serveur local doit exposer l'endpoint /v1/chat/completions
        self.llm = ChatOpenAI(
            model=self.config["model"],
            base_url=self.config["base_url"],   # http://192.168.0.1:12000/v1
            api_key=self.config["api_key"],
            temperature=self.config.get("temperature", 0),
            # temperature=0 → réponses déterministes (pas de hasard)
            # temperature=1 → réponses créatives
        )

        print(f"[BaseAgent] Modèle chargé : {self.config['model']}")
