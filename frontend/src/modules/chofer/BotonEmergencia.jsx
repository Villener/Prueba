/** CU-CHO-10 — el botón de emergencia, con confirmación de dos toques.
 *
 * TRES DECISIONES QUE PARECEN DETALLES Y NO LO SON:
 *
 * 1. EL GPS SE EMPIEZA A PEDIR EN EL PRIMER TOQUE, mientras el chofer lee la
 *    confirmación. Fijar posición tarda entre 3 y 8 segundos a la intemperie;
 *    si se pidiera hasta el segundo toque, el chofer se quedaría mirando una
 *    ruedita parado en la carretera.
 *
 * 2. A LOS 10 SEGUNDOS SE MANDA IGUAL, sin ubicación y marcado como tal. Una
 *    alerta sin punto sirve muchísimo más que una alerta que nunca salió. Si el
 *    fix llega después, se completa solo con POST /averias/:id/ubicacion.
 *
 * 3. NUNCA SE INVENTA UNA UBICACIÓN. La versión anterior, cuando el navegador
 *    negaba el GPS, mandaba en silencio las coordenadas del taller de Álamos.
 *    Así quedó AVE-2026-00005: dice estar en el taller y en realidad nadie sabe
 *    dónde estaba. Es peor que no tener el dato, porque nadie sospecha.
 *
 * Y el aviso de HTTPS: el GPS del navegador solo funciona en origen seguro. En
 * http://192.168.x.x:8081 el navegador lo niega sin explicar por qué, y esa es
 * la causa más probable de una alerta sin ubicación durante las pruebas.
 */
import { useEffect, useRef, useState } from 'react'
import { api } from '../../core/api.js'
import { Aviso, IcoAverias, IcoListo, IcoUbicacion, Modal, Regla, useToast } from '../../ui/index.js'

/** Tope de espera antes de mandar sin punto. */
const ESPERA_MS = 10000

/** Un fix a más de 500 m de precisión no dice dónde está la unidad: dice en qué
 *  colonia anda. Se guarda igual, pero se avisa que es aproximado. */
const PRECISION_DUDOSA = 500

export function BotonEmergencia({ unidad, onListo }) {
  const [confirmando, setConfirmando] = useState(false)
  const [choque, setChoque] = useState(false)
  const seguro = window.isSecureContext

  return (
    <>
      {/* RN-16: dos botones, no uno con opciones. Chocar y quedarse tirado son
          procedimientos distintos —cambia quién tiene que llegar, qué se
          levanta, cuándo se puede mover la unidad y a dónde va después— y
          meterlos en el mismo formulario obligaba al chofer a describir un
          impacto en un campo de «falla». */}
      <button className="boton-panico" disabled={!unidad}
              onClick={() => setConfirmando(true)}>
        <IcoAverias size={30} strokeWidth={2.2} aria-hidden="true" />
        <span>Me quedé tirado</span>
        <small>{unidad ? `La unidad falló · ${unidad.num_economico}` : 'Sin unidad asignada'}</small>
      </button>

      <button className="boton-panico choque" disabled={!unidad}
              onClick={() => setChoque(true)}>
        <IcoAverias size={30} strokeWidth={2.2} aria-hidden="true" />
        <span>Choqué</span>
        <small>{unidad ? 'Hubo un impacto' : 'Sin unidad asignada'}</small>
      </button>

      {!seguro && (
        <Aviso tipo="warn">
          Estás entrando por una dirección sin candado (<code>http://</code>), y por eso el
          navegador no va a dar tu ubicación. La alerta se manda igual, pero llega sin el punto
          en el mapa. Entra por la dirección con <strong>https</strong> para que el GPS funcione.
        </Aviso>
      )}

      {confirmando && (
        <ModalConfirmar unidad={unidad} onCerrar={() => setConfirmando(false)}
                        onListo={(averia) => { setConfirmando(false); onListo(averia) }} />
      )}

      {choque && (
        <ModalChoque unidad={unidad} onCerrar={() => setChoque(false)}
                     onListo={(r) => { setChoque(false); onListo(r) }} />
      )}
    </>
  )
}

/* ------------------------------------------------------------ el segundo toque */

function ModalConfirmar({ unidad, onCerrar, onListo }) {
  const toast = useToast()
  const [gps, setGps] = useState(null)        // {lat, lng, precision}
  const [estadoGps, setEstadoGps] = useState('buscando')  // buscando|listo|negado|sin-soporte
  const [descripcion, setDescripcion] = useState('')
  const [vialidad, setVialidad] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const vigilante = useRef(null)

  // Arranca en cuanto se abre el diálogo: es el punto 1 de la cabecera.
  useEffect(() => {
    if (!navigator.geolocation) { setEstadoGps('sin-soporte'); return }
    // watchPosition y no getCurrentPosition: el primer fix suele venir de la
    // red (200-2000 m) y el del GPS llega unos segundos después. Quedarse con
    // el primero desperdicia la buena.
    vigilante.current = navigator.geolocation.watchPosition(
      (p) => {
        setGps({ lat: p.coords.latitude, lng: p.coords.longitude,
                 precision: Math.round(p.coords.accuracy) })
        setEstadoGps('listo')
      },
      () => setEstadoGps('negado'),
      { enableHighAccuracy: true, timeout: ESPERA_MS, maximumAge: 0 })

    return () => {
      if (vigilante.current != null) navigator.geolocation.clearWatch(vigilante.current)
    }
  }, [])

  const mandar = async () => {
    setEnviando(true)
    try {
      const averia = await api.post('/chofer/averias', {
        unidad_id: unidad.id,
        latitud: gps ? gps.lat : null,
        longitud: gps ? gps.lng : null,
        descripcion_falla: descripcion.trim() || 'Emergencia reportada desde el botón',
        en_vialidad_publica: vialidad,
        requiere_arrastre: false,
      })
      toast(gps ? 'Alerta enviada con tu ubicación' : 'Alerta enviada · sin ubicación todavía')

      // Si salió sin punto, se sigue esperando en segundo plano. El chofer ya
      // no está mirando la pantalla: la alerta ya salió y esto se completa solo.
      if (!gps && navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (p) => api.post(`/chofer/averias/${averia.id}/ubicacion`,
                          { latitud: p.coords.latitude, longitud: p.coords.longitude })
                    .catch(() => {}),
          () => {}, { enableHighAccuracy: true, timeout: 25000 })
      }
      onListo(averia)
    } catch (e) {
      toast(e.message, 'err')
      setEnviando(false)
    }
  }

  const dudosa = gps && gps.precision > PRECISION_DUDOSA

  return (
    <Modal titulo="¿Seguro que quieres pedir auxilio?" onClose={onCerrar}>
      {/* El número económico grande y completo: es lo que ve quien apretó el
          botón por error, y lo único que lo detiene a tiempo. */}
      <p className="panico-unidad">{unidad.num_economico}</p>
      <p className="sub" style={{ textAlign: 'center', marginTop: -6 }}>
        {[unidad.marca, unidad.modelo].filter(Boolean).join(' · ') || 'Tu unidad'}
      </p>

      <div className="panico-gps">
        {estadoGps === 'buscando' && (
          <><IcoUbicacion size={15} className="ico-inline" aria-hidden="true" />
            Buscando tu ubicación…</>
        )}
        {estadoGps === 'listo' && (
          <><IcoListo size={15} className="ico-inline" aria-hidden="true" />
            Ubicación lista · {gps.lat.toFixed(5)}, {gps.lng.toFixed(5)}
            {dudosa ? ` (aproximada, ±${gps.precision} m)` : ''}</>
        )}
        {(estadoGps === 'negado' || estadoGps === 'sin-soporte') && (
          <><IcoUbicacion size={15} className="ico-inline" aria-hidden="true" />
            Sin ubicación · la alerta sale igual</>
        )}
      </div>

      <div className="field">
        <label>¿Qué pasó? · opcional</label>
        <textarea rows={2} value={descripcion} maxLength={400}
                  placeholder="No arranca, se calentó, se ponchó una llanta…"
                  onChange={(e) => setDescripcion(e.target.value)} />
      </div>

      <label className="radio-fila">
        <input type="checkbox" checked={vialidad}
               onChange={(e) => setVialidad(e.target.checked)} />
        <span>
          <strong>Estoy en vialidad pública</strong>
          <small className="sub">
            Carretera, bulevar o calle. Si lo marcas hay que avisar a peritos antes de que
            entre la grúa.
          </small>
        </span>
      </label>

      {(estadoGps === 'negado' || estadoGps === 'sin-soporte') && (
        <Aviso tipo="warn">
          Tu teléfono no está dando la ubicación. La alerta se manda de todos modos y tu
          supervisor recibe el aviso de que llegó sin punto, para hablarte.
        </Aviso>
      )}

      <div className="btn-row panico-acciones">
        <button className="btn" onClick={onCerrar} disabled={enviando}>
          No, fue por error
        </button>
        <button className="btn danger" onClick={mandar} disabled={enviando}>
          {enviando ? 'Enviando…'
            : estadoGps === 'buscando' ? 'Sí, mandar ahora' : 'Sí, mandar la alerta'}
        </button>
      </div>

      <Regla>
        {estadoGps === 'buscando'
          ? 'Puedes mandarla ya sin esperar: si el GPS llega después, el punto se agrega solo.'
          : 'La alerta le llega al administrador de taller y a tu supervisor al mismo tiempo.'}
      </Regla>
    </Modal>
  )
}


/* --------------------------------------------------------------- CU-CHO-18 -- */
/** RN-16: el formulario del choque. No reusa el de avería a propósito.
 *
 *  Un choque no tiene «descripción de falla»: tiene daños, terceros y
 *  lesionados. Y la unidad queda bloqueada hasta que haya peritaje, haya sido
 *  donde haya sido — en una avería eso solo pasa en vialidad pública.
 */
function ModalChoque({ unidad, onCerrar, onListo }) {
  const [danos, setDanos] = useState('')
  const [terceros, setTerceros] = useState(0)
  const [datosTerceros, setDatosTerceros] = useState('')
  const [lesionados, setLesionados] = useState(false)
  const [circula, setCircula] = useState(false)
  const [viaPublica, setViaPublica] = useState(true)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)

  async function mandar() {
    if (!danos.trim()) { setError('Describe los daños: es la base del parte de accidente.'); return }
    setEnviando(true); setError(null)
    try {
      const cuerpo = {
        unidad_id: unidad.id,
        descripcion_danos: danos,
        hay_lesionados: lesionados,
        cuantos_terceros: Number(terceros) || 0,
        datos_terceros: datosTerceros || null,
        unidad_puede_circular: circula,
        en_vialidad_publica: viaPublica,
      }
      if (navigator.geolocation && window.isSecureContext) {
        await new Promise((res) => {
          navigator.geolocation.getCurrentPosition(
            (p) => { cuerpo.latitud = p.coords.latitude; cuerpo.longitud = p.coords.longitude; res() },
            () => res(), { timeout: 8000 })
        })
      }
      const r = await api.post('/chofer/choques', cuerpo)
      onListo(r)
    } catch (e) { setError(String(e.message || e)); setEnviando(false) }
  }

  return (
    <Modal titulo="Reportar un choque" onClose={onCerrar}>
      {error && <Aviso tipo="err">{error}</Aviso>}
      <Aviso tipo="warn">
        La unidad <strong>no se mueve</strong> hasta que llegue el perito y quede el peritaje.
        No importa dónde haya sido. Moverla antes es lo que deja a la empresa sin cómo defenderse.
      </Aviso>

      <label className="campo">
        <span>¿Qué se dañó?</span>
        <textarea rows={3} value={danos} onChange={(e) => setDanos(e.target.value)}
                  placeholder="Salpicadera derecha, faro, defensa…" />
      </label>

      <label className="campo">
        <span>¿Cuántos terceros involucrados?</span>
        <input type="number" min={0} value={terceros}
               onChange={(e) => setTerceros(e.target.value)} />
      </label>

      {Number(terceros) > 0 && (
        <label className="campo">
          <span>Datos de los terceros</span>
          <textarea rows={2} value={datosTerceros}
                    onChange={(e) => setDatosTerceros(e.target.value)}
                    placeholder="Nombre, placas, aseguradora" />
        </label>
      )}

      <label className="radio-fila">
        <input type="checkbox" checked={lesionados}
               onChange={(e) => setLesionados(e.target.checked)} />
        <span>Hay lesionados</span>
      </label>

      <label className="radio-fila">
        <input type="checkbox" checked={viaPublica}
               onChange={(e) => setViaPublica(e.target.checked)} />
        <span>Fue en vialidad pública</span>
      </label>

      <label className="radio-fila">
        <input type="checkbox" checked={circula}
               onChange={(e) => setCircula(e.target.checked)} />
        <span>La unidad puede circular por su cuenta</span>
      </label>

      <Regla>
        Se avisa al <strong>perito</strong>, a tu supervisor y al gerente al mismo tiempo. Que la
        unidad pueda circular no la desbloquea: solo dice si al final hará falta grúa.
      </Regla>

      <div className="acciones">
        <button className="btn" onClick={onCerrar} disabled={enviando}>Cancelar</button>
        <button className="btn danger" onClick={mandar} disabled={enviando}>
          {enviando ? 'Enviando…' : 'Reportar choque'}
        </button>
      </div>
    </Modal>
  )
}
