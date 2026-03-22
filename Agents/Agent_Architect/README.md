# ArchitectAgent

Traduit une spécification produit en architecture technique concrète,
exploitable directement par les agents suivants du pipeline.

**Modèle :** mistral:7b-q4 (`config_mistral.json`)
**Statut :** Implémenté

---

## Rôle dans le pipeline

```
PlannerAgent
     │
     │  spec.json
     ▼
[ ArchitectAgent ]   ← ici
     │
     │  architecture.json
     ├──────────────────► CodePlannerAgent
     └──────────────────► BackendAgent
```

---

## Entrée

| Paramètre | Type | Description |
|---|---|---|
| `spec` | `str` | Texte de la spec produit (sortie du PlannerAgent) |
| `template_path` | `str` | Chemin vers le dossier du template Expo |

## Sortie

Architecture technique structurée en Markdown avec 4 sections :

```
## 1. ÉCRANS (Expo Router)
  - Nom, route (/app/(tabs)/home.tsx), description

## 2. SCHÉMA BASE DE DONNÉES (Supabase)
  - Tables, colonnes avec types SQL, politiques RLS

## 3. HOOKS REACT QUERY
  - useQuery (lecture) / useMutation (écriture), table concernée, fichier

## 4. FICHIERS À MODIFIER / CRÉER
  - [MODIFIER] chemin/exact.tsx — ce qu'il faut changer
  - [CRÉER]    chemin/nouveau.tsx — ce qu'il faut créer
```

---

## Stratégie anti-hallucination

L'agent appelle `scan_template_tree` **en premier** pour obtenir
l'arborescence réelle du template. Il ne peut référencer que des fichiers
qui existent vraiment — pas de chemins inventés.

```
ArchitectAgent
      │
      ├─ 1. scan_template_tree(template_path)  → arborescence réelle
      │                                           "src/app/(tabs)/index.tsx"
      │
      ├─ 2. read_template_file(fichier)         → (optionnel) inspecte un fichier
      │
      └─ 3. Produit l'architecture avec chemins réels
```

---

## Tools disponibles

### `scan_template_tree(template_path, max_depth)`
Parcourt récursivement le template et retourne l'arborescence en texte.
Ignore automatiquement : `node_modules`, `.git`, `.expo`, `dist`, `build`.

### `read_template_file(file_path)`
Lit le contenu d'un fichier spécifique du template.
Tronque automatiquement les fichiers > 8 000 caractères.

---

## Fichiers

```
Agent_Architect/
├── agent.py    ← class AgentArchitect(BaseAgent)
├── tools.py    ← scan_template_tree, read_template_file
└── README.md   ← ce fichier
```

---

## Utilisation directe (hors pipeline)

```python
from Agents.Agent_Architect.agent import AgentArchitect

agent = AgentArchitect()
result = agent.run(
    spec="Application de gestion de tâches avec auth et projets partagés.",
    template_path="C:/projets/mon-template-expo"
)
print(result)
```

Ou via le CLI :
```
python cli.py → [2] Tester un agent seul → ArchitectAgent
```

---

## Prompt système

Le prompt impose un **format de sortie strict** (4 sections dans l'ordre).
C'est volontaire : la sortie est lue par `CodePlannerAgent` et `BackendAgent`
qui s'attendent à ce format précis.

Si tu modifies le prompt, assure-toi que les sections restent dans le même ordre.
