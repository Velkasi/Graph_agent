# PlannerAgent

Premier agent du pipeline. Transforme un prompt utilisateur (texte libre +
éventuellement des maquettes UX) en spécification produit structurée au format JSON.

**Modèle :** mistral:7b-q4 (`config_mistral.json`)
**Statut :** À implémenter

---

## Rôle dans le pipeline

```
Utilisateur
     │
     │  user_prompt + ux_images
     ▼
[ PlannerAgent ]   ← ici
     │
     │  spec.json
     ▼
ArchitectAgent
```

---

## Entrée

| Paramètre | Type | Description |
|---|---|---|
| `prompt` | `str` | Description libre de l'application à construire |
| `ux_images` | `list[str]` | Chemins vers les maquettes / captures d'écran (optionnel) |

## Sortie attendue — `spec.json`

```json
{
  "app_name": "MonApp",
  "description": "Application de gestion de tâches collaborative",
  "screens": [
    { "name": "Accueil", "description": "Liste des tâches du jour" },
    { "name": "Profil",  "description": "Informations et préférences utilisateur" }
  ],
  "features": ["authentification", "tâches", "notifications", "partage"],
  "auth": true,
  "target_users": "Professionnels en équipe"
}
```

---

## Tools à implémenter

### `analyze_ux_image(image_path)`
Analyse une maquette UX et extrait la liste des écrans et composants visibles.
Utile pour guider la spec à partir de designs existants.

### `validate_spec(spec)`
Vérifie que la spec produite contient tous les champs obligatoires
avant de la passer à ArchitectAgent.

---

## Fichiers à créer

```
Agent_Planner/
├── agent.py    ← class AgentPlanner(BaseAgent)
├── tools.py    ← analyze_ux_image, validate_spec
└── README.md   ← ce fichier
```

---

## Template d'implémentation

```python
# agent.py
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from Agents.base_agent import BaseAgent
from Agents.Agent_Planner.tools import analyze_ux_image, validate_spec

class AgentPlanner(BaseAgent):
    def __init__(self):
        super().__init__("config_mistral")
        self.tools = [analyze_ux_image, validate_spec]
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=SystemMessage(content="..."),
        )

    def run(self, prompt: str, ux_images: list[str]) -> dict:
        message = f"Prompt : {prompt}\nImages : {ux_images}"
        result = self.agent.invoke({"messages": [("human", message)]})
        # Parser le JSON de la réponse finale
        return result["messages"][-1].content
```
