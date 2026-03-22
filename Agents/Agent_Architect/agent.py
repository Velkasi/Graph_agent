"""
agent.py — Agent Architect
---------------------------
Premier agent de la pipeline multi-agents.

Utilise create_react_agent (LangGraph) avec 3 tools :
    - scan_template_tree  : lit l'arborescence d'un template existant
    - read_template_file  : lit un fichier du template
    - create_project_file : crée un fichier sur le disque (fichiers vides ou avec contenu)

Boucle d'exécution :
    main.py collecte les 19 réponses du discovery → les envoie en bloc au LLM
    LLM produit le récapitulatif → attend confirmation
    Après "oui" → LLM appelle create_project_file pour chaque artefact
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from Agents.base_agent import BaseAgent
from Agents.Agent_Architect.tools import scan_template_tree, read_template_file, create_project_file


SYSTEM_PROMPT = """Tu es Agent_Architect, premier agent d'une pipeline multi-agents pour SaaS mobiles.

SÉQUENCE :
1. Reçois les réponses du discovery
2. Produis le récapitulatif, termine par "Ce récapitulatif est-il correct ?"
3. Attends confirmation — ne génère rien avant

QUAND ON TE DEMANDE spec.json :
Réponds UNIQUEMENT avec le JSON brut, complet, sans texte autour ni balises markdown.
Inclus : version, project, stack, auth, roles, features, database (tables+champs+rls), screens, hooks, components, abstractions, deferredDecisions.
Tables : id uuid PK, organization_id uuid NOT NULL, created_at, updated_at.
RLS multi-tenant : WHERE organization_id = (auth.jwt()->>'org_id')::uuid

QUAND ON TE DEMANDE README.md :
Réponds UNIQUEMENT avec le Markdown complet.

QUAND ON TE DEMANDE migration.sql :
Réponds UNIQUEMENT avec le SQL complet (extensions → organizations → users → tables métier → RLS → triggers).

QUAND ON TE DEMANDE de créer les fichiers vides :
Utilise create_project_file pour chaque fichier .tsx/.ts listé.
content="" OBLIGATOIRE pour tous les fichiers TypeScript.
Un appel par fichier.
"""


class AgentArchitect(BaseAgent):
    """
    Agent Architect avec tool calling via LangGraph.

    Usage depuis main.py :
        agent = AgentArchitect()
        messages = []
        response, messages = agent.chat(messages, context_discovery)
        # → LLM produit le récapitulatif

        response, messages = agent.chat(messages, "oui")
        # → LLM appelle create_project_file × N et génère les artefacts
    """

    def __init__(self):
        super().__init__("config_groq", agent_name="architect")

        self.tools = [
            scan_template_tree,
            read_template_file,
            create_project_file,
        ]

        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=SystemMessage(content=SYSTEM_PROMPT),
        )

        print(f"[AgentArchitect] Prêt avec {len(self.tools)} tools.")

    def run(self, spec: str, template_path: str, feedback: str = "") -> str:
        """
        Point d'entrée pour le graph (architect_node).

        Args:
            spec          : spec produit sérialisée (JSON string)
            template_path : chemin vers le template Expo
            feedback      : corrections demandées par le ReviewAgent (si retry)

        Returns:
            str — architecture générée (texte libre ou JSON)
        """
        message = f"Voici la spec du projet à architecturer :\n\n{spec}\n\nTemplate : {template_path}"
        if feedback:
            message += f"\n\n{feedback}"
        response, _ = self.chat([], message)
        return response

    def chat(self, messages: list, user_message: str) -> tuple[str, list]:
        """
        Envoie un message à l'agent et retourne sa réponse.
        Passe l'historique complet pour maintenir le contexte entre les tours.

        Args:
            messages     : historique de la conversation (liste de BaseMessage)
            user_message : message de l'utilisateur pour ce tour

        Returns:
            (response_text, updated_messages)
        """
        all_messages = list(messages) + [("human", user_message)]
        result = self.agent.invoke(
            {"messages": all_messages},
            config={"recursion_limit": 150},
        )
        updated_messages = result["messages"]
        response = updated_messages[-1].content
        return response, updated_messages
