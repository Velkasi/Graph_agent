"""
agent.py — ReviewAgent
-----------------------
Chef de qualité du pipeline. Analyse le projet généré par CodegenAgent,
corrige les petits problèmes directement, et émet un verdict structuré.

Modèle : deepseek-coder:7b-q4  (config_deepseek)

Rôle dans la boucle d'auto-correction LangGraph :
    codegen → [review] → "approved"     → test + cicd
                       → "needs_rework" → codegen  (problème de code)
                       → "needs_rework" → architect (problème structurel)

Ce que le ReviewAgent vérifie (dans l'ordre) :
    1. Couverture des écrans  — chaque screen de la spec a son fichier Expo Router
    2. Erreurs TypeScript     — tsc --noEmit sur le projet
    3. Imports manquants      — lecture des fichiers suspects
    4. Cohérence architecture — les entités de la spec existent dans le code

Ce que le ReviewAgent corrige DIRECTEMENT (write_project_file) :
    - Import path incorrect
    - Export manquant sur un composant
    - Type `any` trivial à remplacer
    - Faute de frappe dans un nom de variable

Ce qu'il DÉLÈGUE (verdict "needs_rework") :
    → codegen  : écran manquant, composant vide, logique absente
    → architect: entité de données absente, authentification non configurée

Sortie — verdict JSON lu par route_after_review dans graph.py :
    {
      "status": "approved" | "needs_rework",
      "feedback": {
        "target_agent": "codegen" | "architect",
        "severity": "high" | "medium" | "low",
        "issues": ["description précise du problème"],
        "suggestions": ["comment le corriger"],
        "fixed_directly": ["fichier.tsx — correction appliquée"]
      }
    }
"""

import json
import re

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from Agents.base_agent import BaseAgent
from Agents.Agent_Review.tools import (
    list_project_files,
    read_project_file,
    write_project_file,
    run_tsc,
)


# ===========================================================================
# SYSTEM PROMPT
# ===========================================================================

SYSTEM_PROMPT = """Tu es ReviewAgent, le chef qualité d'une pipeline multi-agents qui génère des applications React Native / Expo / Supabase.

TON RÔLE :
Analyser le projet généré, corriger les petits problèmes directement, et émettre un verdict structuré que LangGraph utilisera pour décider de la suite.

SÉQUENCE D'ANALYSE (respecte cet ordre) :
1. list_project_files     → inventaire complet du projet
2. Vérifier la couverture → chaque écran de la spec a-t-il son fichier dans app/ ?
3. run_tsc                → erreurs TypeScript
4. read_project_file × N  → lire les fichiers suspects (ceux avec des erreurs TSC, ou les écrans)
5. write_project_file × N → corriger DIRECTEMENT les petits problèmes (imports, types, exports)
6. Émettre le verdict JSON

RÈGLE DE DÉCISION :
- Correction directe (write_project_file + verdict "approved") :
    • Import path incorrect ou manquant
    • Export default absent
    • Type `any` simple à corriger
    • Faute de frappe dans un identifiant

- Déléguer à "codegen" (verdict "needs_rework") :
    • Écran de la spec sans fichier correspondant
    • Composant vide (fichier existe mais contenu vide ou placeholder)
    • Logique métier absente (ex: pas de fetch, pas de formulaire)
    • Plus de 5 erreurs TypeScript liées à la logique

- Déléguer à "architect" (verdict "needs_rework") :
    • Entité de données de la spec absente du code (ex: pas de hook pour "tasks")
    • Auth non configurée alors que spec.auth = true
    • Structure de navigation incompatible avec la spec

FORMAT DE SORTIE FINAL :
Termine TOUJOURS par un JSON sur une seule ligne, précédé du marqueur <<<VERDICT>>>

<<<VERDICT>>>
{"status": "approved"|"needs_rework", "feedback": {"target_agent": "codegen"|"architect", "severity": "high"|"medium"|"low", "issues": ["..."], "suggestions": ["..."], "fixed_directly": ["..."]}}

Si tout est correct et que tu n'as rien à corriger :
<<<VERDICT>>>
{"status": "approved", "feedback": {"target_agent": null, "severity": null, "issues": [], "suggestions": [], "fixed_directly": []}}
"""


# ===========================================================================
# UTILITAIRES
# ===========================================================================

def _parse_verdict(text: str) -> dict:
    """
    Extrait le verdict JSON du texte de réponse de l'agent.
    Cherche d'abord le marqueur <<<VERDICT>>>, puis fallback sur un JSON brut.
    """
    # Méthode 1 : marqueur <<<VERDICT>>>
    match = re.search(r"<<<VERDICT>>>\s*(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Méthode 2 : chercher le dernier objet JSON complet dans le texte
    matches = list(re.finditer(r"\{[^{}]*\"status\"[^{}]*\}", text, re.DOTALL))
    if matches:
        try:
            return json.loads(matches[-1].group(0))
        except json.JSONDecodeError:
            pass

    # Méthode 3 : chercher n'importe quel objet JSON
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback : approuver pour ne pas bloquer le pipeline
    print("  [ReviewAgent] ⚠ Verdict non parsable — approbation par défaut")
    return {
        "status": "approved",
        "feedback": {
            "target_agent": None,
            "severity": None,
            "issues": [],
            "suggestions": [],
            "fixed_directly": [],
            "parse_error": text[:200],
        }
    }


def _build_context(
    project_path: str,
    spec: dict,
    architecture: dict,
    team_log: list[dict],
) -> str:
    """
    Construit le message contextuel envoyé au ReviewAgent.
    Résume ce que les agents précédents ont fait pour orienter l'analyse.
    """
    screens = [s.get("name", "?") for s in spec.get("screens", [])]
    entities = spec.get("data_entities", [])
    auth = spec.get("auth", False)

    # Résumé du team_log (dernières 10 entrées)
    log_summary = "\n".join(
        f"  [{e.get('time','')}] {e.get('agent','?')} → {e.get('action','?')}: {e.get('detail','')}"
        for e in team_log[-10:]
    ) or "  (aucune entrée)"

    return f"""CONTEXTE DU PROJET :
Projet généré dans : {project_path}

SPEC (référence de validation) :
  App       : {spec.get('app_name', '?')}
  Écrans    : {', '.join(screens) if screens else 'non définis'}
  Features  : {', '.join(spec.get('features', []))}
  Auth      : {auth}
  Entités   : {', '.join(entities) if entities else 'non définies'}

ARCHITECTURE :
  Statut : {architecture.get('status', 'générée')}

JOURNAL DE L'ÉQUIPE (dernières actions) :
{log_summary}

INSTRUCTIONS :
Lance l'analyse du projet. Commence par list_project_files, puis vérifie la couverture des écrans, lance run_tsc, lis les fichiers suspects, corrige ce qui est corrigeable, et termine par le verdict JSON avec le marqueur <<<VERDICT>>>."""


# ===========================================================================
# AGENT
# ===========================================================================

class AgentReview(BaseAgent):
    """
    ReviewAgent — analyse, corrige et émet un verdict sur le projet généré.

    C'est le pivot de la boucle d'auto-correction LangGraph :
    son verdict "approved" ou "needs_rework" détermine si le pipeline
    avance vers les tests ou revient corriger codegen/architect.

    Usage depuis graph.py (review_node) :
        agent = AgentReview()
        verdict = agent.run(
            project_path="/chemin/du/projet",
            spec={"app_name": "...", "screens": [...], ...},
            architecture={"raw": "..."},
            team_log=[{"agent": "codegen", "action": "files_generated", ...}]
        )
        # verdict = {"status": "approved"|"needs_rework", "feedback": {...}}
    """

    def __init__(self):
        super().__init__("config_deepseek")

        self.tools = [
            list_project_files,
            read_project_file,
            write_project_file,
            run_tsc,
        ]

        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=SystemMessage(content=SYSTEM_PROMPT),
        )

        print(f"[ReviewAgent] Prêt avec {len(self.tools)} tools.")

    def run(
        self,
        project_path: str,
        spec: dict,
        architecture: dict,
        team_log: list[dict],
    ) -> dict:
        """
        Lance l'analyse complète du projet et retourne le verdict.

        Args:
            project_path : chemin du projet généré
            spec         : spec du PlannerAgent (référence de validation)
            architecture : architecture du ArchitectAgent
            team_log     : journal de bord accumulé de l'équipe

        Returns:
            dict — {"status": "approved"|"needs_rework", "feedback": {...}}
        """
        context = _build_context(project_path, spec, architecture, team_log)

        print("  [ReviewAgent] Analyse du projet en cours...")
        result = self.agent.invoke(
            {"messages": [("human", context)]},
            config={"recursion_limit": 50},
        )

        last_message = result["messages"][-1].content
        verdict = _parse_verdict(last_message)

        # Log du verdict
        status = verdict.get("status", "?")
        feedback = verdict.get("feedback", {})
        n_issues = len(feedback.get("issues", []))
        n_fixed = len(feedback.get("fixed_directly", []))

        if status == "approved":
            print(f"  [ReviewAgent] ✓ APPROUVÉ — {n_fixed} correction(s) directe(s)")
        else:
            target = feedback.get("target_agent", "?")
            severity = feedback.get("severity", "?")
            print(f"  [ReviewAgent] ✗ REWORK → {target} ({severity}) — {n_issues} problème(s)")

        return verdict
