"""
tools.py — ReviewAgent
-----------------------
4 tools donnent au ReviewAgent la capacité d'inspecter et corriger le projet :

    1. list_project_files  → inventaire des fichiers .ts/.tsx générés
    2. read_project_file   → lire un fichier pour l'analyser
    3. write_project_file  → appliquer une correction directement
    4. run_tsc             → compiler avec tsc --noEmit et récupérer les erreurs

Stratégie du ReviewAgent :
    - list_project_files  → voir ce qui existe
    - read_project_file   × N → analyser les fichiers suspects
    - run_tsc             → détecter les erreurs TypeScript
    - write_project_file  × N → corriger les petits problèmes directement
    - Verdict final en JSON
"""

import subprocess
from pathlib import Path
from langchain_core.tools import tool


# Extensions considérées comme code source
CODE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".json"}

# Taille maximale d'un fichier lu (en caractères)
MAX_FILE_CHARS = 6000

# Dossiers à ignorer lors du scan
IGNORED_DIRS = {
    "node_modules", ".git", ".expo", "dist", "build",
    "__pycache__", ".venv", ".next", "coverage", ".turbo",
}


@tool
def list_project_files(project_path: str) -> str:
    """
    Liste tous les fichiers de code source (.ts, .tsx, .js, .jsx, .json)
    du projet généré, en excluant les dossiers de build et dépendances.

    Utilise cet outil EN PREMIER pour avoir l'inventaire complet du projet
    avant d'analyser des fichiers spécifiques.

    Args:
        project_path: Chemin absolu ou relatif vers le dossier du projet généré.

    Returns:
        Liste des fichiers avec leur chemin relatif, groupés par dossier.
        Inclut le nombre total de fichiers.
    """
    root = Path(project_path)

    if not root.exists():
        return f"Projet introuvable : '{project_path}' n'existe pas."
    if not root.is_dir():
        return f"'{project_path}' n'est pas un dossier."

    files = []

    def _walk(directory: Path):
        try:
            for entry in sorted(directory.iterdir()):
                if entry.is_dir():
                    if entry.name not in IGNORED_DIRS:
                        _walk(entry)
                elif entry.suffix in CODE_EXTENSIONS:
                    files.append(str(entry.relative_to(root)))
        except PermissionError:
            pass

    _walk(root)

    if not files:
        return f"Aucun fichier de code trouvé dans '{project_path}'."

    lines = [f"[{len(files)} fichiers dans '{root.name}']"]
    current_dir = None
    for f in files:
        parent = str(Path(f).parent)
        if parent != current_dir:
            current_dir = parent
            lines.append(f"\n  {parent}/")
        lines.append(f"    {Path(f).name}")

    return "\n".join(lines)


@tool
def read_project_file(file_path: str) -> str:
    """
    Lit et retourne le contenu d'un fichier du projet généré.

    Utilise cet outil pour analyser le contenu d'un fichier spécifique :
    vérifier les imports, la logique, la cohérence avec la spec, etc.

    Args:
        file_path: Chemin absolu ou relatif vers le fichier.

    Returns:
        Contenu du fichier avec numéros de ligne.
        Tronqué à 6000 caractères si trop grand.
    """
    path = Path(file_path)

    if not path.exists():
        return f"Fichier introuvable : '{file_path}'"
    if not path.is_file():
        return f"'{file_path}' n'est pas un fichier."

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Erreur de lecture : {e}"

    lines = content.splitlines()
    numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))

    if len(numbered) > MAX_FILE_CHARS:
        return (
            f"[{path.name} — {len(lines)} lignes, TRONQUÉ]\n\n"
            + numbered[:MAX_FILE_CHARS]
            + "\n\n... [suite tronquée]"
        )

    return f"[{path.name} — {len(lines)} lignes]\n\n{numbered}"


@tool
def write_project_file(file_path: str, content: str) -> str:
    """
    Écrit ou corrige un fichier du projet.

    Utilise cet outil pour appliquer une correction DIRECTEMENT sur un fichier
    quand le problème est mineur (import manquant, typo, type incorrect, etc.).

    N'utilise ce tool que pour des corrections ciblées.
    Si la correction nécessite de réécrire complètement un composant,
    indique-le dans le verdict final et laisse CodegenAgent le refaire.

    Args:
        file_path: Chemin absolu vers le fichier à corriger.
        content  : Nouveau contenu complet du fichier.

    Returns:
        Confirmation de la correction avec le chemin du fichier.
    """
    path = Path(file_path)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"[OK] Corrigé : {path} ({len(content)} caractères)"
    except Exception as e:
        return f"[ERREUR] Impossible de corriger '{file_path}' : {e}"


@tool
def run_tsc(project_path: str) -> str:
    """
    Lance le compilateur TypeScript (tsc --noEmit) sur le projet et retourne
    toutes les erreurs de compilation détectées.

    Utilise cet outil après avoir lu les fichiers suspects pour confirmer
    les erreurs TypeScript et obtenir leurs emplacements précis (fichier:ligne).

    Args:
        project_path: Chemin absolu vers le dossier du projet (là où se trouve tsconfig.json).

    Returns:
        Sortie de tsc avec les erreurs, ou "Aucune erreur TypeScript détectée." si tout est bon.
    """
    root = Path(project_path)

    if not root.exists():
        return f"Projet introuvable : '{project_path}'"

    tsconfig = root / "tsconfig.json"
    if not tsconfig.exists():
        return f"tsconfig.json absent dans '{project_path}' — impossible de lancer tsc."

    try:
        result = subprocess.run(
            ["npx", "tsc", "--noEmit", "--pretty", "false"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60,
        )

        output = (result.stdout + result.stderr).strip()

        if result.returncode == 0:
            return "Aucune erreur TypeScript détectée."

        if len(output) > 4000:
            output = output[:4000] + "\n\n... [sortie tronquée]"

        error_count = output.count("error TS")
        return f"[{error_count} erreur(s) TypeScript]\n\n{output}"

    except subprocess.TimeoutExpired:
        return "Timeout : tsc a mis plus de 60s."
    except FileNotFoundError:
        return "npx/tsc introuvable — Node.js et TypeScript doivent être installés."
    except Exception as e:
        return f"Erreur lors de l'exécution de tsc : {e}"
