import { LOCALES, setLocale, t, useLocale, type Locale } from '../i18n'

/** English, French or Tunisian Arabic (Derja). No reload: the app stays on the open panel, which
 * remounts and fetches again so what the server sends (course text, replies) is in the new
 * language too (App.tsx keys the panel by locale). */
export function LanguagePicker({ variant = 'row' }: { variant?: 'row' | 'rail' }) {
  const locale = useLocale()
  const choose = (id: Locale) => {
    if (id === locale) return
    setLocale(id)
  }
  return (
    <div
      className={`lang-picker lang-picker--${variant}`}
      role="group"
      aria-label={t('Language')}
      data-testid="language-picker"
    >
      {LOCALES.map((l) => (
        <button
          key={l.id}
          type="button"
          className="lang-picker__b"
          aria-pressed={locale === l.id}
          lang={l.id === 'tn' ? 'ar-TN' : l.id}
          title={l.label}
          onClick={() => {
            choose(l.id)
          }}
        >
          {variant === 'rail' ? l.short : l.label}
        </button>
      ))}
    </div>
  )
}
