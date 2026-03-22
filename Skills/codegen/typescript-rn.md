# TypeScript + React Native — Reference Card

## Component Structure
```ts
import { FC } from 'react'
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native'

interface Props {
  title: string
  onPress: () => void
  disabled?: boolean
}

const MyComponent: FC<Props> = ({ title, onPress, disabled = false }) => {
  return (
    <TouchableOpacity style={[styles.btn, disabled && styles.disabled]} onPress={onPress} disabled={disabled}>
      <Text style={styles.label}>{title}</Text>
    </TouchableOpacity>
  )
}

const styles = StyleSheet.create({
  btn:      { backgroundColor: '#6366F1', padding: 16, borderRadius: 8, alignItems: 'center' },
  disabled: { opacity: 0.5 },
  label:    { color: '#fff', fontWeight: '600', fontSize: 16 },
})

export default MyComponent
```

## Entity Interface Pattern (types/index.ts)
```ts
export interface Task {
  id: string               // uuid — gen_random_uuid()
  created_at: string       // timestamptz
  updated_at: string
  title: string
  status: 'todo' | 'in_progress' | 'done'
  priority: 'low' | 'medium' | 'high'
  project_id: string       // FK → projects.id
  assigned_to: string | null  // FK → users.id
}
```

## Screen with Loading / Error States
```ts
if (isLoading) return (
  <View style={styles.center}><ActivityIndicator size="large" color="#6366F1" /></View>
)
if (error) return (
  <View style={styles.center}><Text style={styles.errorText}>{error}</Text></View>
)
```

## TextInput Pattern
```ts
const [email, setEmail] = useState('')
const [password, setPassword] = useState('')

<TextInput
  style={styles.input}
  placeholder="Email"
  value={email}
  onChangeText={setEmail}
  autoCapitalize="none"
  keyboardType="email-address"
/>
<TextInput
  style={styles.input}
  placeholder="Mot de passe"
  value={password}
  onChangeText={setPassword}
  secureTextEntry
/>
```

## Strict Null Safety
```ts
const label = item?.name ?? 'Sans nom'    // nullish coalescing
const isValid = value != null             // non-null check
const items = data ?? []                  // default to empty array
```
