"""
main.py — Point d'entrée du projet
------------------------------------
Orchestration complète de l'Agent Architect :

  1. Discovery   — main.py pose les 19 questions via input()
  2. Récapitulatif — LLM produit le récapitulatif, attend confirmation
  3. Génération  — approche hybride après "oui" :
       a. LLM génère spec.json en texte pur  → Python sauvegarde
       b. LLM génère README.md en texte pur  → Python sauvegarde
       c. LLM génère migration.sql en texte  → Python sauvegarde
       d. LLM appelle create_project_file()  → fichiers .tsx/.ts vides uniquement
          (content="" ne contient pas de JSON imbriqué → pas d'erreur d'échappement)

Pourquoi hybride ?
  JSON imbriqué dans un argument JSON de tool call → double-échappement très
  peu fiable pour les LLM locaux. Les fichiers à contenu réel (spec, README, SQL)
  sont donc générés en texte pur et sauvegardés par Python.

Pour exécuter :
    python main.py
"""

import sys
import json
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from Agents.Agent_Architect.agent import AgentArchitect


# ─────────────────────────────────────────────
# Questions du discovery — posées par main.py
# ─────────────────────────────────────────────

PHASES = [
    {
        "titre": "PHASE 1 — Fondations",
        "questions": [
            ("Q1",  "Nom du projet ?"),
            ("Q2",  "Domaine métier ? (santé, éducation, RH, e-commerce, finance, logistique…)"),
            ("Q3",  "Multi-tenant (plusieurs organisations) ou mono-tenant ?"),
            ("Q4",  "Stack imposée ou libre ?\n     (défaut si libre : Expo Router / Supabase / React Query / TypeScript)"),
            ("Q5",  "Dossier cible de génération ? (chemin absolu, ex: C:/projets/monapp)"),
        ]
    },
    {
        "titre": "PHASE 2 — Utilisateurs et rôles",
        "questions": [
            ("Q6",  "Qui utilise l'application ? (types d'utilisateurs)"),
            ("Q7",  "Quels rôles distincts existent ?\n     (ex : admin / user, praticien / patient)"),
            ("Q8",  "Authentification : email/password, OAuth (Google, Apple), ou les deux ?"),
            ("Q9",  "Un utilisateur peut-il appartenir à plusieurs organisations ?"),
        ]
    },
    {
        "titre": "PHASE 3 — Fonctionnalités V1",
        "questions": [
            ("Q10", "Quelles sont les 3 fonctionnalités prioritaires pour la V1 ? (max 3)"),
            ("Q11", "Le contenu est-il généré par les utilisateurs ou fourni par la plateforme ?"),
            ("Q12", "Y a-t-il des médias ? (images, vidéos, PDF, audio)\n     Si oui : qui uploade ? qui accède ?"),
            ("Q13", "Y a-t-il un système de paiement ou d'abonnement en V1 ?"),
            ("Q14", "Y a-t-il des notifications (push, email, SMS) en V1 ?"),
        ]
    },
    {
        "titre": "PHASE 4 — Contraintes techniques",
        "questions": [
            ("Q15", "Hébergement médias : Supabase Storage / S3 / Cloudinary / YouTube / Vimeo / pas encore décidé ?"),
            ("Q16", "Services tiers prévus ? (Stripe, Twilio, SendGrid, autre)"),
            ("Q17", "Fonctionnement offline requis ?"),
            ("Q18", "Fonctionnalités temps-réel ? (chat, live updates, notifications push)"),
            ("Q19", "Contraintes de conformité ? (RGPD, HIPAA, ISO 27001)"),
        ]
    },
]

MOTS_CONFIRMATION = {"oui", "yes", "confirme", "ok", "go", "valide", "correct", "c'est bon"}


def poser_questions() -> dict[str, str]:
    """Pose les 19 questions directement via input(). Retourne les réponses."""
    print("=" * 60)
    print("  Agent Architect — Discovery")
    print("  Tapez 'exit' pour quitter à tout moment.")
    print("=" * 60)

    answers: dict[str, str] = {}

    for phase in PHASES:
        print(f"\n{'─' * 60}")
        print(f"  {phase['titre']}")
        print(f"{'─' * 60}")

        for q_id, question in phase["questions"]:
            while True:
                print(f"\n{q_id}. {question}")
                try:
                    reponse = input("> ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\nAu revoir.")
                    sys.exit(0)

                if reponse.lower() in ("exit", "quit", "sortir"):
                    print("Au revoir.")
                    sys.exit(0)

                if reponse:
                    answers[q_id] = reponse
                    break
                else:
                    print("  (réponse obligatoire)")

    return answers


def build_context(answers: dict[str, str]) -> str:
    """Formate toutes les réponses en un bloc structuré pour le LLM."""
    lines = [
        "Voici toutes les réponses du discovery. "
        "Produis le récapitulatif structuré, puis demande ma confirmation "
        "avant de générer les artefacts.\n",
        "=== RÉPONSES DISCOVERY ===",
    ]
    labels = {
        "Q1": "Nom du projet",         "Q2": "Domaine métier",
        "Q3": "Multi-tenant",          "Q4": "Stack",
        "Q5": "Dossier cible",         "Q6": "Types d'utilisateurs",
        "Q7": "Rôles distincts",       "Q8": "Authentification",
        "Q9": "Multi-org par user",    "Q10": "V1 features (3 max)",
        "Q11": "Source du contenu",    "Q12": "Médias",
        "Q13": "Paiement/abonnement",  "Q14": "Notifications",
        "Q15": "Hébergement médias",   "Q16": "Services tiers",
        "Q17": "Offline",              "Q18": "Temps-réel",
        "Q19": "Conformité",
    }
    for q_id, label in labels.items():
        lines.append(f"{q_id} — {label} : {answers.get(q_id, 'non précisé')}")
    lines.append("=== FIN ===")
    return "\n".join(lines)


def extraire_bloc(texte: str, balise: str) -> str:
    """Extrait un bloc de code markdown (```json, ```sql, etc.) ou le texte brut."""
    pattern = rf"```{balise}?\s*\n?(.*?)```"
    match = re.search(pattern, texte, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return texte.strip()


def sauvegarder(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  [OK] {path}")


def generer_artefacts(agent: AgentArchitect, messages: list, answers: dict) -> list:
    """
    Génération hybride :
      - spec.json, README.md, migration.sql → texte pur du LLM + sauvegarde Python
      - Fichiers .tsx/.ts vides → tool calls create_project_file (content="" sûr)
    """
    target = Path(answers.get("Q5", "./output").strip())
    target.mkdir(parents=True, exist_ok=True)

    print("\n" + "─" * 60)
    print("  Génération des artefacts...")
    print("─" * 60)

    # ── 1. spec.json ──────────────────────────────────────────────
    print("\n[1/3] Génération de spec.json...")
    spec_text, messages = agent.chat(
        messages,
        "Génère maintenant spec.json en JSON valide et complet. "
        "Réponds UNIQUEMENT avec le JSON brut, sans texte autour, sans balises markdown."
    )
    spec_raw = extraire_bloc(spec_text, "json")
    sauvegarder(target / "spec.json", spec_raw)
    try:
        spec = json.loads(spec_raw)
    except json.JSONDecodeError as e:
        print(f"  [WARN] spec.json invalide ({e}) — la structure de fichiers sera minimale")
        spec = {}

    # ── 2. README.md ──────────────────────────────────────────────
    print("\n[2/3] Génération de README.md...")
    readme_text, messages = agent.chat(
        messages,
        "Génère maintenant README.md complet en Markdown. "
        "Réponds UNIQUEMENT avec le contenu Markdown, sans balises supplémentaires."
    )
    sauvegarder(target / "README.md", extraire_bloc(readme_text, "md"))

    # ── 3. migration.sql ──────────────────────────────────────────
    print("\n[3/3] Génération de migration.sql...")
    sql_text, messages = agent.chat(
        messages,
        "Génère maintenant migration.sql complet avec RLS. "
        "Réponds UNIQUEMENT avec le SQL brut, sans balises markdown."
    )
    sql_raw = extraire_bloc(sql_text, "sql")
    sauvegarder(target / "migration.sql", sql_raw)
    sauvegarder(target / "supabase" / "migrations" / "001_init.sql", sql_raw)

    # ── 4. Fichiers .tsx/.ts vides via tools ──────────────────────
    print("\nCréation des fichiers vides via tools...")
    roles_raw = spec.get("roles", [])
    roles = [
        r.get("name", "user") if isinstance(r, dict) else str(r)
        for r in roles_raw
    ] or ["user"]
    roles_str = ", ".join(roles)
    response, messages = agent.chat(
        messages,
        f"Crée maintenant tous les fichiers .tsx et .ts vides avec create_project_file. "
        f"Dossier racine : {target}. "
        f"Rôles détectés : {roles_str}. "
        f"Pour chaque fichier : content=\"\" obligatoirement. "
        f"Crée au minimum : app/_layout.tsx, app/(auth)/login.tsx, app/(auth)/register.tsx, "
        f"app/(auth)/_layout.tsx, src/hooks/useCurrentUser.ts, "
        f"et un dossier app/(roleX)/ par rôle avec _layout.tsx et index.tsx."
    )
    print(response)

    print("\n" + "=" * 60)
    print(f"  Projet généré dans : {target}")
    print("=" * 60)

    return messages


def main():
    # Étape 1 — Discovery géré par main.py
    answers = poser_questions()

    print("\n" + "=" * 60)
    print("  Discovery terminé — Lancement de l'Agent Architect")
    print("=" * 60)

    agent = AgentArchitect()
    messages = []

    # Étape 2 — LLM produit le récapitulatif
    context = build_context(answers)
    response, messages = agent.chat(messages, context)
    print(f"\n{response}\n")

    # Étape 3 — Boucle de validation
    while True:
        try:
            user_input = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAu revoir.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "sortir"):
            print("Au revoir.")
            break

        # Confirmation → génération hybride
        if user_input.lower() in MOTS_CONFIRMATION:
            messages = generer_artefacts(agent, messages, answers)
            break

        # Correction → retour au LLM
        response, messages = agent.chat(messages, user_input)
        print(f"\n{response}\n")


if __name__ == "__main__":
    main()
