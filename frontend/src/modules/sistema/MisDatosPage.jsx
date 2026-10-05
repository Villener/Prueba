import { useEffect, useState } from 'react'
import { api, fmtCelular } from '../../core/api.js'
import {
  activarAvisos, alCambiarInstalable, desactivarAvisos, estadoAvisos, instalada, instalar,
  probarAvisos, sePuedeInstalar,
} from '../../core/pwa.js'
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

/** Lo que dice la tarjeta de avisos segun como este ESTE celular. */
const TEXTO_AVISOS = {
  activo: ['ok', 'Este celular recibe tus avisos.'],
  inactivo: ['info', 'Este celular todavía no recibe avisos.'],
  bloqueado: ['warn', 'Los avisos están bloqueados para esta página. Toca el candado junto a la '
    + 'dirección, entra a Permisos → Notificaciones → Permitir y vuelve a esta pantalla.'],
  'ios-instalar': ['info', 'En iPhone los avisos solo llegan con la app instalada: abre esta página '
    + 'en Safari, toca Compartir (el cuadro con la flecha hacia arriba) y luego «Agregar a inicio». '
    + 'Abre la app desde ese ícono y vuelve a Mis datos.'],
  'no-soportado': ['warn', 'Este navegador no puede recibir avisos. En Android usa Chrome; en '
    + 'iPhone, Safari con la app agregada a inicio.'],
}

function AvisosCelular() {
  const [estado, setEstado] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const [instalable, setInstalable] = useState(sePuedeInstalar)
  const toast = useToast()
  const revisar = () => estadoAvisos({ confirmar: true }).then(setEstado)

  useEffect(() => { revisar() }, [])
  useEffect(() => alCambiarInstalable(setInstalable), [])

  const hacer = (fn, exito) => async () => {
    setOcupado(true)
    try {
      const r = await fn()
      const texto = typeof exito === 'function' ? exito(r) : exito
      if (texto) toast(...[].concat(texto))
    } catch (e) {
      toast(e.message, 'err')
    } finally {
      setOcupado(false)
      revisar()
    }
  }
  const activar = hacer(activarAvisos, 'Listo: los avisos del taller te llegarán a este celular')
  const probar = hacer(probarAvisos, (r) => (r.enviados
    ? 'Aviso enviado: debe llegarte en unos segundos'
    : ['No se pudo entregar. Desactiva los avisos y vuelve a activarlos.', 'err']))
  const quitar = hacer(desactivarAvisos, 'Este celular ya no recibirá avisos')
  const instalarApp = hacer(instalar, (ok) => (ok ? 'La app quedó instalada' : null))

  const [tipo, texto] = TEXTO_AVISOS[estado] || ['info', 'Revisando este celular…']
  return (
    <Card title="Avisos en este celular">
      <Aviso tipo={tipo}>{texto}</Aviso>
      <div className="btn-row">
        {estado === 'inactivo' && (
          <button className="btn primary" onClick={activar} disabled={ocupado}>
            {ocupado ? 'Activando…' : 'Activar avisos'}
          </button>
        )}
        {estado === 'activo' && (
          <>
            <button className="btn primary" onClick={probar} disabled={ocupado}>Enviar aviso de prueba</button>
            <button className="btn" onClick={quitar} disabled={ocupado}>Dejar de recibir aquí</button>
          </>
        )}
        {instalable && !instalada() && (
          <button className="btn" onClick={instalarApp} disabled={ocupado}>Instalar la app en este celular</button>
        )}
      </div>
      <Regla>
        Son los mismos avisos de la campana —tus citas, sus cambios y lo que te asigne el taller—,
        pero te llegan aunque la app esté cerrada. Al salir de tu cuenta, este celular deja de recibirlos.
      </Regla>
    </Card>
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

      {!(usuario.roles || []).every((r) => r.startsWith('datos_')) && <AvisosCelular />}
    </>
  )
}
