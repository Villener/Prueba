import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App.jsx'
import { ToastProvider } from './ui/index.js'
import './styles.css'
import { iniciarTema } from './core/tema.js'
import iconoUrl from './assets/logo.svg'

// Fija el tema antes del primer pintado para que no parpadee.
iniciarTema()

// El icono de la pestana sale del MISMO archivo que el logo de la pantalla.
// Se pone desde aqui y no en index.html a proposito: en `public/` haria falta
// una segunda copia del svg, y dos copias se desincronizan -- que es justo lo
// que acaba de pasar.
for (const rel of ['icon', 'apple-touch-icon']) {
  const l = document.createElement('link')
  l.rel = rel
  l.href = iconoUrl
  document.head.appendChild(l)
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HashRouter>
      <ToastProvider>
        <App />
      </ToastProvider>
    </HashRouter>
  </React.StrictMode>
)
