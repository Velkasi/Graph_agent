# Supabase — Reference Card

## Client Singleton (lib/supabaseClient.ts)
```ts
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.EXPO_PUBLIC_SUPABASE_URL!,
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!
)
```

## Auth
```ts
// Login / Register
await supabase.auth.signInWithPassword({ email, password })
await supabase.auth.signUp({ email, password, options: { data: { full_name } } })
await supabase.auth.signOut()

// Session
const { data: { session } } = await supabase.auth.getSession()

// Listener (in useEffect, returns cleanup)
const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
  setSession(session)
})
return () => subscription.unsubscribe()
```

## Database CRUD
```ts
// Read
const { data, error } = await supabase
  .from('tasks')
  .select('*, project:projects(name), assignee:users(full_name)')
  .eq('project_id', projectId)
  .order('created_at', { ascending: false })

// Create
const { data, error } = await supabase
  .from('tasks')
  .insert({ title, project_id, assigned_to: userId })
  .select()
  .single()

// Update
const { error } = await supabase
  .from('tasks')
  .update({ status, updated_at: new Date().toISOString() })
  .eq('id', id)

// Delete
const { error } = await supabase.from('tasks').delete().eq('id', id)
```

## Realtime Subscription
```ts
useEffect(() => {
  const channel = supabase
    .channel(`tasks-${projectId}`)
    .on('postgres_changes', {
      event: '*', schema: 'public', table: 'tasks',
      filter: `project_id=eq.${projectId}`
    }, (payload) => {
      // payload.eventType: 'INSERT' | 'UPDATE' | 'DELETE'
      refetch()
    })
    .subscribe()
  return () => { supabase.removeChannel(channel) }
}, [projectId])
```

## Storage (Avatars)
```ts
// Upload
const { error } = await supabase.storage
  .from('avatars')
  .upload(`${userId}.jpg`, file, { upsert: true, contentType: 'image/jpeg' })

// Public URL
const { data } = supabase.storage.from('avatars').getPublicUrl(`${userId}.jpg`)
const url = data.publicUrl
```
