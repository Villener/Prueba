import { createContext, useCallback, useContext, useState } from 'react'

const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }) {
  const [t, setT] = useState(null)
  const show = useCallback((mensaje, tipo = 'ok') => {
    setT({ mensaje, tipo })
    setTimeout(() => setT(null), 3800)
  }, [])
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {t && <div className={`toast ${t.tipo}`} role="status">{t.mensaje}</div>}
    </ToastCtx.Provider>
  )
}
