---
name: realtime-storage
description: "Use this skill when the user needs to implement real-time data synchronization or file uploads with Supabase. Triggers: Supabase Realtime, subscribe, channel, broadcast, presence, file upload, Storage, bucket, signed URL, image picker, avatar upload, live updates, useEffect subscription, invalidate on realtime."
---

# Realtime & Storage — Supabase

## Overview

This skill covers:
- Supabase Realtime: subscribing to database changes and presence
- Integration of Realtime with React Query (auto-invalidate cache on changes)
- Supabase Storage: uploading files, generating signed/public URLs
- Common patterns: avatar upload, image picker integration

---

## Part 1 — Realtime

### 1.1 Subscribe to Table Changes

```ts
// hooks/use-realtime-posts.ts
import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import { queryKeys } from '../lib/query-keys'

export function useRealtimePosts() {
  const queryClient = useQueryClient()

  useEffect(() => {
    const channel = supabase
      .channel('posts-changes')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'posts' },
        (payload) => {
          queryClient.invalidateQueries({ queryKey: queryKeys.posts.all })

          if (payload.eventType === 'UPDATE' || payload.eventType === 'DELETE') {
            const id = (payload.old as any).id
            queryClient.invalidateQueries({ queryKey: queryKeys.posts.detail(id) })
          }
        }
      )
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [queryClient])
}
```

---

### 1.2 Subscribe to a Specific Row

```ts
export function useRealtimePost(postId: string) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!postId) return

    const channel = supabase
      .channel(`post-${postId}`)
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'posts', filter: `id=eq.${postId}` },
        (payload) => {
          // Directly set cache — no refetch needed
          queryClient.setQueryData(queryKeys.posts.detail(postId), payload.new)
        }
      )
      .subscribe()

    return () => { supabase.removeChannel(channel) }
  }, [postId, queryClient])
}
```

---

### 1.3 Presence — Track Online Users

```ts
// hooks/use-presence.ts
import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export function usePresence(roomId: string, currentUser: { id: string; username: string }) {
  const [onlineUsers, setOnlineUsers] = useState<Record<string, any[]>>({})

  useEffect(() => {
    const channel = supabase.channel(`room:${roomId}`)

    channel
      .on('presence', { event: 'sync' }, () => {
        setOnlineUsers(channel.presenceState())
      })
      .subscribe(async (status) => {
        if (status === 'SUBSCRIBED') {
          await channel.track({ userId: currentUser.id, username: currentUser.username })
        }
      })

    return () => { supabase.removeChannel(channel) }
  }, [roomId, currentUser.id])

  return { onlineUsers }
}
```

---

### 1.4 Broadcast — Custom Events

```ts
// Send
await channel.send({
  type: 'broadcast',
  event: 'typing',
  payload: { userId: 'abc', isTyping: true },
})

// Listen
channel
  .on('broadcast', { event: 'typing' }, ({ payload }) => {
    console.log('Typing:', payload)
  })
  .subscribe()
```

---

## Part 2 — Storage

### 2.1 Bucket Setup (migration)

```sql
INSERT INTO storage.buckets (id, name, public) VALUES ('avatars', 'avatars', true);

CREATE POLICY "Users can upload their avatar" ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'avatars' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Public read access" ON storage.objects FOR SELECT
USING (bucket_id = 'avatars');
```

---

### 2.2 Upload a File

```ts
// lib/storage.ts
export async function uploadFile(
  bucket: string,
  path: string,        // e.g. "userId/avatar.jpg"
  file: Blob | File,
  contentType: string
): Promise<string> {
  const { error } = await supabase.storage
    .from(bucket)
    .upload(path, file, { contentType, upsert: true })

  if (error) throw error

  const { data } = supabase.storage.from(bucket).getPublicUrl(path)
  return data.publicUrl
}
```

---

### 2.3 Avatar Upload with expo-image-picker

```tsx
// hooks/use-avatar-upload.ts
import * as ImagePicker from 'expo-image-picker'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { decode } from 'base64-arraybuffer'
import { supabase } from '../lib/supabase'

export function useAvatarUpload(userId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
        base64: true,
      })

      if (result.canceled || !result.assets[0].base64) return null

      const asset = result.assets[0]
      const fileExt = asset.uri.split('.').pop() ?? 'jpg'
      const filePath = `${userId}/avatar.${fileExt}`

      const { error: uploadError } = await supabase.storage
        .from('avatars')
        .upload(filePath, decode(asset.base64), {
          contentType: asset.mimeType ?? 'image/jpeg',
          upsert: true,
        })

      if (uploadError) throw uploadError

      const { data } = supabase.storage.from('avatars').getPublicUrl(filePath)
      const avatarUrl = data.publicUrl + '?t=' + Date.now()  // cache-bust

      const { error: updateError } = await supabase
        .from('profiles').update({ avatar_url: avatarUrl }).eq('id', userId)
      if (updateError) throw updateError

      return avatarUrl
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile', userId] })
    },
  })
}
```

---

### 2.4 Signed URLs (private buckets)

```ts
export function useSignedUrl(bucket: string, path: string | null) {
  return useQuery({
    queryKey: ['signed-url', bucket, path],
    queryFn: async () => {
      const { data, error } = await supabase.storage
        .from(bucket).createSignedUrl(path!, 60)
      if (error) throw error
      return data.signedUrl
    },
    enabled: !!path,
    staleTime: 1000 * 50,  // Refresh before 60s expiry
  })
}
```

---

## Best Practices

- **Always unsubscribe** in `useEffect` cleanup (`supabase.removeChannel(channel)`).
- **Prefer server-side filters** (`filter: 'id=eq.xyz'`) over client-side filtering.
- **Combine Realtime + React Query**: use Realtime to trigger `invalidateQueries` — single source of truth.
- **Include user ID in storage paths** (`userId/filename.jpg`) to simplify RLS policies.
- **Public buckets** for avatars/public media; **private + signed URLs** for user documents.
- **Cache-bust public URLs** after re-upload: `url + '?t=' + Date.now()`.
