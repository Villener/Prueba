/** Modulo Acceso - CU-GEN-01 de docs/casos-de-uso.md */
import { useState } from 'react'
import { login } from '../../core/api.js'
import { Aviso, Card } from '../../ui/index.js'
import { Logo } from '../../ui/Logo.jsx'

/* Personas REALES con su número de empleado. Antes esta lista eran nombres
   inventados —"Luis Barrera Soto", "Ana Villalobos Rey"— que no existen en
   ningún archivo del cliente y que, por parecer reales, nadie cuestionaba.

   Los 297 choferes y los 13 supervisores los crea el importador desde
   "INFO CHOFERES 2026 ACTUAL.xlsx". Aquí va UNO de cada uno, como puerta de
   entrada al demo; los demás se buscan por su correo.

   Convención de correo, la misma para todos:
     con número de empleado  ->  e<num>@bajagas.mx
     sin número (supervisores, que en el Excel no lo traen)
                             ->  <nombre+sucursal sin espacios, 12 letras>@bajagas.mx */
const CUENTAS = [
  ['gerente@bajagas.mx', 'Luis Siscareño', 'Gerente · falta su número de empleado'],
  ['e925@bajagas.mx', 'Erick Ávalos', 'Compras y enlace con gerencia'],
  ['e10853@bajagas.mx', 'Pedro Montaño', 'Piso de taller y almacén'],
  ['e647@bajagas.mx', 'Víctor Sallas', 'Agenda de mantenimiento'],
  ['e11807@bajagas.mx', 'Pablo Reyes', 'Operativo · suplente'],
  ['e13905@bajagas.mx', 'Jaime Yair Domínguez', 'Capturista de datos · requisiciones'],
  ['ricardoandre@bajagas.mx', 'Ricardo Andrés Flores', 'Supervisor de Carranza · 55 choferes'],
  ['e3145@bajagas.mx', 'Blas Mauricio Cota', 'Chofer de reparto · unidad 1009, Tecate'],
  ['e4932@bajagas.mx', 'Rubén Espejo', 'Montacarguista'],
]

/* El panel de cuentas y la contraseña pre-escrita SOLO existen en desarrollo.
   `import.meta.env.DEV` es true con `npm run dev` y false en `npm run build`,
   que es lo que sirve Docker y lo que sale por el túnel.

   No es una precaución teórica: esta pantalla publicaba el subtítulo "Todos
   usan la contraseña bajagas2026" junto a la lista del personal real. En la
   red de la casa daba igual; con una URL pública, cualquiera que diera con
   ella entraba como gerente y veía los datos de 335 empleados. La comodidad de
   no teclear la contraseña en el demo no vale eso. */
const EN_DESARROLLO = import.meta.env.DEV

export default function Login({ onEntrar }) {
  const [email, setEmail] = useState(EN_DESARROLLO ? 'gerente@bajagas.mx' : '')
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
                     onChange={(e) => setEmail(e.target.value)} required />
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

        {EN_DESARROLLO && (
          <Card title="Personal del taller" sub="Solo en desarrollo · rellena el correo">
            <div className="demo-users">
              {CUENTAS.map(([correo, rol, desc]) => (
                <button key={correo} type="button" onClick={() => setEmail(correo)}>
                  <strong>{rol}</strong><br />
                  <span style={{ color: 'var(--muted)' }}>{desc}</span>
                </button>
              ))}
            </div>
            <p className="rule">
              Arriba va <strong>una</strong> persona por perfil. Los <strong>297 choferes</strong> y
              los <strong>13 supervisores</strong> también tienen cuenta: los crea el importador
              desde el Excel, con correo <code>e&lt;núm. empleado&gt;@bajagas.mx</code>.
              Los mecánicos de Álamos no tienen cuenta: no usan la aplicación, y por eso el
              administrador y el capturista teclean su trabajo.
            </p>
          </Card>
        )}
      </div>
    </div>
  )
}
