"""
tools.py — Outils de l'Agent Backend
--------------------------------------
Donnent à l'agent la capacité d'écrire les artefacts Supabase sur le disque.

Tools disponibles :
    1. write_sql_migration  → écrit un fichier .sql dans supabase/migrations/
    2. write_edge_function  → crée un dossier + index.ts dans supabase/functions/
    3. write_project_file   → écrit n'importe quel fichier dans le projet
                              (README.md, .env.example, etc.)
"""

from pathlib import Path
from langchain_core.tools import tool


@tool
def write_sql_migration(project_path: str, filename: str, sql_content: str) -> str:
    """
    Écrit un fichier de migration SQL dans supabase/migrations/.

    Utilise cet outil pour chaque fichier de migration SQL à générer.
    Respecte la convention de nommage Supabase : 001_initial_schema.sql, 002_rls.sql, etc.

    Args:
        project_path : chemin ABSOLU du projet (ex: C:/Users/.../output_test)
        filename     : nom du fichier SQL (ex: "001_initial_schema.sql")
        sql_content  : contenu SQL complet (extensions, tables, RLS, triggers, indexes)

    Returns:
        Confirmation avec le chemin absolu du fichier créé.
    """
    path = Path(project_path) / "supabase" / "migrations" / filename
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sql_content, encoding="utf-8")
        return f"[OK] Migration créée : {path} ({len(sql_content)} caractères)"
    except Exception as e:
        return f"[ERREUR] {e}"


@tool
def write_edge_function(project_path: str, function_name: str, ts_content: str) -> str:
    """
    Crée une Edge Function Supabase dans supabase/functions/<function_name>/index.ts.

    Utilise cet outil pour chaque Edge Function à générer (ex: send_notification,
    on_user_created, process_payment, etc.).
    Le code doit être du TypeScript compatible Deno.

    Args:
        project_path  : chemin ABSOLU du projet
        function_name : nom de la fonction (ex: "send_notification")
        ts_content    : code TypeScript Deno complet de la fonction

    Returns:
        Confirmation avec le chemin absolu du fichier créé.
    """
    path = Path(project_path) / "supabase" / "functions" / function_name / "index.ts"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(ts_content, encoding="utf-8")
        return f"[OK] Edge Function créée : {path} ({len(ts_content)} caractères)"
    except Exception as e:
        return f"[ERREUR] {e}"


@tool
def write_project_file(project_path: str, relative_path: str, content: str) -> str:
    """
    Écrit un fichier quelconque dans le projet (README.md, .env.example, config, etc.).

    Args:
        project_path  : chemin ABSOLU du projet
        relative_path : chemin relatif depuis la racine du projet (ex: "README.md")
        content       : contenu du fichier

    Returns:
        Confirmation avec le chemin absolu du fichier créé.
    """
    path = Path(project_path) / relative_path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"[OK] Fichier créé : {path} ({len(content)} caractères)"
    except Exception as e:
        return f"[ERREUR] {e}"


@tool
def append_project_file(project_path: str, relative_path: str, content: str) -> str:
    """
    Ajoute du contenu à la suite d'un fichier existant (ou le crée s'il n'existe pas).

    Utilise cet outil pour écrire les gros fichiers (SQL, TypeScript) EN PLUSIEURS APPELS
    successifs plutôt qu'en un seul bloc. Cela évite les erreurs de parsing JSON sur les
    grands contenus.

    Stratégie recommandée pour la migration SQL :
        1. append_project_file  → extensions + fonction update_updated_at
        2. append_project_file  → table organizations + users
        3. append_project_file  → tables métier (projects, tasks, comments, notifications)
        4. append_project_file  → triggers
        5. append_project_file  → indexes
        6. append_project_file  → RLS (ALTER TABLE + policies)

    Args:
        project_path  : chemin ABSOLU du projet
        relative_path : chemin relatif depuis la racine du projet
                        Ex: "supabase/migrations/001_initial_schema.sql"
        content       : bloc de contenu à ajouter (pas besoin d'être le fichier entier)

    Returns:
        Confirmation avec le chemin et la taille totale du fichier.
    """
    path = Path(project_path) / relative_path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        total = path.stat().st_size
        return f"[OK] Contenu ajouté : {path} ({total} octets au total)"
    except Exception as e:
        return f"[ERREUR] {e}"
