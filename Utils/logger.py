"""
logger.py — Logger partagé pour tous les agents et le graph
------------------------------------------------------------
Usage depuis n'importe quel agent ou nœud du graph :

    from Utils.logger import log, log_router, log_state, log_error

    log("planner", "INFO",  "Génération de la spec...")
    log("planner", "OK",    "Spec générée : TaskFlow — 6 écrans")
    log("review",  "WARN",  "3 problèmes détectés")
    log("review",  "ERROR", "Impossible de lire le fichier")

    log_router("review", "codegen", "needs_rework — retry 1/3")
    log_router("review", "test ‖ cicd", "approved")

    log_state(state)   # snapshot lisible du state courant

Sortie : console (couleurs ANSI) + fichier runs/workflow.log (texte brut)
"""

import re
import sys
from datetime import datetime
from pathlib import Path

# --- Fichier de log ---
LOG_DIR = Path(__file__).parent.parent / "runs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "workflow.log"

# --- Couleurs ANSI ---
R = "\033[0m"       # reset
B = "\033[1m"       # bold

AGENT_COLORS = {
    "planner":      "\033[94m",   # bleu
    "architect":    "\033[95m",   # violet
    "code_planner": "\033[96m",   # cyan
    "backend":      "\033[33m",   # orange
    "codegen":      "\033[92m",   # vert
    "review":       "\033[93m",   # jaune
    "test":         "\033[36m",   # cyan foncé
    "cicd":         "\033[90m",   # gris
    "graph":        "\033[97m",   # blanc brillant
    "router":       "\033[96m",   # cyan
}

LEVEL_COLORS = {
    "INFO":   "\033[37m",    # gris clair
    "OK":     "\033[92m",    # vert
    "WARN":   "\033[93m",    # jaune
    "ERROR":  "\033[91m",    # rouge
    "ROUTER": "\033[96m",    # cyan
    "STATE":  "\033[90m",    # gris foncé
    "START":  "\033[97m",    # blanc brillant
    "END":    "\033[97m",    # blanc brillant
}

LEVEL_ICONS = {
    "INFO":   "·",
    "OK":     "✓",
    "WARN":   "⚠",
    "ERROR":  "✗",
    "ROUTER": "→",
    "STATE":  "≡",
    "START":  "┌",
    "END":    "└",
}


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _strip_ansi(text: str) -> str:
    """Supprime les codes ANSI pour l'écriture dans le fichier."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


def _write(line_console: str, line_file: str | None = None):
    """Écrit une ligne sur la console et dans le fichier de log."""
    print(line_console)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write((line_file or _strip_ansi(line_console)) + "\n")


# ===========================================================================
# FONCTIONS PUBLIQUES
# ===========================================================================

def log(agent: str, level: str, message: str):
    """
    Log principal — utilisé par les agents et les nœuds du graph.

    Args:
        agent   : nom de l'agent ("planner", "review", "graph", ...)
        level   : "INFO" | "OK" | "WARN" | "ERROR" | "START" | "END"
        message : texte libre

    Exemples :
        log("planner", "START", "Démarrage")
        log("planner", "OK",    "Spec générée : TaskFlow — 6 écrans")
        log("review",  "WARN",  "3 problèmes détectés dans auth.ts")
        log("review",  "ERROR", "Fichier introuvable : navigation.ts")
    """
    level = level.upper()
    agent_col  = AGENT_COLORS.get(agent.lower(), "\033[37m")
    level_col  = LEVEL_COLORS.get(level, "\033[37m")
    icon       = LEVEL_ICONS.get(level, "·")
    agent_label = agent.upper().ljust(12)

    line = (
        f"{level_col}{icon}{R} "
        f"[{_now()}] "
        f"{agent_col}{B}{agent_label}{R} "
        f"{level_col}{message}{R}"
    )
    _write(line)


def log_router(from_node: str, to_node: str, reason: str = ""):
    """
    Log une décision de routing — visible d'un coup d'œil.

    Exemples :
        log_router("review", "test ‖ cicd", "approved")
        log_router("review", "codegen",     "needs_rework — retry 1/3")
        log_router("test",   "END",         "tous les tests passés")
    """
    reason_txt = f" ({reason})" if reason else ""
    line = (
        f"{LEVEL_COLORS['ROUTER']}→{R} "
        f"[{_now()}] "
        f"{AGENT_COLORS.get('router', '')}{B}ROUTER      {R}"
        f"{AGENT_COLORS.get(from_node, '')}{from_node}{R}"
        f"{LEVEL_COLORS['ROUTER']} ──▶ {B}{to_node}{R}"
        f"{LEVEL_COLORS['STATE']}{reason_txt}{R}"
    )
    _write(line)


def log_state(state: dict):
    """
    Affiche un snapshot lisible des champs clés du WorkflowState.
    À appeler à la fin d'un nœud ou après un routing pour voir l'état courant.
    """
    sep = f"{LEVEL_COLORS['STATE']}{'─' * 55}{R}"
    _write(sep)
    _write(f"{LEVEL_COLORS['STATE']}≡ [{_now()}] STATE SNAPSHOT{R}")

    # Champs à afficher (par ordre de priorité)
    fields = [
        ("current_agent",    state.get("current_agent", "—")),
        ("completed_agents", ", ".join(state.get("completed_agents", [])) or "—"),
        ("review_status",    state.get("review_status", "—")),
        ("retry_counts",     state.get("retry_counts", {}) or "—"),
        ("errors",           len(state.get("errors", []))),
        ("team_log entries", len(state.get("team_log", []))),
    ]

    for key, val in fields:
        line = (
            f"  {LEVEL_COLORS['STATE']}{key:<20}{R}"
            f"{LEVEL_COLORS['INFO']}{val}{R}"
        )
        _write(line)

    # Résumé de la spec si disponible
    spec = state.get("spec", {})
    if spec.get("app_name"):
        n_screens  = len(spec.get("screens", []))
        n_features = len(spec.get("features", []))
        line = (
            f"  {LEVEL_COLORS['STATE']}{'spec':<20}{R}"
            f"{LEVEL_COLORS['INFO']}{spec['app_name']} — {n_screens} écrans, {n_features} features{R}"
        )
        _write(line)

    _write(sep)


def log_error(agent: str, error: Exception | str):
    """
    Log une erreur avec traceback si disponible.
    Raccourci pour log(agent, "ERROR", ...).
    """
    log(agent, "ERROR", str(error))


def log_separator(label: str = ""):
    """Séparateur visuel entre les grandes étapes du pipeline."""
    if label:
        pad = max(0, 50 - len(label))
        txt = f"── {label} {'─' * pad}"
    else:
        txt = "─" * 55
    line = f"\n{LEVEL_COLORS['STATE']}{txt}{R}\n"
    _write(line)
