"""
skill_loader.py — Chargement dynamique des Skills pour les agents
-------------------------------------------------------------------
Charge les fichiers de référence framework-spécifiques selon :
  - Le type de fichier à générer (pour CodeGen)
  - La stack détectée dans le discovery_context

Usage :
    from Utils.skill_loader import skills_for_file, skills_for_stack

    # CodeGen : skills adaptées au type de fichier
    skills = skills_for_file(file_type="screen", discovery_context=ctx)

    # CodePlanner : toutes les skills de la stack détectée
    skills = skills_for_stack(discovery_context=ctx)
"""

from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / "Skills"

# Mapping mot-clé (discovery_context lowercase) → nom du fichier skill
STACK_KEYWORD_MAP = {
    "expo router": "expo-router",
    "expo":        "expo-router",
    "supabase":    "supabase",
    "react query": "data-fetching",   # remplacé par la skill complète
    "@tanstack":   "data-fetching",
    "realtime":    "realtime-storage",
    "storage":     "realtime-storage",
    "auth":        "auth-navigation",
    "typescript":  "typescript-rn",
}

# Skills par type de fichier (file_spec["type"])
# Ordre = priorité d'injection (les plus spécifiques d'abord)
FILE_TYPE_SKILLS = {
    "lib":        ["supabase", "typescript-rn"],
    "types":      ["typescript-rn"],
    "hook":       ["data-fetching", "realtime-storage", "typescript-rn"],
    "screen":     ["auth-navigation", "expo-router", "typescript-rn"],
    "component":  ["expo-router", "typescript-rn"],
    "layout":     ["auth-navigation", "expo-router", "data-fetching", "typescript-rn"],
    "config":     ["typescript-rn"],
}


def _load(skill_name: str, category: str = "codegen") -> str:
    """Charge le contenu d'un fichier skill. Retourne '' si absent."""
    path = SKILLS_DIR / category / f"{skill_name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def detect_stack_skills(discovery_context: str) -> list[str]:
    """Retourne la liste des noms de skills détectés dans le discovery_context."""
    ctx_lower = discovery_context.lower()
    skills = []
    for keyword, skill_name in STACK_KEYWORD_MAP.items():
        if keyword in ctx_lower and skill_name not in skills:
            skills.append(skill_name)
    # typescript-rn est toujours pertinent si Supabase ou Expo détectés
    if skills and "typescript-rn" not in skills:
        skills.append("typescript-rn")
    return skills


def skills_for_file(file_type: str, discovery_context: str = "") -> str:
    """
    Charge les skills pertinentes pour un type de fichier donné.
    Filtre selon la stack réelle si discovery_context est fourni.

    Args:
        file_type         : type du fichier ("screen", "hook", "lib", "types", "component")
        discovery_context : Q&A discovery pour filtrer par stack réelle

    Returns:
        str — contenu des skills concatenées, vide si aucune applicable
    """
    candidates = FILE_TYPE_SKILLS.get(file_type, ["typescript-rn"])

    if discovery_context:
        stack_skills = detect_stack_skills(discovery_context)
        # Garder seulement les skills pertinentes pour ce projet
        candidates = [s for s in candidates if s in stack_skills]

    parts = []
    for name in candidates:
        content = _load(name)
        if content:
            parts.append(content)

    if not parts:
        return ""

    return "--- RÉFÉRENCE FRAMEWORK ---\n\n" + "\n\n---\n\n".join(parts) + "\n--- FIN RÉFÉRENCE ---"


def skills_for_stack(discovery_context: str, category: str = "codegen") -> str:
    """
    Charge toutes les skills de la stack détectée (pour CodePlanner).

    Returns:
        str — contenu des skills concatenées
    """
    skill_names = detect_stack_skills(discovery_context)

    parts = []
    for name in skill_names:
        content = _load(name, category)
        if content:
            parts.append(content)

    if not parts:
        return ""

    return "--- RÉFÉRENCE FRAMEWORK ---\n\n" + "\n\n---\n\n".join(parts) + "\n--- FIN RÉFÉRENCE ---"
