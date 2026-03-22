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

from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from Utils.config_loader import load_config
from Utils.prompt_logger import PromptLogger


class BaseAgent:
    """
    Classe de base pour tous les agents.

    Responsabilité unique : charger la config et initialiser la connexion
    au modèle LLM (via l'API compatible OpenAI du serveur local).

    Attributs:
        llm (ChatOpenAI): Instance du modèle prête à l'emploi.
        config (dict): La config brute chargée depuis le JSON.
    """

    def __init__(self, config_name: str, agent_name: str = ""):
        """
        Initialise le LLM à partir d'un fichier de configuration.

        Args:
            config_name: Nom du fichier config (sans .json)
                         Ex: "config_local" utilise Config/config_local.json
            agent_name:  Nom de l'agent pour les logs de prompts (ex: "planner")
        """
        # 1. Charger la configuration
        self.config = load_config(config_name)

        # 2. Logger de prompts — capture chaque appel LLM dans runs/prompts/
        name       = agent_name or config_name
        session_id = datetime.now().strftime("%H%M%S")
        self._prompt_logger = PromptLogger(agent_name=name, session_id=session_id)

        # 3. Créer la connexion au modèle
        provider = self.config.get("provider", "openai")

        if provider == "anthropic":
            self.llm = ChatAnthropic(
                model=self.config["model"],
                api_key=self.config["api_key"],
                temperature=self.config.get("temperature", 0),
                callbacks=[self._prompt_logger],
            )
        else:
            # ChatOpenAI = client LangChain compatible avec l'API OpenAI.
            # On lui passe notre serveur local à la place d'OpenAI.
            # max_retries gère les 429 rate-limit avec backoff exponentiel automatique.
            self.llm = ChatOpenAI(
                model=self.config["model"],
                base_url=self.config["base_url"],
                api_key=self.config["api_key"],
                temperature=self.config.get("temperature", 0),
                max_retries=self.config.get("max_retries", 2),
                callbacks=[self._prompt_logger],
            )

        print(f"[BaseAgent] Modèle chargé : {self.config['model']} (provider: {provider})")
