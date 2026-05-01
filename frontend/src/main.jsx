import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { NavigationBlockerProvider } from './contexts/NavigationBlockerContext'
import './index.css'
import './i18n'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <NavigationBlockerProvider>
        <App />
      </NavigationBlockerProvider>
    </BrowserRouter>
  </StrictMode>,
)
