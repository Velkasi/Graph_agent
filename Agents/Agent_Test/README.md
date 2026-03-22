# TestAgent

Lance les tests du projet généré et retourne un rapport JSON structuré.

**Modèle :** phi3:3.8b-q5 (`config_phi.json`)
**Statut :** À implémenter

---

## Rôle dans le pipeline

```
ReviewAgent
     │
     │  project_path
     ▼
[ TestAgent ]   ← ici   (en parallèle avec CICDAgent)
     │
     │  test_report.json
     ▼
    END
```

---

## Entrée

| Paramètre | Type | Description |
|---|---|---|
| `project_path` | `str` | Chemin du projet généré par CodegenAgent |

## Sortie — `test_report.json`

```json
{
  "status": "passed",
  "summary": {
    "total": 12,
    "passed": 11,
    "failed": 1,
    "skipped": 0
  },
  "failures": [
    {
      "test": "TaskList renders correctly",
      "error": "Cannot read properties of undefined (reading 'map')"
    }
  ],
  "commands_run": ["npm install", "npx expo export", "npm test"]
}
```

---

## Tools à implémenter

### `run_command(command, cwd)`
Exécute une commande shell dans le répertoire du projet et retourne
stdout + stderr + code de retour.

Utilisé pour :
- `npm install`
- `npx expo export` — vérifie que le build passe
- `npm test` — lance la suite de tests
- `curl` — teste les endpoints Edge Functions si applicable

### `read_test_results(project_path)`
Parse les résultats de tests (Jest JSON output) en un rapport structuré.

---

## Fichiers à créer

```
Agent_Test/
├── agent.py    ← class AgentTest(BaseAgent)
├── tools.py    ← run_command, read_test_results
└── README.md   ← ce fichier
```

---

## Note de sécurité

`run_command` exécute des commandes shell — limiter aux commandes `npm`,
`npx`, `expo` et `curl` uniquement. Ne jamais passer une commande
construite à partir d'une entrée utilisateur non validée.
