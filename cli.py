"""
cli.py — Interface en ligne de commande
-----------------------------------------
Point d'entrée interactif pour le workflow de génération d'application.

Modes disponibles :
    [1] Pipeline complet     — lance tous les agents dans l'ordre
    [2] Agent seul           — teste un agent en isolation
    [3] Reprendre session    — reprend une session existante (même thread_id)
    [4] Voir les sessions    — liste les sessions sauvegardées
    [q] Quitter

Persistence :
    Chaque session a un `thread_id` unique (ex: "session-001").
    LangGraph sauvegarde l'état après chaque agent dans SQLite (runs/workflow_memory.db).
    Reprendre une session = continuer exactement où on s'est arrêté.

Usage :
    python cli.py
"""

import sys
import json
import uuid
from pathlib import Path
from datetime import datetime

# Force UTF-8 pour le terminal Windows
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Dossier de sauvegarde des sessions
RUNS_DIR = Path("runs")
RUNS_DIR.mkdir(exist_ok=True)


# ===========================================================================
# UTILITAIRES
# ===========================================================================

def banner():
    print("\n" + "=" * 60)
    print("   Workflow IA — Generateur d'application mobile")
    print("   Expo Router + Supabase + React Query")
    print("=" * 60)


def menu_principal():
    print("\nQue voulez-vous faire ?")
    print("  [1] Lancer le pipeline complet")
    print("  [2] Tester un agent seul")
    print("  [3] Reprendre une session existante")
    print("  [4] Voir les sessions sauvegardees")
    print("  [q] Quitter")
    return input("\nChoix : ").strip().lower()


def menu_agents():
    agents = [
        ("planner",      "PlannerAgent      — spec produit"),
        ("architect",    "ArchitectAgent    — architecture technique"),
        ("code_planner", "CodePlannerAgent  — plan de fichiers"),
        ("codegen",      "CodegenAgent      — generation de code"),
        ("backend",      "BackendAgent      — migrations SQL + Edge Fn"),
        ("review",       "ReviewAgent       — revue et corrections"),
        ("test",         "TestAgent         — rapport de tests"),
        ("cicd",         "CICDAgent         — pipeline CI/CD"),
    ]
    print("\nQuel agent tester ?")
    for i, (key, label) in enumerate(agents, 1):
        print(f"  [{i}] {label}")
    choix = input("\nChoix : ").strip()
    try:
        idx = int(choix) - 1
        if 0 <= idx < len(agents):
            return agents[idx][0]
    except ValueError:
        pass
    return None


def sauvegarder_session(thread_id: str, meta: dict):
    """Sauvegarde les métadonnées d'une session dans un fichier JSON."""
    path = RUNS_DIR / f"{thread_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def lister_sessions():
    """Affiche les sessions sauvegardées."""
    sessions = list(RUNS_DIR.glob("*.json"))
    if not sessions:
        print("\n  Aucune session sauvegardee.")
        return []

    print(f"\n  {len(sessions)} session(s) trouvee(s) :\n")
    result = []
    for i, path in enumerate(sorted(sessions, reverse=True), 1):
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)
        print(f"  [{i}] {meta.get('thread_id', path.stem)}")
        print(f"       Date    : {meta.get('date', '?')}")
        print(f"       Prompt  : {meta.get('user_prompt', '?')[:60]}...")
        print(f"       Agents  : {', '.join(meta.get('completed_agents', []))}")
        print()
        result.append(meta)
    return result


def demander_inputs_pipeline() -> dict:
    """Demande à l'utilisateur les informations pour lancer le pipeline."""
    print("\n--- Configuration du pipeline ---\n")

    user_prompt = input(
        "Decrivez l'application a construire\n"
        "(ex: app de gestion de taches avec auth, profils et notifications)\n> "
    ).strip()

    template_path = input(
        "\nChemin vers le template Expo (laisser vide = dossier courant)\n> "
    ).strip() or "."

    project_path = input(
        "\nChemin de destination du projet genere (laisser vide = ./output)\n> "
    ).strip() or "./output"

    ux_images_raw = input(
        "\nChemins vers les maquettes UX (separes par des virgules, optionnel)\n> "
    ).strip()
    ux_images = [p.strip() for p in ux_images_raw.split(",") if p.strip()]

    return {
        "user_prompt": user_prompt,
        "template_path": template_path,
        "project_path": project_path,
        "ux_images": ux_images,
        "completed_agents": [],
        "errors": [],
        "current_agent": "",
        "spec": {},
        "architecture": {},
        "code_plan": {},
    }


# ===========================================================================
# ACTIONS PRINCIPALES
# ===========================================================================

def lancer_pipeline(thread_id: str = None):
    """Lance le pipeline complet avec tous les agents."""
    from Graph.graph import build_graph

    if not thread_id:
        thread_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    print(f"\n  Session ID : {thread_id}")
    print("  (Conservez cet ID pour reprendre la session si necessaire)\n")

    inputs = demander_inputs_pipeline()

    print(f"\n{'=' * 60}")
    print(f"  Lancement du pipeline")
    print(f"  Thread : {thread_id}")
    print(f"{'=' * 60}")

    # Sauvegarde les métadonnées de la session
    sauvegarder_session(thread_id, {
        "thread_id": thread_id,
        "date": datetime.now().isoformat(),
        "user_prompt": inputs["user_prompt"],
        "completed_agents": [],
    })

    graph = build_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # Lance le pipeline — LangGraph sauvegarde l'état après chaque nœud
    result = graph.invoke(inputs, config=config)

    print(f"\n{'=' * 60}")
    print("  Pipeline termine !")
    print(f"  Agents completes : {', '.join(result.get('completed_agents', []))}")
    if result.get("errors"):
        print(f"  Erreurs          : {'; '.join(result['errors'])}")
    print(f"{'=' * 60}")

    # Met à jour les métadonnées de la session
    sauvegarder_session(thread_id, {
        "thread_id": thread_id,
        "date": datetime.now().isoformat(),
        "user_prompt": inputs["user_prompt"],
        "completed_agents": result.get("completed_agents", []),
    })


def tester_agent_seul():
    """Teste un agent en isolation sans passer par le pipeline complet."""
    agent_key = menu_agents()
    if not agent_key:
        print("  Agent invalide.")
        return

    print(f"\n--- Test de {agent_key} ---\n")

    # Selon l'agent, on demande les inputs nécessaires
    if agent_key == "planner":
        prompt = input("Decrivez l'application :\n> ").strip()
        try:
            from Agents.Agent_Planner.agent import AgentPlanner
            agent = AgentPlanner()
            result = agent.run(prompt=prompt, ux_images=[])
            print(f"\nResultat :\n{result}")
        except ImportError:
            print("  [STUB] PlannerAgent pas encore implemente.")

    elif agent_key == "architect":
        spec = input("Entrez la spec (texte libre) :\n> ").strip()
        template_path = input("Chemin du template :\n> ").strip() or "."
        try:
            from Agents.Agent_Architect.agent import AgentArchitect
            agent = AgentArchitect()
            result = agent.run(spec=spec, template_path=template_path)
            print(f"\nResultat :\n{result}")
        except Exception as e:
            print(f"  Erreur : {e}")

    elif agent_key in ("code_planner", "codegen", "backend", "review", "test", "cicd"):
        print(f"  [STUB] {agent_key} pas encore implemente.")
        print("  Implementez l'agent puis relancez.")

    else:
        print("  Agent non reconnu.")


def reprendre_session():
    """Reprend une session existante depuis son état sauvegardé."""
    sessions = lister_sessions()
    if not sessions:
        return

    choix = input("Numero de la session a reprendre : ").strip()
    try:
        idx = int(choix) - 1
        if 0 <= idx < len(sessions):
            thread_id = sessions[idx]["thread_id"]
            lancer_pipeline(thread_id=thread_id)
        else:
            print("  Numero invalide.")
    except ValueError:
        print("  Entree invalide.")


# ===========================================================================
# BOUCLE PRINCIPALE
# ===========================================================================

def main():
    banner()

    while True:
        choix = menu_principal()

        if choix == "1":
            lancer_pipeline()

        elif choix == "2":
            tester_agent_seul()

        elif choix == "3":
            reprendre_session()

        elif choix == "4":
            lister_sessions()

        elif choix in ("q", "quit", "exit"):
            print("\n  Au revoir !\n")
            break

        else:
            print("  Choix invalide. Recommencez.")


if __name__ == "__main__":
    main()
