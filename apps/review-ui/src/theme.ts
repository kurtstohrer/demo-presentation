// Light, dark, or follow the OS. Sets data-theme on <html> and remembers the choice.

export type ThemeChoice = 'system' | 'light' | 'dark'

export interface ThemeController {
  readonly choice: ThemeChoice
  set(choice: ThemeChoice): void
  onChange(listener: (choice: ThemeChoice) => void): () => void
}

const KEY = 'demo-review:theme'

export function initTheme(): ThemeController {
  const media = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: light)') : null
  const listeners = new Set<(choice: ThemeChoice) => void>()
  const valid = (c: unknown): c is ThemeChoice => c === 'system' || c === 'light' || c === 'dark'
  let stored: string | null = null
  try { stored = localStorage.getItem(KEY) } catch { /* private window */ }
  let choice: ThemeChoice = valid(stored) ? stored : 'system'

  function apply(): void {
    const shown = choice === 'system' ? (media?.matches ? 'light' : 'dark') : choice
    document.documentElement.setAttribute('data-theme', shown)
    for (const listener of listeners) listener(choice)
  }
  media?.addEventListener('change', () => { if (choice === 'system') apply() })
  apply()

  return {
    get choice() { return choice },
    set(next) {
      choice = valid(next) ? next : 'system'
      try { localStorage.setItem(KEY, choice) } catch { /* shown, not remembered */ }
      apply()
    },
    onChange(listener) { listeners.add(listener); return () => listeners.delete(listener) },
  }
}
