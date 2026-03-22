"""
agent.py — CodePlannerAgent
----------------------------
Transforme l'architecture en plan de code fichier par fichier.
Chaque entrée du plan indique à CodegenAgent ce qu'il doit écrire dans le fichier.

Modèle : openai/gpt-oss-120b (config_groq)

Rôle dans le pipeline :
    architect → [code_planner]  (en parallèle avec backend)
                     │
                     ▼
               [codegen]  (attend code_planner + backend)

Entrée : architecture (files, screens, project_path) + spec
Sortie : code_plan JSON — liste de fichiers avec leur description et logique
"""

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from Agents.base_agent import BaseAgent
from Utils.logger import log
from Utils.skill_loader import skills_for_stack


SYSTEM_PROMPT = """Tu es CodePlannerAgent, expert React Native / Expo / Supabase.

TON RÔLE :
Produire un plan de code JSON décrivant précisément ce que chaque fichier .tsx/.ts doit contenir.
Ce plan est lu par CodegenAgent pour générer le code.

FORMAT DE SORTIE :
Réponds UNIQUEMENT avec le JSON brut. Pas de markdown, pas de texte autour.

{
  "files": [
    {
      "path": "lib/supabaseClient.ts",
      "type": "lib",
      "description": "Initialise et exporte le client Supabase",
      "imports": [],
      "logic": "createClient avec EXPO_PUBLIC_SUPABASE_URL et EXPO_PUBLIC_SUPABASE_ANON_KEY depuis process.env"
    },
    {
      "path": "types/index.ts",
      "type": "types",
      "description": "Interfaces TypeScript pour toutes les entités de la spec",
      "imports": [],
      "logic": "Une interface par data_entity avec id uuid, created_at, updated_at et tous les champs métier"
    },
    {
      "path": "hooks/useAuth.ts",
      "type": "hook",
      "description": "Hook d'authentification — session, login, logout, register",
      "imports": ["@/lib/supabaseClient"],
      "logic": "useState pour session/loading/error, supabase.auth.signInWithPassword pour login, signUp pour register, signOut pour logout, onAuthStateChange pour écouter les changements"
    },
    {
      "path": "app/Login.tsx",
      "type": "screen",
      "description": "Écran de connexion email + mot de passe",
      "imports": ["@/hooks/useAuth", "@/types"],
      "logic": "Formulaire avec TextInput email + password, bouton Connexion appelle useAuth.login, redirect vers /(tabs) après succès, lien vers Inscription"
    }
  ]
}

ORDRE OBLIGATOIRE dans le plan :
1. lib/supabaseClient.ts  (toujours en premier)
2. types/index.ts
3. hooks/useAuth.ts (en premier parmi les hooks)
4. autres hooks/* (un hook par entité : useProject, useTask, etc.)
5. components/*
6. app/* (écrans)

RÈGLES :
- N'inclure QUE les fichiers .tsx et .ts
- Être précis dans "logic" : nommer les méthodes Supabase, les tables, les navigations Expo Router
- Pour les screens : mentionner la navigation après action (ex: "redirect vers /(tabs) après login")
- Garder "logic" court (2-3 phrases max)
"""


class AgentCodePlanner(BaseAgent):
    """
    CodePlannerAgent — produit un plan JSON décrivant le contenu de chaque fichier.

    Usage depuis graph.py (code_planner_node) :
        agent = AgentCodePlanner()
        code_plan = agent.run(
            architecture={"files": [...], "screens": [...], ...},
            spec={"app_name": "...", "data_entities": [...], ...}
        )
        # → {"files": [{"path": "...", "type": "...", "logic": "..."}, ...]}
    """

    def __init__(self):
        super().__init__("config_groq_codegen", agent_name="code_planner")
        log("code_planner", "INFO", "Prêt — openai/gpt-oss-20b")

    def run(self, architecture: dict, spec: dict, discovery_context: str = "") -> dict:
        ts_files = [
            f for f in architecture.get("files", [])
            if f.endswith((".tsx", ".ts"))
        ]
        screens   = architecture.get("screens", [])
        entities  = spec.get("data_entities", [])
        app_name  = spec.get("app_name", "App")
        features  = spec.get("features", [])

        message = (
            f"Produis le plan de code pour l'application '{app_name}'.\n\n"
            f"Fichiers TypeScript à planifier ({len(ts_files)}) :\n"
            + "\n".join(f"  - {f}" for f in ts_files)
            + f"\n\nÉcrans de la spec : {', '.join(screens)}"
            f"\nEntités (tables Supabase) : {', '.join(entities)}"
            f"\nFeatures : {', '.join(features)}"
            f"\nAuth : {spec.get('auth', True)}, Rôles : {', '.join(spec.get('roles', []))}"
        )
        if discovery_context:
            message += f"\n\nCONTEXTE DISCOVERY (contraintes réelles) :\n{discovery_context}"
            skills = skills_for_stack(discovery_context)
            if skills:
                message += f"\n\n{skills}"

        response = self.llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=message),
        ])
        plan = _parse_plan(response.content)
        n = len(plan.get("files", []))
        log("code_planner", "OK", f"Plan généré — {n} fichiers planifiés")
        return plan


def _parse_plan(text: str) -> dict:
    """Parse le JSON du plan avec 3 stratégies de fallback."""
    strategies = [
        lambda t: json.loads(t),
        lambda t: json.loads(re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL).group(1)),
        lambda t: json.loads(re.search(r"\{.*\}", t, re.DOTALL).group(0)),
    ]
    for strategy in strategies:
        try:
            result = strategy(text)
            if "files" in result:
                return result
        except Exception:
            pass
    log("code_planner", "WARN", "Parse JSON échoué — plan vide retourné")
    return {"files": []}
