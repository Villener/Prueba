import { useState } from 'react'
import { api, fmtCelular } from '../../core/api.js'
import { getToken, setSession, telefonoValido } from '../../core/sesion.js'
import { Aviso, Card, Regla, useToast } from '../../ui/index.js'

/** Mis datos: cada quien ve su cuenta y pone SU celular.
 *
 *  No es un registro: la cuenta ya existe (nace de la lista de personal) y aqui
 *  solo se completa el telefono. Sin el no hay forma de avisarle al chofer de
 *  su cita por WhatsApp, y 350 de 434 personas no lo traen en ningun Excel. */

const NOMBRE_ROL = {
  gerente: 'Gerente', administrador: 'Administrador', capturista: 'Capturista',
  supervisor: 'Supervisor', chofer_grua: 'Chofer de grúa', perito: 'Perito',
  mecanico: 'Mecánico', chofer: 'Chofer', datos_logistica: 'Carga de datos · Logística',
  datos_almacen: 'Carga de datos · Almacén', datos_compras: 'Carga de datos · Compras',
  datos_taller: 'Carga de datos · Taller',
}

const bonito = (t) => (telefonoValido(t) ? fmtCelular(t) : '')

function Dato({ etiqueta, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span className="sub" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
        {etiqueta}
      </span>
      <span>{children}</span>
    </div>
  )
}

export default function MisDatos({ usuario, onCambio }) {
  const [telefono, setTelefono] = useState(bonito(usuario.telefono))
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState(null)
  const toast = useToast()
  const tiene = telefonoValido(usuario.telefono)

  const guardar = async (e) => {
    e.preventDefault()
    const digitos = telefono.replace(/\D/g, '').replace(/^52(?=\d{10}$)/, '')
    if (digitos.length !== 10) {
      setError('Escribe tu celular de 10 dígitos, por ejemplo 664 123 4567.')
      return
    }
    setError(null)
    setGuardando(true)
    try {
      const yo = await api.put('/auth/me/telefono', { telefono: digitos })
      setSession(getToken(), yo)
      onCambio(yo)
      setTelefono(bonito(yo.telefono))
      toast('Tu celular quedó guardado')
    } catch (err) {
      setError(err.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <>
      <h1 style={{ marginBottom: 14 }}>Mis datos</h1>
      <Card title="Tu cuenta">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
          <Dato etiqueta="Nombre">{usuario.nombre} {usuario.apellidos}</Dato>
          <Dato etiqueta="Usuario para entrar">{usuario.email}</Dato>
          <Dato etiqueta="Puesto en el sistema">
            {(usuario.roles || []).map((r) => NOMBRE_ROL[r] || r).join(', ')}
          </Dato>
        </div>
        <Regla>
          El usuario para entrar no es un correo real: lo arma el sistema con tu número de
          empleado. Si algo de esto está mal, avísale al administrador del taller.
        </Regla>
      </Card>

      <Card title="Tu celular">
        {!tiene && (
          <Aviso tipo="warn">
            Todavía no tenemos tu celular. Sin él, el taller no puede avisarte de tus citas.
          </Aviso>
        )}
        <form onSubmit={guardar} style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 360 }}>
          <label htmlFor="mi-celular" className="sub">Celular (10 dígitos)</label>
          <input id="mi-celular" type="tel" inputMode="numeric" autoComplete="tel-national"
                 placeholder="664 123 4567" value={telefono}
                 onChange={(e) => { setTelefono(e.target.value); setError(null) }} />
          {error && <span style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</span>}
          <button className="btn primary" disabled={guardando}>
            {guardando ? 'Guardando…' : tiene ? 'Cambiar celular' : 'Guardar celular'}
          </button>
        </form>
        <Regla>
          Se usa solo para avisos del taller: tus citas de mantenimiento y sus cambios, por
          WhatsApp. Queda registrado quién lo cambió y cuándo.
        </Regla>
      </Card>
    </>
  )
}
