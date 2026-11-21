import { LOCALES, setLocale, t, useLocale, type Locale } from '../i18n'

/** English, French or Tunisian Arabic (Derja). The page reloads so every view, and what the
 * server sends (course text, the coach's replies), comes back in the new language. */
export function LanguagePicker({ variant = 'row' }: { variant?: 'row' | 'rail' }) {
  const locale = useLocale()
  const choose = (id: Locale) => {
    if (id === locale) return
    setLocale(id)
    window.location.reload()
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
