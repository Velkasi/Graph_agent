"""
tools.py — Outils de l'Agent Architect
----------------------------------------
Ces tools donnent à l'agent la capacité de LIRE le template existant
avant de produire l'architecture, puis de CRÉER les fichiers du projet.

Stratégie clé : l'agent reçoit l'arborescence réelle du template via
`scan_template_tree`. Ainsi le LLM peut référencer les fichiers par leur
chemin exact (ex: "src/components/Button.tsx") plutôt qu'inventer des noms.
Cela réduit drastiquement les hallucinations de chemins.

Tools disponibles :
    1. scan_template_tree  → arborescence complète d'un dossier
    2. read_template_file  → contenu d'un fichier spécifique
    3. create_project_file → crée un fichier (et ses dossiers parents) sur le disque
"""

from pathlib import Path
from langchain_core.tools import tool


# Dossiers à ignorer lors du scan (build artifacts, dépendances, etc.)
IGNORED_DIRS = {
    "node_modules", ".git", ".expo", "dist", "build",
    "__pycache__", ".venv", ".next", "coverage",
}

# Taille maximale d'un fichier lisible (en caractères)
MAX_FILE_CHARS = 8000


@tool
def scan_template_tree(template_path: str, max_depth: int = 6) -> str:
    """
    Parcourt récursivement un dossier et retourne son arborescence complète.

    Utilise cet outil EN PREMIER pour obtenir la liste exacte des fichiers
    du template avant de produire l'architecture. Cela permet de référencer
    les fichiers existants par leur chemin réel et d'éviter les erreurs.

    Args:
        template_path: Chemin absolu ou relatif vers le dossier du template.
                       Ex: "C:/projets/mon-template" ou "./template"
        max_depth: Profondeur maximale de récursion (défaut: 6).
                   Augmenter si le projet est très imbriqué.

    Returns:
        L'arborescence du projet sous forme de texte, style `tree`.
        Ex:
            src/
            ├── app/
            │   ├── (tabs)/
            │   │   └── index.tsx
            │   └── _layout.tsx
            └── components/
                └── Button.tsx
    """
    root = Path(template_path)

    if not root.exists():
        return f"Erreur : le chemin '{template_path}' n'existe pas."
    if not root.is_dir():
        return f"Erreur : '{template_path}' n'est pas un dossier."

    lines = [f"{root.name}/"]

    def _walk(directory: Path, prefix: str, depth: int):
        if depth > max_depth:
            lines.append(f"{prefix}... (profondeur max atteinte)")
            return

        # Trie : dossiers d'abord, puis fichiers, ordre alphabétique
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            lines.append(f"{prefix}[accès refusé]")
            return

        # Filtre les dossiers ignorés
        entries = [e for e in entries if e.name not in IGNORED_DIRS]

        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            extension = "│   " if not is_last else "    "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                _walk(entry, prefix + extension, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

    _walk(root, "", 1)

    total_files = sum(1 for line in lines if not line.endswith("/"))
    summary = f"\n[Scan terminé : {total_files} fichiers trouvés dans '{root.name}']"

    return "\n".join(lines) + summary


@tool
def read_template_file(file_path: str) -> str:
    """
    Lit et retourne le contenu d'un fichier du template.

    Utilise cet outil pour inspecter un fichier spécifique dont tu as
    besoin de comprendre la structure avant de décider quoi modifier.
    Utile pour les fichiers de config, layouts, ou composants de base.

    Args:
        file_path: Chemin absolu ou relatif vers le fichier.
                   Ex: "C:/projets/template/src/app/_layout.tsx"

    Returns:
        Le contenu du fichier sous forme de texte.
        Si le fichier est trop grand (> 8000 caractères), retourne
        uniquement le début avec un avertissement.
    """
    path = Path(file_path)

    if not path.exists():
        return f"Erreur : le fichier '{file_path}' n'existe pas."
    if not path.is_file():
        return f"Erreur : '{file_path}' n'est pas un fichier."

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Erreur de lecture : {e}"

    # Si le fichier est trop long, on tronque pour ne pas saturer le contexte LLM
    if len(content) > MAX_FILE_CHARS:
        return (
            f"[FICHIER TRONQUÉ — {len(content)} caractères, limite {MAX_FILE_CHARS}]\n\n"
            + content[:MAX_FILE_CHARS]
            + "\n\n... [suite tronquée]"
        )

    return f"[Fichier : {path.name} — {len(content)} caractères]\n\n{content}"


@tool
def create_project_file(file_path: str, content: str = "") -> str:
    """
    Crée un fichier dans le dossier du projet avec le contenu fourni.
    Crée automatiquement tous les dossiers parents si nécessaire.

    Utilise cet outil pour CHAQUE fichier listé dans la section
    "FICHIERS À MODIFIER / CRÉER" de ton architecture.
    Appelle-le autant de fois que nécessaire, un fichier à la fois.

    Args:
        file_path: Chemin ABSOLU du fichier à créer.
                   Ex: "C:/Users/kbout/projets/mon-app/src/components/Button.tsx"
                   Le chemin complet est fourni dans le message utilisateur.

        content: Contenu à écrire dans le fichier.
                 Pour les fichiers TypeScript/TSX : écris un composant ou hook minimal valide.
                 Pour les fichiers de config (JSON, etc.) : écris la structure de base.
                 Laisse vide ("") uniquement si le fichier est un placeholder.

    Returns:
        Confirmation de création avec le chemin absolu du fichier.
    """
    path = Path(file_path)

    try:
        # Crée les dossiers parents si besoin (ex: src/components/ si inexistant)
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding="utf-8")

        size = len(content)
        return f"[OK] Fichier créé : {path} ({size} caractères)"

    except Exception as e:
        return f"[ERREUR] Impossible de créer '{file_path}' : {e}"
