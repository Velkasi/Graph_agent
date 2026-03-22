"""
graph.py — Pipeline LangGraph avec boucles d'auto-correction
-------------------------------------------------------------
Définit le graphe d'exécution reliant tous les agents du workflow.

ARCHITECTURE "TEAM LOOP" :

    [START]
       │
       ▼
  [planner]          PlannerAgent     → produit spec
       │
       ▼
  [architect]        ArchitectAgent   → produit architecture
       │
       ├─────────────────────┐
       ▼                     ▼
  [code_planner]        [backend]     (en parallèle)
       │                     │
       └──────────┬──────────┘
                  ▼
             [codegen]              CodegenAgent → écrit les fichiers
                  │
                  ▼
             [review]               ReviewAgent → analyse et émet un verdict
                  │
          ┌───────┴──────────────────────────────────┐
          │  "approved"                               │  "needs_rework"
          ▼                                           ▼
    ┌─────┴──────┐                          target_agent == "architect" ?
    ▼            ▼                              │ oui → [architect] (retry)
  [test]      [cicd]  (en parallèle)            │ non → [codegen]   (retry)
    │            │                              │
    └─────┬──────┘                          max_retries atteint ?
          │                                    → [test] de force
          ▼
      "tests_failed" ? → [codegen] (retry)
          │
          ▼
        [END]

MÉMOIRE DE L'ÉQUIPE :
    - WorkflowState = tableau blanc partagé entre tous les agents
    - team_log = journal de bord accumulé (chaque agent écrit ce qu'il a fait)
    - review_feedback = message structuré du ReviewAgent pour guider la correction
    - retry_counts = garde-fou contre les boucles infinies (max MAX_RETRIES)

PERSISTENCE (SQLite) :
    LangGraph sauvegarde l'état après CHAQUE nœud.
    thread_id = identifiant de session → reprise possible après crash.
"""

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from Graph.state import WorkflowState
from Utils.logger import log, log_router, log_state, log_separator

# Dossier de persistence SQLite
PERSISTENCE_DIR = Path(__file__).parent.parent / "runs"
PERSISTENCE_DIR.mkdir(exist_ok=True)
DB_PATH = str(PERSISTENCE_DIR / "workflow_memory.db")

# Nombre maximum de tentatives de correction par agent
MAX_RETRIES = 3


# ===========================================================================
# HELPERS
# ===========================================================================

def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")

def _log_entry(agent: str, action: str, detail: str = "") -> dict:
    """Crée une entrée de journal pour team_log."""
    return {"agent": agent, "action": action, "detail": detail, "time": _now()}

def _get_retry(state: WorkflowState, agent: str) -> int:
    """Retourne le nombre de tentatives d'un agent (0 si pas encore tenté)."""
    return state.get("retry_counts", {}).get(agent, 0)

def _increment_retry(state: WorkflowState, agent: str) -> dict:
    """Retourne un dict partiel avec le compteur incrémenté."""
    counts = dict(state.get("retry_counts", {}))
    counts[agent] = counts.get(agent, 0) + 1
    return counts


# ===========================================================================
# NŒUDS DU GRAPHE
# Chaque nœud reçoit le state complet et retourne un dict PARTIEL.
# LangGraph fusionne ce dict dans le state global avant le nœud suivant.
# ===========================================================================

def planner_node(state: WorkflowState) -> dict:
    """
    PlannerAgent — traduit le prompt utilisateur en spec structurée.

    Lit    : user_prompt, ux_images
    Écrit  : spec
    Modèle : mistral:7b-q4
    """
    log_separator("PLANNER")
    log("planner", "START", "Démarrage — prompt reçu")
    try:
        from Agents.Agent_Planner.agent import AgentPlanner
        agent = AgentPlanner()
        # Utilise le discovery complet si disponible, sinon le prompt court
        prompt = state.get("discovery_context") or state["user_prompt"]
        spec = agent.run(
            prompt=prompt,
            ux_images=state.get("ux_images", []),
        )
        n = len(spec.get("screens", []))
        log("planner", "OK", f"Spec générée : '{spec.get('app_name', '?')}' — {n} écrans")
        return {
            "spec": spec,
            "current_agent": "planner",
            "completed_agents": ["planner"],
            "team_log": [_log_entry("planner", "spec_generated", f"{n} écrans")],
        }
    except ImportError:
        log("planner", "WARN", "Non implémenté — données simulées (STUB)")
        stub_spec = {
            "status": "stub",
            "description": state.get("user_prompt", ""),
            "screens": ["Accueil", "Profil", "Paramètres"],
            "features": ["auth", "profil", "navigation"],
        }
        return {
            "spec": stub_spec,
            "current_agent": "planner",
            "completed_agents": ["planner"],
            "team_log": [_log_entry("planner", "stub", "données simulées")],
        }


def architect_node(state: WorkflowState) -> dict:
    """
    ArchitectAgent — traduit la spec en architecture technique.

    Lit    : spec, template_path, review_feedback (si retry architecte)
    Écrit  : architecture
    Modèle : mistral/devstral
    """
    retry = _get_retry(state, "architect")
    log_separator("ARCHITECT")
    log("architect", "START", f"Démarrage {'— retry #' + str(retry) if retry else ''}")

    feedback_context = ""
    if retry > 0 and state.get("review_feedback"):
        issues = state["review_feedback"].get("issues", [])
        feedback_context = "\nCorrections demandées par le ReviewAgent :\n" + "\n".join(f"- {i}" for i in issues)
        log("architect", "INFO", f"Feedback appliqué : {len(issues)} problème(s) à corriger")
        for i in issues:
            log("architect", "INFO", f"  · {i}")

    try:
        from Agents.Agent_Architect.agent import AgentArchitect
        agent = AgentArchitect()

        # Résoudre le chemin absolu pour que create_project_file sache où écrire
        project_path = str(Path(state.get("project_path", ".")).resolve())
        spec = state.get("spec", {})
        screens = [s.get("name", "?") for s in spec.get("screens", [])]

        # Tour 1 : récapitulatif architecture
        discovery = state.get("discovery_context", "")
        message = (
            f"Voici la spec du projet à architecturer :\n\n{spec}\n\n"
            f"Template : {state.get('template_path', '.')}"
        )
        if discovery:
            message += f"\n\nCONTEXTE DISCOVERY (contraintes réelles du projet) :\n{discovery}"
        if feedback_context:
            message += f"\n\n{feedback_context}"
        recap, messages = agent.chat([], message)

        # Tour 2 : confirmation + création des fichiers via les tools de l'agent
        confirm = (
            f"Oui, c'est correct.\n\n"
            f"Utilise maintenant create_project_file pour créer TOUS les fichiers vides "
            f"de l'infrastructure dans ce dossier (chemin absolu) : {project_path}\n\n"
            f"Fichiers attendus (au minimum) :\n"
            f"- Un fichier par écran de la spec dans {project_path}/app/ : {screens}\n"
            f"- Les composants partagés dans {project_path}/components/\n"
            f"- Les hooks dans {project_path}/hooks/\n"
            f"- Les types dans {project_path}/types/\n"
            f"- Les services Supabase dans {project_path}/lib/\n\n"
            f"Exemple de chemin : {project_path}/app/index.tsx\n"
            f"content=\"\" pour tous les fichiers TypeScript. Un appel create_project_file par fichier."
        )
        result, _ = agent.chat(messages, confirm)

        # Construire une architecture structurée en scannant les fichiers créés
        project_dir = Path(project_path)
        extensions = {".tsx", ".ts", ".sql", ".json", ".md", ".js"}
        ignored = {"node_modules", ".git", ".expo", "dist", "build", "__pycache__"}
        files_created = sorted(
            str(p.relative_to(project_dir)).replace("\\", "/")
            for p in project_dir.rglob("*")
            if p.is_file()
            and p.suffix in extensions
            and not any(part in ignored for part in p.parts)
        )
        architecture = {
            "status": "generated",
            "project_path": project_path,
            "screens": screens,
            "files": files_created,
        }

        log("architect", "OK", f"Architecture générée — {len(files_created)} fichiers dans {project_path}")
        return {
            "architecture": architecture,
            "current_agent": "architect",
            "completed_agents": ["architect"],
            "retry_counts": _increment_retry(state, "architect") if retry else state.get("retry_counts", {}),
            "team_log": [_log_entry("architect", "architecture_generated", f"retry={retry}, {len(files_created)} fichiers")],
        }
    except Exception as e:
        log("architect", "ERROR", str(e))
        return {
            "architecture": {"status": "error", "error": str(e)},
            "current_agent": "architect",
            "completed_agents": ["architect"],
            "errors": [f"ArchitectAgent: {e}"],
            "team_log": [_log_entry("architect", "error", str(e))],
        }


def code_planner_node(state: WorkflowState) -> dict:
    """
    CodePlannerAgent — liste précise des fichiers à créer/modifier.

    Lit    : architecture, template_path
    Écrit  : code_plan
    Modèle : deepseek-coder:7b-q4
    """
    log_separator("CODE PLANNER")
    log("code_planner", "START", "Démarrage")
    try:
        from Agents.Agent_CodePlanner.agent import AgentCodePlanner
        agent = AgentCodePlanner()
        code_plan = agent.run(
            architecture=state.get("architecture", {}),
            spec=state.get("spec", {}),
            discovery_context=state.get("discovery_context", ""),
        )
        n = len(code_plan.get("files", []))
        log("code_planner", "OK", f"Plan généré : {n} fichiers")
        return {
            "code_plan": code_plan,
            "completed_agents": ["code_planner"],
            "team_log": [_log_entry("code_planner", "plan_generated", f"{n} fichiers")],
        }
    except ImportError:
        log("code_planner", "WARN", "Non implémenté — données simulées (STUB)")
        return {
            "code_plan": {"status": "stub", "files": []},
            "completed_agents": ["code_planner"],
            "team_log": [_log_entry("code_planner", "stub")],
        }


def backend_node(state: WorkflowState) -> dict:
    """
    BackendAgent — génère migrations SQL et Edge Functions Supabase.

    Lit    : architecture (section tables)
    Écrit  : fichiers SQL sur le disque
    Modèle : mistral:7b-q4
    """
    log_separator("BACKEND")
    log("backend", "START", "Démarrage — génération des migrations SQL")
    try:
        from Agents.Agent_Backend.agent import AgentBackend
        from pathlib import Path as _Path
        agent = AgentBackend()
        project_path = str(_Path(state.get("project_path", ".")).resolve())
        result = agent.run(
            spec=state.get("spec", {}),
            architecture=state.get("architecture", {}),
            project_path=project_path,
            discovery_context=state.get("discovery_context", ""),
        )
        n = len(result.get("files_created", []))
        log("backend", "OK", f"{n} fichier(s) Supabase créé(s)")
        return {
            "completed_agents": ["backend"],
            "team_log": [_log_entry("backend", "supabase_generated", f"{n} fichiers")],
        }
    except Exception as e:
        log("backend", "ERROR", str(e))
        return {
            "completed_agents": ["backend"],
            "errors": [f"BackendAgent: {e}"],
            "team_log": [_log_entry("backend", "error", str(e))],
        }


def codegen_node(state: WorkflowState) -> dict:
    """
    CodegenAgent — écrit les fichiers du projet.

    Lit    : code_plan, project_path, review_feedback (si retry)
    Écrit  : fichiers sur le disque
    Modèle : deepseek-coder:7b-q4

    BOUCLE : peut être relancé par le ReviewAgent ou le TestAgent.
    """
    retry = _get_retry(state, "codegen")
    log_separator("CODEGEN")
    log("codegen", "START", f"Démarrage {'— retry #' + str(retry) if retry else ''}")

    feedback_context = ""
    if retry > 0 and state.get("review_feedback"):
        issues = state["review_feedback"].get("issues", [])
        suggestions = state["review_feedback"].get("suggestions", [])
        feedback_context = (
            "\nProblèmes identifiés par le ReviewAgent :\n"
            + "\n".join(f"- {i}" for i in issues)
            + ("\nSuggestions :\n" + "\n".join(f"- {s}" for s in suggestions) if suggestions else "")
        )
        log("codegen", "INFO", f"Feedback appliqué : {len(issues)} problème(s), {len(suggestions)} suggestion(s)")

    try:
        from Agents.Agent_CodeGen.agent import AgentCodegen
        agent = AgentCodegen()
        agent.run(
            code_plan=state.get("code_plan", {}),
            project_path=state.get("project_path", "."),
            feedback=feedback_context,
            discovery_context=state.get("discovery_context", ""),
        )
        log("codegen", "OK", "Fichiers générés")
        return {
            "current_agent": "codegen",
            "completed_agents": ["codegen"],
            "retry_counts": _increment_retry(state, "codegen"),
            "team_log": [_log_entry("codegen", "files_generated", f"retry={retry}")],
        }
    except ImportError:
        log("codegen", "WARN", "Non implémenté (STUB)")
        return {
            "current_agent": "codegen",
            "completed_agents": ["codegen"],
            "retry_counts": _increment_retry(state, "codegen"),
            "team_log": [_log_entry("codegen", "stub")],
        }


def review_node(state: WorkflowState) -> dict:
    """
    ReviewAgent — vérifie les fichiers générés et émet un verdict.

    Lit    : project_path, spec, architecture, team_log
    Écrit  : review_status ("approved" | "needs_rework"), review_feedback
    Modèle : deepseek-coder:7b-q4

    C'EST LE CHEF D'ÉQUIPE : il décide si le travail est acceptable ou non.
    Son feedback est lu par codegen/architect pour se corriger.
    """
    log_separator("REVIEW")
    log("review", "START", "Analyse du projet généré...")
    try:
        from Agents.Agent_Review.agent import AgentReview
        agent = AgentReview()
        verdict = agent.run(
            project_path=state.get("project_path", "."),
            spec=state.get("spec", {}),
            architecture=state.get("architecture", {}),
            team_log=state.get("team_log", []),
        )
        status = verdict.get("status", "approved")
        feedback = verdict.get("feedback", {})
        issues = feedback.get("issues", [])
        level = "OK" if status == "approved" else "WARN"
        log("review", level, f"Verdict : {status.upper()} — {len(issues)} problème(s)")
        for issue in issues:
            log("review", "WARN", f"  · {issue}")
        log_state(state)
        return {
            "review_status": status,
            "review_feedback": feedback,
            "current_agent": "review",
            "completed_agents": ["review"],
            "team_log": [_log_entry("review", status, str(issues))],
        }
    except ImportError:
        log("review", "WARN", "Non implémenté — approuvé automatiquement (STUB)")
        log_state(state)
        return {
            "review_status": "approved",
            "review_feedback": {},
            "current_agent": "review",
            "completed_agents": ["review"],
            "team_log": [_log_entry("review", "stub_approved")],
        }


def test_node(state: WorkflowState) -> dict:
    """
    TestAgent — lance les tests et retourne un rapport structuré.

    Lit    : project_path
    Écrit  : test_results
    Modèle : phi3:3.8b-q5

    BOUCLE : si des tests échouent, le graph retourne à codegen.
    """
    log_separator("TEST")
    log("test", "START", "Lancement des tests...")
    try:
        from Agents.Agent_Test.agent import AgentTest
        agent = AgentTest()
        results = agent.run(project_path=state.get("project_path", "."))
        passed = results.get("passed", 0)
        failed = results.get("failed", 0)
        level = "OK" if failed == 0 else "WARN"
        log("test", level, f"{passed} tests OK / {failed} KO")
        for issue in results.get("issues", []):
            log("test", "WARN", f"  · {issue}")
        return {
            "test_results": results,
            "completed_agents": ["test"],
            "team_log": [_log_entry("test", "tested", f"passed={passed} failed={failed}")],
        }
    except ImportError:
        log("test", "WARN", "Non implémenté — tous tests supposés passés (STUB)")
        return {
            "test_results": {"status": "stub", "passed": 0, "failed": 0, "issues": []},
            "completed_agents": ["test"],
            "team_log": [_log_entry("test", "stub_passed")],
        }


def cicd_node(state: WorkflowState) -> dict:
    """
    CICDAgent — génère le fichier .github/workflows/ci.yml.

    Lit    : project_path
    Écrit  : fichier CI/CD sur le disque
    Modèle : phi3:3.8b-q5
    """
    log_separator("CICD")
    log("cicd", "START", "Génération du pipeline CI/CD...")
    try:
        from Agents.Agent_CICD.agent import AgentCICD
        agent = AgentCICD()
        agent.run(project_path=state.get("project_path", "."))
        log("cicd", "OK", ".github/workflows/ci.yml généré")
        return {
            "completed_agents": ["cicd"],
            "team_log": [_log_entry("cicd", "ci_generated")],
        }
    except ImportError:
        log("cicd", "WARN", "Non implémenté (STUB)")
        return {
            "completed_agents": ["cicd"],
            "team_log": [_log_entry("cicd", "stub")],
        }


# ===========================================================================
# ROUTEURS — CONDITIONAL EDGES
# Décident du prochain nœud en fonction de l'état courant.
# ===========================================================================

def route_after_review(state: WorkflowState) -> list[str] | str:
    """
    Routeur après ReviewAgent.

    approved          → ["test", "cicd"]  fan-out en parallèle
    needs_rework      → "codegen" ou "architect" selon le feedback
    max retries       → ["test", "cicd"]  best effort (on ne bloque pas indéfiniment)

    Retourner une LISTE = LangGraph démarre tous les nœuds listés en parallèle.
    Retourner un STRING = LangGraph route vers ce nœud unique.
    """
    status = state.get("review_status", "approved")
    feedback = state.get("review_feedback", {})
    target_agent = feedback.get("target_agent", "codegen") or "codegen"

    if status == "approved":
        log_router("review", "test ‖ cicd", "approved — parallèle")
        return ["test", "cicd"]

    retry = _get_retry(state, target_agent)
    if retry >= MAX_RETRIES:
        log_router("review", "test ‖ cicd", f"max retries ({MAX_RETRIES}) atteint — best effort")
        return ["test", "cicd"]

    log_router("review", target_agent, f"needs_rework — tentative {retry + 1}/{MAX_RETRIES}")

    if target_agent == "architect":
        return "architect"
    return "codegen"


def route_after_tests(state: WorkflowState) -> str:
    """
    Routeur après TestAgent.

    all passed        → END
    tests failed      → codegen (si retries disponibles), sinon END
    """
    results = state.get("test_results", {})
    failed = results.get("failed", 0)
    status = results.get("status", "stub")

    if status == "stub" or failed == 0:
        print(f"  [ROUTER] test → TOUS PASSÉS → END")
        return END

    retry = _get_retry(state, "codegen")
    if retry >= MAX_RETRIES:
        log_router("test", "END", f"{failed} test(s) KO — max retries atteint")
        return END

    log_router("test", "codegen", f"{failed} test(s) KO — tentative {retry + 1}/{MAX_RETRIES}")
    return "codegen"


# ===========================================================================
# CONSTRUCTION DU GRAPHE
# ===========================================================================

def build_graph():
    """
    Construit et compile le graphe LangGraph avec :
    - Boucles d'auto-correction (review → codegen/architect)
    - Boucle test → codegen si échec
    - Persistence SQLite par thread_id

    Usage :
        graph = build_graph()
        result = graph.invoke(
            {"user_prompt": "...", "template_path": "...", "project_path": "..."},
            config={"configurable": {"thread_id": "session-001"}}
        )
    """
    builder = StateGraph(WorkflowState)

    # --- Nœuds ---
    builder.add_node("planner",      planner_node)
    builder.add_node("architect",    architect_node)
    builder.add_node("code_planner", code_planner_node)
    builder.add_node("backend",      backend_node)
    builder.add_node("codegen",      codegen_node)
    builder.add_node("review",       review_node)
    builder.add_node("test",         test_node)
    builder.add_node("cicd",         cicd_node)

    # --- Edges fixes (séquence principale) ---
    builder.add_edge(START,          "planner")
    builder.add_edge("planner",      "architect")

    # architect → code_planner et backend en parallèle
    builder.add_edge("architect",    "code_planner")
    builder.add_edge("architect",    "backend")

    # code_planner + backend → codegen (attend les deux)
    builder.add_edge("code_planner", "codegen")
    builder.add_edge("backend",      "codegen")

    # codegen → review
    builder.add_edge("codegen",      "review")

    # --- Conditional edge : review → codegen | architect | [test, cicd] ---
    # route_after_review retourne une LISTE ["test", "cicd"] quand approuvé
    # → LangGraph démarre les deux nœuds en parallèle automatiquement
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {
            "codegen":   "codegen",    # needs_rework → corrections code
            "architect": "architect",  # needs_rework → corrections architecture
            "test":      "test",       # approved (fan-out géré par la liste)
            "cicd":      "cicd",       # approved (fan-out géré par la liste)
        }
    )

    # --- Conditional edge : test → codegen | END ---
    builder.add_conditional_edges(
        "test",
        route_after_tests,
        {
            "codegen": "codegen",  # tests KO → corrections
            END:       END,        # tests OK → terminé
        }
    )

    # cicd → END
    builder.add_edge("cicd", END)

    # --- Persistence SQLite ---
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    graph = builder.compile(checkpointer=checkpointer)
    log("graph", "OK", f"Pipeline compilé — persistence : {DB_PATH}")
    return graph
