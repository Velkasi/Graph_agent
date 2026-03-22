# BackendAgent

Génère les migrations SQL et les Edge Functions Supabase à partir du schéma
de base de données défini par ArchitectAgent.

**Modèle :** mistral:7b-q4 (`config_mistral.json`)
**Statut :** À implémenter

---

## Rôle dans le pipeline

```
ArchitectAgent
     │
     │  architecture.json (section "database")
     ▼
[ BackendAgent ]   ← ici   (en parallèle avec CodePlannerAgent)
     │
     │  migrations SQL + Edge Functions
     ▼
CodegenAgent (attend les deux branches)
```

---

## Entrée

| Paramètre | Type | Description |
|---|---|---|
| `architecture` | `dict` | Sortie de ArchitectAgent — section `database` utilisée |

## Sortie

Fichiers écrits sur le disque :

```
supabase/
├── migrations/
│   └── 001_initial_schema.sql    ← CREATE TABLE, types, contraintes
└── functions/
    └── send_notification/
        └── index.ts              ← Edge Function Deno
```

---

## Tools à implémenter

### `write_sql_migration(file_path, sql_content)`
Écrit un fichier de migration SQL dans `supabase/migrations/`.

### `write_edge_function(function_name, ts_content)`
Crée le dossier et le fichier `index.ts` d'une Edge Function.

### `run_supabase_cli(command)`
Exécute une commande Supabase CLI (ex: `supabase db push`).
Nécessite Supabase CLI installé sur la machine.

---

## Exemple de migration générée

```sql
-- 001_initial_schema.sql
CREATE TABLE tasks (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  title       text NOT NULL,
  completed   boolean DEFAULT false,
  created_at  timestamptz DEFAULT now()
);

-- RLS : chaque utilisateur ne voit que ses propres tâches
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_tasks" ON tasks
  FOR ALL USING (auth.uid() = user_id);
```

---

## Fichiers à créer

```
Agent_Backend/
├── agent.py    ← class AgentBackend(BaseAgent)
├── tools.py    ← write_sql_migration, write_edge_function, run_supabase_cli
└── README.md   ← ce fichier
```
