# Workflow IA — Générateur d'application mobile

Système multi-agents qui transforme un prompt utilisateur en application
**Expo Router + Supabase + React Query** complète et fonctionnelle.

---

## Vue d'ensemble du pipeline

```
Utilisateur
    │
    │  user_prompt + ux_images
    ▼
┌─────────────┐
│ PlannerAgent│  mistral:7b-q4
│             │  Traduit le prompt en spec produit structurée
└──────┬──────┘
       │  spec.json
       ▼
┌─────────────────┐
│ ArchitectAgent  │  mistral:7b-q4
│                 │  Traduit la spec en architecture technique :
│                 │  écrans (routes Expo), schéma DB Supabase, hooks
└────────┬────────┘
         │  architecture.json
         │
    ┌────┴────┐  (en parallèle)
    │         │
    ▼         ▼
┌──────────┐  ┌─────────────┐
│CodePlann.│  │ BackendAgent│  deepseek + mistral
│          │  │             │  CodePlanner : plan des fichiers à créer
│          │  │             │  BackendAgent : migrations SQL + Edge Fn
└────┬─────┘  └──────┬──────┘
     │  code_plan    │  migrations SQL
     └────────┬──────┘
              │
              ▼
      ┌───────────────┐
      │  CodegenAgent │  deepseek-coder:7b-q4
      │               │  Écrit les fichiers du projet
      └───────┬───────┘
              │  fichiers modifiés
              ▼
      ┌───────────────┐
      │  ReviewAgent  │  deepseek-coder:7b-q4
      │               │  Vérifie, corrige, valide (tsc, lint)
      └───────┬───────┘
              │
         ┌────┴────┐  (en parallèle)
         │         │
         ▼         ▼
  ┌──────────┐  ┌──────────┐
  │TestAgent │  │CICDAgent │  phi3:3.8b-q5
  │          │  │          │  TestAgent : rapport de tests JSON
  │          │  │          │  CICDAgent : .github/workflows/ci.yml
  └──────────┘  └──────────┘
```

---

## Table des agents

| Agent | Modèle | Entrée | Sortie | Statut |
|---|---|---|---|---|
| PlannerAgent | mistral:7b-q4 | user_prompt + ux_images | spec.json | À implémenter |
| ArchitectAgent | mistral:7b-q4 | spec.json | architecture.json | Implémenté |
| CodePlannerAgent | deepseek-coder:7b-q4 | architecture.json + template | code_plan.json | À implémenter |
| CodegenAgent | deepseek-coder:7b-q4 | code_plan.json + fichiers | Fichiers modifiés | À implémenter |
| BackendAgent | mistral:7b-q4 | architecture.json (tables) | Migrations SQL + Edge Fn | À implémenter |
| ReviewAgent | deepseek-coder:7b-q4 | Fichiers + spec | Corrections / validation | À implémenter |
| CICDAgent | phi3:3.8b-q5 | project_path + stack | ci.yml | À implémenter |
| TestAgent | phi3:3.8b-q5 | project_path | Test report JSON | À implémenter |

---

## Structure du projet

```
01_First_Agent/
│
├── cli.py                      ← Point d'entrée — interface terminal
│
├── Agents/                     ← Un dossier par agent
│   ├── base_agent.py           ← Classe parente commune (connexion LLM)
│   ├── Agent_Planner/
│   ├── Agent_Architect/        ← Implémenté
│   ├── Agent_CodePlanner/
│   ├── Agent_Codegen/
│   ├── Agent_Backend/
│   ├── Agent_Review/
│   ├── Agent_CICD/
│   └── Agent_Test/
│
├── Graph/
│   ├── state.py                ← État partagé (TypedDict)
│   └── graph.py                ← Pipeline LangGraph + persistence SQLite
│
├── Config/                     ← Un fichier par modèle LLM
│   ├── config_mistral.json
│   ├── config_deepseek.json
│   ├── config_phi.json
│   └── config_local.json       ← Serveur local (liquid/lfm2.5-1.2b)
│
├── Utils/
│   └── config_loader.py        ← Charge les fichiers de config
│
├── runs/                       ← Créé automatiquement
│   └── workflow_memory.db      ← Persistence SQLite (sessions LangGraph)
│
└── requirements.txt
```

---

## Lancer le projet

```bash
# Activer l'environnement virtuel
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Mac / Linux

# Lancer le CLI interactif
python cli.py
```

### Menu du CLI

```
[1] Pipeline complet      → lance tous les agents dans l'ordre
[2] Tester un agent seul  → teste un agent en isolation (utile pendant le dev)
[3] Reprendre une session → reprend une session depuis son dernier état
[4] Voir les sessions     → liste les sessions sauvegardées
[q] Quitter
```

---

## Concepts clés

### État partagé (WorkflowState)

Toutes les données circulent dans un seul objet `WorkflowState` défini dans
`Graph/state.py`. Chaque agent lit ce dont il a besoin et y écrit sa sortie.

```
WorkflowState
├── user_prompt       ← entrée utilisateur
├── spec              ← rempli par PlannerAgent
├── architecture      ← rempli par ArchitectAgent
├── code_plan         ← rempli par CodePlannerAgent
├── template_path     ← chemin du template Expo
├── project_path      ← chemin du projet généré
├── completed_agents  ← liste qui s'accumule
└── errors            ← erreurs rencontrées
```

### Persistence (SQLite)

Chaque session a un `thread_id` unique. LangGraph sauvegarde l'état après
chaque agent dans `runs/workflow_memory.db`. Si un agent plante, on peut
reprendre exactement où on s'est arrêté sans tout relancer.

### Stubs

Les agents non encore implémentés sont des stubs dans `Graph/graph.py`.
Le pipeline tourne quand même avec des données simulées. À mesure qu'on
implémente un agent, le stub est remplacé automatiquement.

### Ajout d'un nouvel agent

1. Créer `Agents/Agent_Nom/agent.py` avec une classe héritant de `BaseAgent`
2. Créer `Agents/Agent_Nom/tools.py` avec les tools spécifiques
3. Dans `Graph/graph.py`, remplacer le stub correspondant par l'import réel

---

## Dépendances

```
langchain            → framework LLM de base
langchain-openai     → client compatible API OpenAI (pour serveur local)
langgraph            → pipeline multi-agents avec graphe d'états
langgraph-checkpoint-sqlite  → persistence SQLite entre sessions
anthropic            → SDK Anthropic (optionnel)
sqlite-utils         → utilitaires SQLite
```

Installation :
```bash
pip install -r requirements.txt
```
