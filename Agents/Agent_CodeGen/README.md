# CodegenAgent

Exécute le plan de travail produit par CodePlannerAgent : lit les fichiers
existants du template et écrit les fichiers du projet final (création ou modification).

**Modèle :** deepseek-coder:7b-q4 (`config_deepseek.json`)
**Statut :** À implémenter

---

## Rôle dans le pipeline

```
CodePlannerAgent  +  BackendAgent
         │                │
         │  code_plan.json│
         └────────┬───────┘
                  ▼
         [ CodegenAgent ]   ← ici
                  │
                  │  fichiers écrits sur le disque
                  ▼
            ReviewAgent
```

---

## Entrée

| Paramètre | Type | Description |
|---|---|---|
| `code_plan` | `dict` | Sortie de CodePlannerAgent (liste ordonnée de tâches) |
| `project_path` | `str` | Chemin de destination du projet à générer |

## Sortie

Pas de retour JSON — l'agent écrit directement les fichiers sur le disque
dans `project_path`. ReviewAgent les lira ensuite.

---

## Tools à implémenter

### `read_file(file_path)`
Lit le contenu d'un fichier (template ou fichier déjà généré).

### `write_file(file_path, content)`
Écrit ou écrase un fichier sur le disque.
**Tool le plus critique du pipeline** — c'est lui qui produit le code final.

### `create_directory(dir_path)`
Crée un dossier si nécessaire avant d'y écrire des fichiers.

---

## Fonctionnement tâche par tâche

Pour chaque tâche du `code_plan`, l'agent :
1. Lit le fichier existant si `action == "MODIFIER"`
2. Génère le nouveau contenu avec le LLM
3. Écrit le fichier avec `write_file`
4. Passe à la tâche suivante (en respectant l'ordre et les dépendances)

---

## Fichiers à créer

```
Agent_Codegen/
├── agent.py    ← class AgentCodegen(BaseAgent)
├── tools.py    ← read_file, write_file, create_directory
└── README.md   ← ce fichier
```
