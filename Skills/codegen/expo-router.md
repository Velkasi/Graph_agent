# Expo Router — Reference Card

## File-Based Routing Structure
```
app/
  _layout.tsx           ← root layout (providers, auth redirect)
  (tabs)/
    _layout.tsx         ← tab bar config
    index.tsx           ← first tab
  [id].tsx              ← dynamic route
  Connexion.tsx         ← auth screens at root
```

## Navigation
```ts
import { useRouter, useLocalSearchParams, Link, Redirect } from 'expo-router'

const router = useRouter()
router.push('/screen')          // navigate (adds to stack)
router.replace('/screen')       // replace (no back button)
router.back()                   // go back

// Dynamic route params
const { id } = useLocalSearchParams<{ id: string }>()

// Declarative link
<Link href={`/details/${item.id}`}>Voir</Link>
```

## Protected Route Pattern (app/_layout.tsx)
```ts
import { Redirect } from 'expo-router'

if (loading) return null
if (!session) return <Redirect href="/Connexion" />
return <Stack />
```

## Screen Options
```ts
import { Stack } from 'expo-router'

// Inside component:
<Stack.Screen options={{ title: 'Titre', headerShown: false }} />
```

## Tab Navigation (_layout.tsx in (tabs)/)
```ts
import { Tabs } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'

export default function TabLayout() {
  return (
    <Tabs>
      <Tabs.Screen name="index" options={{ title: 'Projets',
        tabBarIcon: ({ color }) => <Ionicons name="folder" size={24} color={color} /> }} />
    </Tabs>
  )
}
```
