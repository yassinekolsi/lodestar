import { useSyncExternalStore } from 'react'

import { FR } from './fr'
import { TN } from './tn'

/** The three languages of the interface (backend/i18n.py has the same list).
 *
 * - `en`: English.
 * - `fr`: French. Tunisian university courses are taught in French.
 * - `tn`: Tunisian Arabic (Derja), in Arabic script, right to left. The course itself stays in
 *   French, the way Tunisian students study it; the interface and the coach speak Derja.
 *
 * The English text is the key: `t('Start studying')` returns the translation when there is one
 * and the English otherwise, so an untranslated string never breaks a screen. `{name}` in a
 * string is filled from `vars`. */
export type Locale = 'en' | 'fr' | 'tn'

export const LOCALES: { id: Locale; label: string; short: string }[] = [
  { id: 'en', label: 'English', short: 'EN' },
  { id: 'fr', label: 'Français', short: 'FR' },
  { id: 'tn', label: 'تونسي', short: 'تونسي' },
]

const KEY = 'lodestar.locale'
const TABLES: Record<Locale, Record<string, string>> = { en: {}, fr: FR, tn: TN }

function isLocale(value: string | null | undefined): value is Locale {
  return value === 'en' || value === 'fr' || value === 'tn'
}

/** `?lang=fr` (a shared demo link), then the saved choice, then the browser's language. */
function initial(): Locale {
  if (typeof window === 'undefined') return 'en'
  const fromUrl = new URLSearchParams(window.location.search).get('lang')
  if (isLocale(fromUrl)) {
    try {
      window.localStorage.setItem(KEY, fromUrl)
    } catch {
      // private mode: the choice lasts for this page only
    }
    return fromUrl
  }
  try {
    const saved = window.localStorage.getItem(KEY)
    if (isLocale(saved)) return saved
  } catch {
    // storage unavailable
  }
  const browser = (window.navigator.language || 'en').toLowerCase()
  if (browser.startsWith('fr')) return 'fr'
  if (browser.startsWith('ar')) return 'tn'
  return 'en'
}

let current: Locale = initial()
const listeners = new Set<() => void>()

/** `lang` and `dir` on <html>: Derja is written right to left. */
export function applyDocument(locale: Locale = current): void {
  if (typeof document === 'undefined') return
  document.documentElement.lang = locale === 'tn' ? 'ar-TN' : locale
  document.documentElement.dir = locale === 'tn' ? 'rtl' : 'ltr'
}

export function getLocale(): Locale {
  return current
}

export function setLocale(locale: Locale): void {
  if (locale === current) return
  current = locale
  try {
    window.localStorage.setItem(KEY, locale)
  } catch {
    // storage unavailable
  }
  applyDocument(locale)
  listeners.forEach((l) => {
    l()
  })
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Re-renders a component when the language changes. */
export function useLocale(): Locale {
  return useSyncExternalStore(subscribe, getLocale, (): Locale => 'en')
}

/** The interface text in the current language; the English text is the key. */
export function t(english: string, vars?: Record<string, string | number>): string {
  const text = TABLES[current][english] ?? english
  if (!vars) return text
  return text.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  )
}

/** "Good morning" and friends, by the hour. */
export function greeting(now: Date): string {
  const h = now.getHours()
  return t(h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening')
}
