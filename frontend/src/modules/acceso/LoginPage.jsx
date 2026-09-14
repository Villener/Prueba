/** Modulo Acceso - CU-GEN-01 de docs/casos-de-uso.md
 *
 * La pantalla es la MISMA en desarrollo y en produccion, y eso es deliberado.
 *
 * Antes traia un panel con la lista del personal del taller para rellenar el
 * correo de un clic, visible solo con `npm run dev`. Era comodo, pero tenia dos
 * costos que no valian la comodidad:
 *
 *   1. La pantalla que se probaba a diario NO era la que ve el usuario. El
 *      panel empujaba el formulario hacia arriba, asi que los problemas de
 *      espaciado solo aparecian ya servido por Docker, que es el peor momento
 *      para descubrirlos.
 *   2. Publicaba la plantilla real --nueve personas con nombre y puesto-- en la
 *      unica pantalla que se ve sin haber iniciado sesion.
 *
 * Las cuentas de prueba viven en el README, que es donde se buscan sin tener
 * que abrir la aplicacion.
 */
import { useState } from 'react'
import { login } from '../../core/api.js'
import { Aviso, Card } from '../../ui/index.js'
import { Logo } from '../../ui/Logo.jsx'

export default function Login({ onEntrar }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [cargando, setCargando] = useState(false)

  const enviar = async (e) => {
    e.preventDefault()
    setCargando(true)
    setError(null)
    try {
      onEntrar(await login(email, password))
    } catch (err) {
      setError(err.message)
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div style={{ display: 'flex', flexDirection: 'column',
                      alignItems: 'center', marginBottom: 18 }}>
          <Logo alto={54} />
          <p style={{ color: 'var(--ink-2)', fontSize: '.88rem', marginTop: 10 }}>
            Gestión de Flota y Taller
          </p>
        </div>

        <Card>
          <form onSubmit={enviar}>
            <Aviso tipo="err">{error}</Aviso>
            <div className="field">
              <label htmlFor="email">Correo</label>
              <input id="email" type="email" value={email} autoComplete="username"
                     autoFocus onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="pwd">Contraseña</label>
              <input id="pwd" type="password" value={password} autoComplete="current-password"
                     onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button className="btn primary block" disabled={cargando}>
              {cargando ? 'Entrando…' : 'Entrar'}
            </button>
          </form>
        </Card>
      </div>
    </div>
  )
}
