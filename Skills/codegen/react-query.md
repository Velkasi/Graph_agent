# React Query — Reference Card

## Setup (app/_layout.tsx)
```ts
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60,       // 1 min before refetch
      networkMode: 'offlineFirst', // serve cache when offline
      retry: 2,
    },
  },
})

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <Stack />
    </QueryClientProvider>
  )
}
```

## useQuery
```ts
import { useQuery, useQueryClient } from '@tanstack/react-query'

const { data: tasks = [], isLoading, error, refetch } = useQuery({
  queryKey: ['tasks', projectId],         // cache key — array for invalidation
  queryFn: async () => {
    const { data, error } = await supabase
      .from('tasks')
      .select('*')
      .eq('project_id', projectId)
    if (error) throw error
    return data
  },
  enabled: !!projectId,                   // only run if projectId is set
})
```

## useMutation
```ts
import { useMutation, useQueryClient } from '@tanstack/react-query'

const queryClient = useQueryClient()

const createTask = useMutation({
  mutationFn: async (payload: Partial<Task>) => {
    const { data, error } = await supabase
      .from('tasks')
      .insert(payload)
      .select()
      .single()
    if (error) throw error
    return data
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
  },
})

// Call:
createTask.mutate({ title, project_id, assigned_to })
// or async:
await createTask.mutateAsync({ title, project_id })
```

## Hook Return Pattern
```ts
return {
  tasks,
  isLoading,
  error: error?.message ?? null,
  createTask: createTask.mutate,
  updateTask: updateTask.mutate,
  deleteTask: deleteTask.mutate,
  refetch,
}
```
