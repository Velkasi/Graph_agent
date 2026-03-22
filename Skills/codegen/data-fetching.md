---
name: data-fetching
description: "Use this skill when the user needs to fetch, mutate, or cache data from Supabase using React Query. Triggers: useQuery, useMutation, queryClient, invalidateQueries, optimistic update, infinite scroll, pagination, Supabase select/insert/update/delete with React Query, cache, staleTime, prefetch."
---

# Data Fetching — React Query + Supabase

## Overview

This skill covers the standard patterns for combining React Query with Supabase:
- Setup and configuration of QueryClient
- useQuery for reads
- useMutation for writes (insert / update / delete)
- Cache invalidation and optimistic updates
- Pagination and infinite scroll
- Typed query keys

---

## 1. QueryClient Setup

```tsx
// app/_layout.tsx  (or wrap in a providers.tsx)
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,   // 5 minutes
      retry: 2,
      refetchOnWindowFocus: false,  // on mobile, use AppState instead
    },
  },
})

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* ...rest of providers */}
    </QueryClientProvider>
  )
}
```

---

## 2. Query Keys Convention

Always centralize query keys to avoid typos and simplify invalidation.

```ts
// lib/query-keys.ts
export const queryKeys = {
  profile: (userId: string) => ['profile', userId] as const,
  posts: {
    all: ['posts'] as const,
    list: (filters?: Record<string, unknown>) => ['posts', 'list', filters] as const,
    detail: (id: string) => ['posts', 'detail', id] as const,
    byUser: (userId: string) => ['posts', 'byUser', userId] as const,
  },
  comments: {
    byPost: (postId: string) => ['comments', 'byPost', postId] as const,
  },
}
```

---

## 3. useQuery — Reading Data

```ts
// hooks/use-profile.ts
import { useQuery } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import { queryKeys } from '../lib/query-keys'

export function useProfile(userId: string) {
  return useQuery({
    queryKey: queryKeys.profile(userId),
    queryFn: async () => {
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .single()

      if (error) throw error
      return data
    },
    enabled: !!userId,
  })
}
```

### Query with join

```ts
export function usePosts(filters?: { authorId?: string }) {
  return useQuery({
    queryKey: queryKeys.posts.list(filters),
    queryFn: async () => {
      let query = supabase
        .from('posts')
        .select(`id, title, body, created_at, author:profiles(id, username, avatar_url)`)
        .order('created_at', { ascending: false })

      if (filters?.authorId) query = query.eq('author_id', filters.authorId)

      const { data, error } = await query
      if (error) throw error
      return data
    },
  })
}
```

---

## 4. useMutation — Writing Data

### Insert

```ts
export function useCreatePost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (input: { title: string; body: string }) => {
      const { data, error } = await supabase
        .from('posts').insert(input).select().single()
      if (error) throw error
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.posts.all })
    },
  })
}
```

### Update

```ts
export function useUpdatePost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, ...updates }: { id: string; title?: string; body?: string }) => {
      const { data, error } = await supabase
        .from('posts').update(updates).eq('id', id).select().single()
      if (error) throw error
      return data
    },
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.posts.detail(data.id), data)
      queryClient.invalidateQueries({ queryKey: queryKeys.posts.all })
    },
  })
}
```

### Delete

```ts
export function useDeletePost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (postId: string) => {
      const { error } = await supabase.from('posts').delete().eq('id', postId)
      if (error) throw error
      return postId
    },
    onSuccess: (postId) => {
      queryClient.removeQueries({ queryKey: queryKeys.posts.detail(postId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.posts.all })
    },
  })
}
```

---

## 5. Optimistic Updates

```ts
export function useLikePost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (postId: string) => {
      const { error } = await supabase.from('likes').insert({ post_id: postId })
      if (error) throw error
    },
    onMutate: async (postId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.posts.detail(postId) })
      const previousPost = queryClient.getQueryData(queryKeys.posts.detail(postId))

      queryClient.setQueryData(queryKeys.posts.detail(postId), (old: any) => ({
        ...old,
        likes_count: old.likes_count + 1,
        liked_by_me: true,
      }))

      return { previousPost }
    },
    onError: (_err, postId, context) => {
      queryClient.setQueryData(queryKeys.posts.detail(postId), context?.previousPost)
    },
    onSettled: (_data, _err, postId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.posts.detail(postId) })
    },
  })
}
```

---

## 6. Infinite Scroll

```ts
import { useInfiniteQuery } from '@tanstack/react-query'

export function useInfinitePosts() {
  return useInfiniteQuery({
    queryKey: queryKeys.posts.list({ infinite: true }),
    queryFn: async ({ pageParam }) => {
      let query = supabase.from('posts').select('*')
        .order('created_at', { ascending: false }).limit(20)

      if (pageParam) query = query.lt('created_at', pageParam)

      const { data, error } = await query
      if (error) throw error
      return data
    },
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) =>
      lastPage.length === 20 ? lastPage[lastPage.length - 1].created_at : undefined,
  })
}

// Usage: data?.pages.flat() ?? []
```

---

## Best Practices

- **Always throw on Supabase error** — React Query needs thrown errors for `isError` to work.
- **Use `enabled`** to prevent queries running before required params are ready.
- **Centralize query keys** — invalidating a parent key invalidates all children.
- **Never** call `supabase` directly in components — always wrap in a hook.
- **Don't duplicate RLS logic** in frontend — rely on Supabase Row Level Security.
- Set `staleTime` per query: profiles = 5min+, feed = 1-2min.
