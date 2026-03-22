# CICDAgent

Génère le fichier de pipeline CI/CD GitHub Actions adapté au projet Expo
généré (stack détectée automatiquement).

**Modèle :** phi3:3.8b-q5 (`config_phi.json`)
**Statut :** À implémenter

---

## Rôle dans le pipeline

```
ReviewAgent
     │
     │  project_path + stack info
     ▼
[ CICDAgent ]   ← ici   (en parallèle avec TestAgent)
     │
     │  .github/workflows/ci.yml
     ▼
    END
```

---

## Entrée

| Paramètre | Type | Description |
|---|---|---|
| `project_path` | `str` | Chemin du projet généré |

L'agent détecte la stack automatiquement en lisant `package.json`.

## Sortie

```
.github/
└── workflows/
    └── ci.yml    ← pipeline GitHub Actions
```

---

## Exemple de ci.yml généré

```yaml
name: CI

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npx tsc --noEmit
      - run: npx expo export
```

---

## Tools à implémenter

### `read_package_json(project_path)`
Lit `package.json` pour détecter la stack (Expo, version Node, dépendances).

### `write_file(file_path, content)`
Écrit le fichier `ci.yml` dans `.github/workflows/`.

---

## Fichiers à créer

```
Agent_CICD/
├── agent.py    ← class AgentCICD(BaseAgent)
├── tools.py    ← read_package_json, write_file
└── README.md   ← ce fichier
```
