---
name: auth-navigation
description: "Use this skill when the user needs to implement authentication, session management, or protected navigation in an Expo Router + Supabase app. Triggers: login, signup, logout, OAuth, protected routes, auth guard, session, redirect on auth, layout groups, tab navigation with auth, conditional navigation."
---

# Auth & Navigation — Expo Router + Supabase

## Overview

This skill covers the full auth + navigation pattern:
- Supabase Auth (email/password, OAuth, magic link)
- Session persistence and listening
- Protected routes via Expo Router layout groups
- Conditional navigation based on auth state

---

## Project Structure

```
app/
├── _layout.tsx              # Root layout — session provider
├── (auth)/
│   ├── _layout.tsx          # Unauthenticated stack
│   ├── sign-in.tsx
│   └── sign-up.tsx
├── (app)/
│   ├── _layout.tsx          # Authenticated stack (protected)
│   ├── (tabs)/
│   │   ├── _layout.tsx
│   │   ├── home.tsx
│   │   └── profile.tsx
│   └── settings.tsx
lib/
├── supabase.ts              # Supabase client
└── auth-context.tsx         # Session context
```

---

## 1. Supabase Client Setup

```ts
// lib/supabase.ts
import { createClient } from '@supabase/supabase-js'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { AppState } from 'react-native'

export const supabase = createClient(
  process.env.EXPO_PUBLIC_SUPABASE_URL!,
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!,
  {
    auth: {
      storage: AsyncStorage,
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
    },
  }
)

// Refresh token when app comes back to foreground
AppState.addEventListener('change', (state) => {
  if (state === 'active') {
    supabase.auth.startAutoRefresh()
  } else {
    supabase.auth.stopAutoRefresh()
  }
})
```

---

## 2. Auth Context

```tsx
// lib/auth-context.tsx
import { createContext, useContext, useEffect, useState } from 'react'
import { Session } from '@supabase/supabase-js'
import { supabase } from './supabase'

type AuthContextType = {
  session: Session | null
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType>({
  session: null,
  isLoading: true,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setIsLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  return (
    <AuthContext.Provider value={{ session, isLoading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
```

---

## 3. Root Layout — Session Guard

```tsx
// app/_layout.tsx
import { Slot, useRouter, useSegments } from 'expo-router'
import { useEffect } from 'react'
import { AuthProvider, useAuth } from '../lib/auth-context'

function InitialLayout() {
  const { session, isLoading } = useAuth()
  const segments = useSegments()
  const router = useRouter()

  useEffect(() => {
    if (isLoading) return

    const inAuthGroup = segments[0] === '(auth)'

    if (!session && !inAuthGroup) {
      router.replace('/(auth)/sign-in')
    } else if (session && inAuthGroup) {
      router.replace('/(app)/(tabs)/home')
    }
  }, [session, isLoading, segments])

  return <Slot />
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <InitialLayout />
    </AuthProvider>
  )
}
```

---

## 4. Sign In Screen

```tsx
// app/(auth)/sign-in.tsx
import { useState } from 'react'
import { View, TextInput, Button, Text, Alert } from 'react-native'
import { supabase } from '../../lib/supabase'

export default function SignIn() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSignIn() {
    setLoading(true)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) Alert.alert('Erreur', error.message)
    setLoading(false)
    // Navigation handled automatically by root layout guard
  }

  return (
    <View>
      <TextInput value={email} onChangeText={setEmail} placeholder="Email" autoCapitalize="none" />
      <TextInput value={password} onChangeText={setPassword} placeholder="Mot de passe" secureTextEntry />
      <Button title={loading ? 'Connexion...' : 'Se connecter'} onPress={handleSignIn} disabled={loading} />
    </View>
  )
}
```

---

## 5. Sign Out

```ts
async function handleSignOut() {
  const { error } = await supabase.auth.signOut()
  // Root layout guard will automatically redirect to (auth)
}
```

---

## 6. Authenticated Tab Layout

```tsx
// app/(app)/(tabs)/_layout.tsx
import { Tabs } from 'expo-router'
import { useAuth } from '../../../lib/auth-context'

export default function TabsLayout() {
  const { session } = useAuth()
  if (!session) return null

  return (
    <Tabs>
      <Tabs.Screen name="home" options={{ title: 'Accueil' }} />
      <Tabs.Screen name="profile" options={{ title: 'Profil' }} />
    </Tabs>
  )
}
```

---

## Best Practices

- **Never** check `session` in individual screens — use layout groups + root layout guard.
- Use `router.replace()` (not `router.push()`) for auth redirects to avoid back navigation to auth screens.
- Always handle `isLoading` to avoid flash of unauthenticated content.
- Store Supabase keys in `.env` as `EXPO_PUBLIC_*` variables.
- Use `AsyncStorage` (not `localStorage`) for session persistence in React Native.
- Prefer `onAuthStateChange` over polling — it handles token refresh automatically.
