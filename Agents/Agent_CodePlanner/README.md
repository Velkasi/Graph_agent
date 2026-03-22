# CodePlannerAgent

Reçoit l'architecture technique et l'arborescence du template pour produire
un plan de travail précis : liste ordonnée des fichiers à créer ou modifier,
avec pour chacun le contenu attendu.

**Modèle :** deepseek-coder:7b-q4 (`config_deepseek.json`)
**Statut :** À implémenter

---

## Rôle dans le pipeline

```
ArchitectAgent
     │
     │  architecture.json + template tree
     ▼
[ CodePlannerAgent ]   ← ici
     │
     │  code_plan.json
     ▼
CodegenAgent
```

---

## Entrée

| Paramètre | Type | Description |
|---|---|---|
| `architecture` | `dict` | Sortie de ArchitectAgent (écrans, DB, hooks, fichiers) |
| `template_path` | `str` | Chemin vers le template Expo pour référencer les fichiers réels |

## Sortie attendue — `code_plan.json`

```json
{
  "tasks": [
    {
      "order": 1,
      "action": "MODIFIER",
      "file": "src/app/(tabs)/index.tsx",
      "description": "Ajouter la liste des tâches avec useQuery",
      "depends_on": []
    },
    {
      "order": 2,
      "action": "CRÉER",
      "file": "src/hooks/useTasks.ts",
      "description": "Hook React Query pour lire la table 'tasks'",
      "depends_on": [1]
    }
  ]
}
```

---

## Tools à implémenter

Mêmes tools que ArchitectAgent (accès au template) :

### `scan_template_tree(template_path)`
Arborescence du template — pour référencer les fichiers existants.

### `read_template_file(file_path)`
Lit un fichier du template — pour comprendre la structure avant de planifier.

---

## Fichiers à créer

```
Agent_CodePlanner/
├── agent.py    ← class AgentCodePlanner(BaseAgent)
├── tools.py    ← scan_template_tree, read_template_file
└── README.md   ← ce fichier
```

> Les tools `scan_template_tree` et `read_template_file` sont déjà implémentés
> dans `Agent_Architect/tools.py`. Tu peux les importer directement plutôt que
> de les réécrire.
