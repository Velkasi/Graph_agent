"""
agent.py — BackendAgent
------------------------
Génère tous les artefacts Supabase du projet :
    - Migration SQL initiale (tables, types, RLS, triggers, indexes)
    - Edge Functions Deno (notifications, webhooks, etc.)
    - README.md du projet
    - .env.example

Modèle : openai/gpt-oss-120b (config_groq)

Rôle dans le pipeline :
    architect → [backend]  (en parallèle avec code_planner)
                    │
                    ▼
              [codegen]  (attend backend + code_planner)

Entrée : spec (entités, rôles, features) + architecture + project_path
Sortie : fichiers écrits dans project_path/supabase/
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from Agents.base_agent import BaseAgent
from Agents.Agent_Backend.tools import write_sql_migration, write_edge_function, write_project_file, append_project_file
from Utils.logger import log


SYSTEM_PROMPT = """Tu es BackendAgent, expert Supabase dans une pipeline de génération d'apps React Native / Expo.

TON RÔLE :
Générer tous les artefacts backend du projet à partir de la spec et de l'architecture fournis.

SÉQUENCE (respecte cet ordre) :
1. Migration SQL  → via append_project_file EN PLUSIEURS APPELS (voir ci-dessous)
2. Edge Functions → via append_project_file EN PLUSIEURS APPELS (voir ci-dessous)
3. README.md      → via write_project_file (contenu court, un seul appel)
4. .env.example   → via write_project_file (contenu court, un seul appel)

RÈGLE CRITIQUE — ÉCRITURE EN CHUNKS :
N'utilise JAMAIS write_sql_migration ni write_edge_function pour de gros contenus.
Utilise append_project_file avec des blocs courts (max ~30 lignes par appel).

Pour la migration SQL (fichier : "supabase/migrations/001_initial_schema.sql") :
  Appel 1 → extensions + fonction update_updated_at_column
  Appel 2 → table organizations + table users
  Appel 3 → tables métier (une ou deux tables par appel)
  Appel N → (continue jusqu'à toutes les tables)
  Appel N+1 → triggers (un ou deux par appel)
  Appel N+2 → indexes
  Appel N+3 → ALTER TABLE ... ENABLE ROW LEVEL SECURITY (toutes tables)
  Appel N+4 → policies RLS (2-3 tables par appel)

Pour chaque Edge Function (fichier : "supabase/functions/<nom>/index.ts") :
  Appel 1 → imports + setup Supabase client
  Appel 2 → logique métier
  Appel 3 → gestion erreurs + serve()

RÈGLES SQL :
- Chaque table : id uuid PK DEFAULT gen_random_uuid(), created_at/updated_at timestamptz DEFAULT now()
- Foreign keys avec ON DELETE CASCADE
- RLS sur toutes les tables métier
- Index sur user_id, project_id, status

RÈGLES EDGE FUNCTIONS :
- TypeScript / Deno uniquement
- Import : import { createClient } from "https://esm.sh/@supabase/supabase-js@2"
- Réponses HTTP : 400, 401, 500

RÈGLES README :
- Description, Stack, Installation, Variables d'environnement, Structure du projet
- Commandes : supabase start, supabase db push, supabase functions serve

RÈGLES .env.example :
- EXPO_PUBLIC_SUPABASE_URL=your-project-url
- EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
- SUPABASE_SERVICE_ROLE_KEY=your-service-role-key"""


class AgentBackend(BaseAgent):
    """
    BackendAgent — génère la migration SQL, les Edge Functions, le README et .env.example.

    Usage depuis graph.py (backend_node) :
        agent = AgentBackend()
        agent.run(
            spec={"app_name": "...", "data_entities": [...], ...},
            architecture={"raw": "..."},
            project_path="/chemin/absolu/du/projet"
        )
    """

    def __init__(self):
        super().__init__("config_groq", agent_name="backend")

        self.tools = [
            write_sql_migration,
            write_edge_function,
            write_project_file,
            append_project_file,
        ]

        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=SystemMessage(content=SYSTEM_PROMPT),
        )

        log("backend", "INFO", f"Prêt avec {len(self.tools)} tools.")

    def run(self, spec: dict, architecture: dict, project_path: str, discovery_context: str = "") -> dict:
        """
        Génère tous les artefacts backend du projet.

        Args:
            spec         : spec du PlannerAgent (entités, rôles, features, auth)
            architecture : architecture du ArchitectAgent
            project_path : chemin absolu du projet cible

        Returns:
            dict — résumé des fichiers créés {"files_created": [...]}
        """
        entities  = spec.get("data_entities", [])
        roles     = spec.get("roles", [])
        features  = spec.get("features", [])
        app_name  = spec.get("app_name", "App")
        auth      = spec.get("auth", False)
        arch_raw  = architecture.get("raw", str(architecture))

        message = (
            f"Génère tous les artefacts Supabase pour le projet suivant.\n\n"
            f"Chemin absolu du projet : {project_path}\n\n"
            f"SPEC :\n"
            f"  App         : {app_name}\n"
            f"  Entités     : {', '.join(entities)}\n"
            f"  Rôles       : {', '.join(roles)}\n"
            f"  Features    : {', '.join(features)}\n"
            f"  Auth        : {auth}\n\n"
            f"ARCHITECTURE :\n{arch_raw[:2000]}\n\n"
            f"Génère maintenant dans l'ordre : migration SQL → Edge Functions → README → .env.example"
        )
        if discovery_context:
            message += f"\n\nCONTEXTE DISCOVERY (services tiers, contraintes, conformité) :\n{discovery_context}"

        log("backend", "INFO", "Génération des artefacts Supabase...")
        result = self.agent.invoke(
            {"messages": [("human", message)]},
            config={"recursion_limit": 80},
        )

        # Compter les appels tools réussis pour le résumé
        files_created = []
        for msg in result["messages"]:
            if hasattr(msg, "content") and "[OK]" in str(msg.content):
                for line in str(msg.content).split("\n"):
                    if "[OK]" in line:
                        files_created.append(line.replace("[OK] ", "").split(" (")[0])

        log("backend", "OK", f"{len(files_created)} fichier(s) créé(s)")
        for f in files_created:
            log("backend", "INFO", f"  · {f}")

        return {"files_created": files_created}
