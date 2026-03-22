"""
agent.py — CodegenAgent
------------------------
Écrit le code source de chaque fichier TypeScript/TSX du projet.
Traite les fichiers UN PAR UN — un appel LLM par fichier.

Modèle : openai/gpt-oss-120b (config_groq)

Stratégie "file-by-file" :
    → Pas de tool calls (évite les erreurs 400 JSON parsing)
    → Contexte minimal par appel (respecte la limite 8000 TPM de Groq)
    → Sur retry : régénère uniquement les fichiers vides ou mentionnés dans le feedback

Rôle dans le pipeline :
    [code_planner + backend] → [codegen] → [review]
"""

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from Agents.base_agent import BaseAgent
from Utils.logger import log
from Utils.skill_loader import skills_for_file


SYSTEM_PROMPT = """Tu es CodegenAgent, développeur expert React Native / Expo / Supabase.

TON RÔLE :
Écrire le contenu complet d'UN fichier TypeScript/TSX à la fois.

STACK :
- React Native + Expo Router (routing basé sur les fichiers dans app/)
- Supabase (auth + database)
- TypeScript strict

CONVENTIONS OBLIGATOIRES :
- Imports avec alias @/ (ex: @/lib/supabaseClient, @/hooks/useAuth, @/types)
- Supabase client : import { supabase } from '@/lib/supabaseClient'
- Auth hook : import { useAuth } from '@/hooks/useAuth'
- Types : import { NomType } from '@/types'
- Navigation Expo Router : import { useRouter } from 'expo-router'
- Styles : StyleSheet.create() en bas du fichier, avant export
- Pas de dépendances npm externes (hors React Native, Expo, Supabase, React Query)

PATTERNS PAR TYPE DE FICHIER :

lib/supabaseClient.ts :
  import { createClient } from '@supabase/supabase-js'
  export const supabase = createClient(process.env.EXPO_PUBLIC_SUPABASE_URL!, process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!)

types/index.ts :
  Une interface TypeScript par entité, avec id, created_at, updated_at et les champs métier.

hooks/use*.ts :
  Utilise useState + useEffect pour charger les données depuis Supabase.
  Retourne { data, loading, error } + les fonctions d'action.

screens (app/*.tsx) :
  Composant fonctionnel avec View, Text, TextInput, TouchableOpacity.
  Utilise les hooks correspondants.
  Gère les états loading + error.

components/*.tsx :
  Composant réutilisable, props typées avec interface Props.

FORMAT DE SORTIE :
Réponds UNIQUEMENT avec le code TypeScript/TSX complet.
Pas de texte avant, pas de ``` markdown, pas d'explication après.
Le code doit être complet, compilable et fonctionnel.
"""


class AgentCodegen(BaseAgent):
    """
    CodegenAgent — génère le code de chaque fichier TypeScript/TSX.

    Traite les fichiers un par un depuis le code_plan fourni par CodePlannerAgent.
    Sur retry, ne régénère que les fichiers vides ou mentionnés dans le feedback.

    Usage depuis graph.py (codegen_node) :
        agent = AgentCodegen()
        agent.run(
            code_plan={"files": [{"path": "app/Login.tsx", "logic": "..."}]},
            project_path="/chemin/absolu/du/projet",
            feedback="Problèmes : tous les écrans sont vides"
        )
    """

    def __init__(self):
        super().__init__("config_groq_codegen", agent_name="codegen")
        log("codegen", "INFO", "Prêt — openai/gpt-oss-20b (file-by-file)")

    def run(self, code_plan: dict, project_path: str, feedback: str = "", discovery_context: str = "") -> None:
        all_files = [
            f for f in code_plan.get("files", [])
            if f.get("path", "").endswith((".tsx", ".ts"))
        ]

        if not all_files:
            log("codegen", "WARN", "Plan vide ou aucun fichier TypeScript — rien à générer")
            return

        # Sur retry : cibler uniquement les fichiers vides ou mentionnés dans le feedback
        files_to_generate = self._select_files(all_files, project_path, feedback)
        self._discovery_context = discovery_context
        total = len(files_to_generate)

        if total == 0:
            log("codegen", "INFO", "Tous les fichiers sont déjà remplis")
            return

        log("codegen", "INFO", f"{total} fichier(s) à générer")

        for i, file_spec in enumerate(files_to_generate, 1):
            path = file_spec.get("path", "")
            log("codegen", "INFO", f"[{i}/{total}] {path}")
            code = self._generate_file(file_spec, feedback)
            if code:
                self._write(project_path, path, code)

        log("codegen", "OK", f"Génération terminée — {total} fichier(s) écrits")

    def _select_files(self, files: list, project_path: str, feedback: str) -> list:
        """Sur un retry, ne sélectionne que les fichiers vides ou mentionnés."""
        if not feedback:
            return files  # premier run : tout générer

        selected = []
        for file_spec in files:
            path_str = file_spec.get("path", "")
            full_path = Path(project_path) / path_str
            is_empty = not full_path.exists() or full_path.stat().st_size == 0
            in_feedback = path_str in feedback or Path(path_str).name in feedback
            if is_empty or in_feedback:
                selected.append(file_spec)

        log("codegen", "INFO", f"Retry : {len(selected)}/{len(files)} fichiers ciblés par le feedback")
        return selected

    def _generate_file(self, file_spec: dict, feedback: str) -> str:
        """Appel LLM pour générer le contenu d'un fichier."""
        path        = file_spec.get("path", "")
        description = file_spec.get("description", "")
        imports     = file_spec.get("imports", [])
        logic       = file_spec.get("logic", "")
        file_type   = file_spec.get("type", "")

        message = (
            f"Fichier à écrire : {path}\n"
            f"Type : {file_type}\n"
            f"Description : {description}\n"
            f"Imports à utiliser : {', '.join(imports) if imports else 'standards React Native + Expo'}\n"
            f"Logique : {logic}"
        )
        discovery = getattr(self, "_discovery_context", "")
        if discovery:
            message += f"\n\nCONTEXTE PROJET (contraintes discovery) :\n{discovery}"
            skills = skills_for_file(file_type, discovery)
            if skills:
                message += f"\n\n{skills}"
        if feedback:
            message += f"\n\nFeedback du ReviewAgent (corrections à appliquer) :\n{feedback}"

        try:
            response = self.llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=message),
            ])
            return response.content.strip()
        except Exception as e:
            log("codegen", "ERROR", f"Échec LLM pour {path} : {e}")
            return ""

    def _write(self, project_path: str, relative_path: str, content: str) -> None:
        """Écrit le contenu généré dans le fichier."""
        path = Path(project_path) / relative_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            log("codegen", "OK", f"  ✓ {relative_path} ({len(content)} chars)")
        except Exception as e:
            log("codegen", "ERROR", f"  ✗ {relative_path} : {e}")
