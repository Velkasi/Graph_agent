# ReviewAgent

Vérifie la qualité du code généré par CodegenAgent : détecte les erreurs
TypeScript, les incohérences avec la spec, et corrige automatiquement si possible.

**Modèle :** deepseek-coder:7b-q4 (`config_deepseek.json`)
**Statut :** À implémenter

---

## Rôle dans le pipeline

```
CodegenAgent
     │
     │  fichiers générés + spec
     ▼
[ ReviewAgent ]   ← ici
     │
     ├──────────────────► TestAgent
     └──────────────────► CICDAgent
```

---

## Entrée

| Paramètre | Type | Description |
|---|---|---|
| `project_path` | `str` | Chemin du projet généré par CodegenAgent |
| `spec` | `dict` | Spec originale du PlannerAgent — référence de validation |

## Sortie

- Corrections appliquées directement sur les fichiers du projet
- Rapport de revue : fichiers modifiés, problèmes détectés, statut final

---

## Ce que l'agent vérifie

| Vérification | Outil |
|---|---|
| Erreurs TypeScript | `run_tsc` — compile avec `tsc --noEmit` |
| Cohérence avec la spec | LLM compare spec et fichiers générés |
| Imports manquants | Lecture + analyse des fichiers |
| Routes Expo Router | Vérifie que chaque écran de la spec a son fichier |

---

## Tools à implémenter

### `read_file(file_path)`
Lit un fichier généré pour le soumettre à l'analyse.

### `write_file(file_path, content)`
Applique une correction sur un fichier.

### `run_tsc(project_path)`
Lance `tsc --noEmit` et retourne les erreurs TypeScript.

### `list_project_files(project_path)`
Liste tous les fichiers `.ts` / `.tsx` du projet.

---

## Fichiers à créer

```
Agent_Review/
├── agent.py    ← class AgentReview(BaseAgent)
├── tools.py    ← read_file, write_file, run_tsc, list_project_files
└── README.md   ← ce fichier
```
