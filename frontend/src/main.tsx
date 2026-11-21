import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './app/App'
import { applyDocument } from './i18n'
import '@fontsource-variable/bricolage-grotesque/opsz.css'
import '@fontsource-variable/inter/opsz.css'
import '@fontsource-variable/geist-mono'
import './index.css'
import './games/games.css'

applyDocument() // lang and dir on <html> before the first paint

const root = document.getElementById('root')
if (!root) throw new Error('Missing #root element')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
