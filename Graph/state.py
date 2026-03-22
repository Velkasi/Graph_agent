"""
state.py — État partagé du workflow (mémoire de l'équipe)
----------------------------------------------------------
Le STATE est le "tableau blanc" que toute l'équipe partage.
Chaque agent lit ce que les autres ont écrit, et y ajoute sa contribution.

PHILOSOPHIE DU TEAM STATE :
    - Chaque agent ne travaille pas dans le vide : il lit le contexte complet
    - Le `team_log` est le journal de bord de l'équipe (qui a fait quoi, pourquoi)
    - `review_feedback` est le message du ReviewAgent aux autres agents
    - `retry_counts` empêche les boucles infinies (max 3 corrections par agent)

FLUX DE CORRECTION (boucle d'auto-correction) :
    1. codegen génère les fichiers
    2. review analyse → écrit dans review_status + review_feedback
    3. Si "needs_rework" → codegen relit le feedback et corrige (max 3 fois)
    4. Si "approved" → test + cicd
    5. Si tests échouent → codegen corrige encore

Annotation `Annotated[list, add]` :
    Ces champs s'ACCUMULENT — chaque agent AJOUTE ses éléments sans écraser.
    Utilisé pour les logs, erreurs, agents terminés.
"""

from typing import TypedDict, Annotated
from operator import add


class WorkflowState(TypedDict):
    """
    État global du workflow — mémoire partagée de toute l'équipe.

    ┌─────────────────────────────────────────────────────────────┐
    │  ENTRÉES UTILISATEUR                                        │
    │    user_prompt    : description de l'app à construire       │
    │    ux_images      : maquettes / screenshots UX              │
    │    template_path  : template Expo/React Native de base      │
    │    project_path   : dossier de génération du projet final   │
    └─────────────────────────────────────────────────────────────┘
    ┌─────────────────────────────────────────────────────────────┐
    │  SORTIES DES AGENTS (alimentées progressivement)            │
    │    spec           : PlannerAgent → JSON des écrans/features │
    │    architecture   : ArchitectAgent → JSON technique          │
    │    code_plan      : CodePlannerAgent → liste de fichiers    │
    │    test_results   : TestAgent → rapport des tests           │
    └─────────────────────────────────────────────────────────────┘
    ┌─────────────────────────────────────────────────────────────┐
    │  MÉMOIRE PARTAGÉE DE L'ÉQUIPE                               │
    │    team_log       : journal de bord accumulé (qui/quoi/why) │
    └─────────────────────────────────────────────────────────────┘
    ┌─────────────────────────────────────────────────────────────┐
    │  BOUCLE D'AUTO-CORRECTION                                   │
    │    review_status  : "pending"|"approved"|"needs_rework"     │
    │    review_feedback: feedback structuré du ReviewAgent        │
    │    retry_counts   : {"codegen": 2} — max 3 par agent       │
    └─────────────────────────────────────────────────────────────┘
    ┌─────────────────────────────────────────────────────────────┐
    │  SUIVI DU PIPELINE                                          │
    │    current_agent  : agent en cours d'exécution              │
    │    completed_agents: agents terminés (liste accumulée)      │
    │    errors         : erreurs rencontrées (liste accumulée)   │
    └─────────────────────────────────────────────────────────────┘
    """

    # --- ENTRÉES UTILISATEUR ---
    user_prompt: str
    ux_images: list[str]        # Ex: ["maquettes/home.png", "maquettes/profil.png"]
    template_path: str          # Ex: "C:/projets/expo-template"
    project_path: str           # Ex: "C:/projets/mon-app-generee"

    # --- SORTIES DES AGENTS ---
    spec: dict                  # PlannerAgent   → {"screens": [...], "features": [...]}
    architecture: dict          # ArchitectAgent → {"screens": [...], "database": {...}}
    code_plan: dict             # CodePlannerAgent → {"files": [...], "tasks": [...]}
    test_results: dict          # TestAgent → {"passed": 12, "failed": 2, "issues": [...]}

    # --- MÉMOIRE PARTAGÉE DE L'ÉQUIPE ---
    # Journal de bord accumulé — chaque agent y ajoute une entrée
    # Format : {"agent": "review", "action": "reject", "reason": "...", "timestamp": "..."}
    team_log: Annotated[list[dict], add]

    # --- BOUCLE D'AUTO-CORRECTION ---
    # Statut de la revue courante
    # "pending"      = pas encore reviewé
    # "approved"     = tout est bon, on passe aux tests
    # "needs_rework" = des corrections sont nécessaires
    review_status: str

    # Feedback structuré du ReviewAgent → lu par codegen/architect pour se corriger
    # Format : {
    #   "target_agent": "codegen",          # qui doit corriger
    #   "severity": "high"|"medium"|"low",
    #   "issues": ["auth.ts manque X", "navigation.ts a une erreur Y"],
    #   "suggestions": ["Utiliser useCallback ici", "Vérifier le typage de Z"]
    # }
    review_feedback: dict

    # Compteur de tentatives par agent — pour éviter les boucles infinies
    # Ex: {"codegen": 2, "architect": 1}
    # Chaque agent vérifie son compteur avant d'agir
    retry_counts: dict

    # --- SUIVI DU PIPELINE ---
    current_agent: str

    # Listes accumulées (Annotated[list, add] = chaque nœud AJOUTE sans écraser)
    completed_agents: Annotated[list[str], add]
    errors: Annotated[list[str], add]
