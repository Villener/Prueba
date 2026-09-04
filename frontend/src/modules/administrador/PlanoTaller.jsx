/** Piezas compartidas del plano.

PlanoTaller se usa en dos lugares: la pantalla del plano y el modal de la
solicitud, donde el administrador elige la casilla antes de aceptar. */
import { useEffect } from 'react'
import { api } from '../../core/api.js'
import { Badge, Spinner, useApi } from '../../ui/index.js'

/** Selector de taller. Ya son 6 plantas, no una sola. */
export function SelectorTaller({ valor, onCambio }) {
  const { data } = useApi(() => api.get('/admin/talleres'))
  const talleres = data || []
  useEffect(() => {
    if (!valor && talleres.length) onCambio(talleres[0].id)
  }, [talleres, valor, onCambio])
  if (talleres.length <= 1) return null
  return (
    <div className="field" style={{ maxWidth: 260, marginBottom: 0 }}>
      <label>Taller</label>
      <select value={valor || ''} onChange={(e) => onCambio(Number(e.target.value))}>
        {talleres.map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>)}
      </select>
    </div>
  )
}

/* ---------------------------------------------------------- el croquis ---- */
/**
 * EL ORDEN VISUAL DEL CROQUIS DE ÁLAMOS.
 *
 * Esto reproduce el dibujo que entregó el cliente, y el dibujo es de UN edificio
 * concreto: dos filas de cajones enfrentadas con el pasillo de circulación en
 * medio, la salida a la izquierda, la entrada a la derecha, y a un lado el
 * patio, el área de lavado y el yonke.
 *
 * Va por nombre de zona y no por un campo de la base porque lo que se está
 * codificando es *la forma del edificio*, no un dato del taller: la llantera
 * está a la izquierda de la fila de arriba porque así está construida, y eso no
 * cambia aunque cambien las unidades. Una zona que no esté en estas listas
 * igual se dibuja —al final, en su propia banda— así que agregar una zona nueva
 * nunca la desaparece de la pantalla.
 */
const CROQUIS = {
  arriba: ['LLANTERA', 'REPARTO NORTE', 'PIPAS'],
  abajo: ['ELECTRICOS', 'UTILITARIOS', 'OFICINA', 'REPARTO SUR', 'FOSA'],
  // El renglón de arriba del anexo: contenedor, los diez primeros del patio y
  // el área de lavado.
  apoyo: ['CONTENEDOR BASURA', 'PATIO', 'AREA LAVADO'],
  // El yonke NO tiene cajones: ahí hay piezas y partes, no vehículos. Se dibuja
  // porque está en el croquis y sirve para orientarse.
  almacen: ['YONKE'],
}

/* El patio son 55 lugares en dos bloques: diez arriba, junto al contenedor y el
   lavado, y cuarenta y cinco abajo en tres renglones de quince. Es UNA zona
   -- una unidad en el P-40 está en el patio igual que una en el P-03 -- así que
   se parte solo para dibujarla, no en los datos. */
const PATIO_ARRIBA = 10
const PATIO_RENGLONES = 3

/* Los colores de las bandas son los del Excel del cliente: azul reparto, gris
   pipas, ámbar eléctricos, morado utilitarios. Quien conoce el papel reconoce
   la pantalla sin que nadie se lo explique. */
const TONO_ZONA = {
  'REPARTO NORTE': 'reparto', 'REPARTO SUR': 'reparto',
  PIPAS: 'pipas', ELECTRICOS: 'electricos', UTILITARIOS: 'utilitarios',
  LLANTERA: 'especial', FOSA: 'especial',
}

/** «T-01» → «1». El croquis del cliente numera 1..18 y 1..12; el prefijo dice
 *  de qué fila es y sirve para hablar por radio, pero en el dibujo estorba. */
const corto = (numero) => (numero || '').replace(/^[A-Z]-0*/, '') || numero

function Casilla({ e, zona, onEspacio, seleccionado, soloLibres }) {
  const bloqueado = soloLibres && e.estado !== 'libre'
  return (
    <button type="button" disabled={bloqueado}
            className={`espacio ${e.estado}`
              + (zona.cuenta_para_ocupacion ? '' : ' no-cuenta')
              + (seleccionado === e.id ? ' elegido' : '')}
            title={`${zona.nombre} ${e.numero}` + (e.unidad
              ? ` · ${e.unidad} · ${e.dias_ocupado} días`
              : ` · libre · admite ${e.tipo_permitido || 'cualquier tipo'}`)}
            onClick={() => onEspacio && onEspacio(e)}>
      <span>{corto(e.numero)}</span>
      {e.unidad && <small>{e.unidad}</small>}
    </button>
  )
}

function BandaZona({ zona, onEspacio, seleccionado, soloLibres,
                    desde = 0, hasta, filas = 1, titulo }) {
  // Una zona sin cajones (oficina, contenedor, yonke) existe en el croquis para
  // orientarse: no se toca, pero quitarla desdibuja el edificio.
  if (!zona.espacios.length) {
    return (
      <div className="cro-zona cro-hito" data-tono="hito">
        <span>{zona.nombre}</span>
        {zona.proposito === 'almacenaje' && <small>piezas y partes</small>}
      </div>
    )
  }
  // `desde`/`hasta` recortan la zona para dibujarla en dos bloques sin
  // partirla en los datos: es el caso del patio.
  const trozo = zona.espacios.slice(desde, hasta)
  const ocupados = trozo.filter((e) => e.estado === 'ocupado').length
  const porRenglon = Math.ceil(trozo.length / filas)
  const renglones = Array.from({ length: filas }, (_, i) =>
    trozo.slice(i * porRenglon, (i + 1) * porRenglon))

  return (
    <div className="cro-zona" data-tono={TONO_ZONA[zona.nombre] || 'neutra'}>
      <div className="cro-banda">
        <span>{titulo || zona.nombre}</span>
        <span className="cro-cuenta">{ocupados}/{trozo.length}</span>
      </div>
      {renglones.map((r, i) => (
        <div className="cro-casillas" key={i}>
          {r.map((e) => (
            <Casilla key={e.id} e={e} zona={zona} onEspacio={onEspacio}
                     seleccionado={seleccionado} soloLibres={soloLibres} />
          ))}
        </div>
      ))}
    </div>
  )
}

/**
 * El croquis de Álamos, como el plano que entregó el cliente.
 *
 * Antes el plano era una lista vertical de zonas: correcta pero imposible de
 * cruzar con el papel que tienen pegado en la pared. Quien está parado en el
 * taller busca «la de hasta la orilla junto a la entrada», no «la tercera de
 * REPARTO SUR».
 */
function Croquis({ taller, onEspacio, seleccionado, soloLibres }) {
  const porNombre = Object.fromEntries(taller.zonas.map((z) => [z.nombre, z]))
  const usadas = new Set()
  const tomar = (nombres) => nombres
    .map((n) => { if (porNombre[n]) usadas.add(n); return porNombre[n] })
    .filter(Boolean)

  const arriba = tomar(CROQUIS.arriba)
  const abajo = tomar(CROQUIS.abajo)
  const apoyo = tomar(CROQUIS.apoyo)
  const almacen = tomar(CROQUIS.almacen)
  // Lo que el croquis no conoce se dibuja igual, al final. Una zona nueva no
  // puede desaparecer de la pantalla solo por no estar en la lista de arriba.
  const otras = taller.zonas.filter((z) => !usadas.has(z.nombre))

  const props = { onEspacio, seleccionado, soloLibres }

  return (
    <div className="croquis">
      {/* La nave: dos filas enfrentadas y el pasillo en medio. */}
      <div className="cro-nave">
        <div className="cro-puerta salida"><span>SALIDA</span></div>
        <div className="cro-centro">
          <div className="cro-fila">
            {arriba.map((z) => <BandaZona key={z.id} zona={z} {...props} />)}
          </div>
          {/* El sentido de circulación. Está en el papel y no es adorno: dice
              por qué la salida está de un lado y la entrada del otro. */}
          <div className="cro-pasillo" aria-label="Sentido de circulación: hacia la salida">
            <span className="cro-flecha" aria-hidden="true">←</span>
            <span>circulación</span>
            <span className="cro-flecha" aria-hidden="true">←</span>
          </div>
          <div className="cro-fila">
            {abajo.map((z) => <BandaZona key={z.id} zona={z} {...props} />)}
          </div>
        </div>
        <div className="cro-puerta entrada"><span>ENTRADA</span></div>
      </div>

      {/* Afuera de la nave: lo que admite unidades pero no es capacidad. */}
      {(apoyo.length > 0 || almacen.length > 0) && (
        <div className="cro-anexo">
          <div className="cro-fila">
            {apoyo.map((z) => (
              z.nombre === 'PATIO'
                ? <BandaZona key={z.id} zona={z} hasta={PATIO_ARRIBA} {...props} />
                : <BandaZona key={z.id} zona={z} {...props} />
            ))}
          </div>
          {/* Los otros cuarenta y cinco del patio, abajo, como en el croquis. */}
          {apoyo.filter((z) => z.nombre === 'PATIO' && z.espacios.length > PATIO_ARRIBA)
            .map((z) => (
              <BandaZona key={`${z.id}-abajo`} zona={z} desde={PATIO_ARRIBA}
                         filas={PATIO_RENGLONES} titulo="PATIO (continúa)" {...props} />
            ))}
          <div className="cro-fila">
            {almacen.map((z) => <BandaZona key={z.id} zona={z} {...props} />)}
          </div>
        </div>
      )}

      {otras.length > 0 && (
        <div className="cro-anexo">
          <div className="cro-fila">
            {otras.map((z) => <BandaZona key={z.id} zona={z} {...props} />)}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Dibuja el plano. Se usa en dos lugares: la pantalla del plano y el modal de
 * la solicitud, donde el administrador elige la casilla antes de aceptar.
 *
 * Álamos sale como croquis; las satélites, que son una sola zona de dos o tres
 * cajones, salen como lista. Dibujarle una nave con pasillo y flechas a un
 * taller de dos lugares sería inventarle una planta que no tiene.
 */
export function PlanoTaller({ taller, onEspacio, seleccionado, soloLibres = false }) {
  if (!taller) return <Spinner />
  const conCajones = taller.zonas.filter((z) => z.espacios.length > 0)
  if (conCajones.length > 1) {
    return <Croquis taller={taller} onEspacio={onEspacio}
                    seleccionado={seleccionado} soloLibres={soloLibres} />
  }
  return (
    <>
      {taller.zonas.map((z) => (
        <div className="zona" key={z.id}>
          <div className="zona-head">
            <span>{z.nombre}</span>
            {!z.cuenta_para_ocupacion && <Badge>no cuenta</Badge>}
            <span style={{ color: 'var(--muted)', fontWeight: 500 }}>
              {z.espacios.filter((e) => e.estado === 'ocupado').length}/{z.espacios.length}
            </span>
          </div>
          <div className="espacios">
            {z.espacios.map((e) => (
              <Casilla key={e.id} e={e} zona={z} onEspacio={onEspacio}
                       seleccionado={seleccionado} soloLibres={soloLibres} />
            ))}
            {z.espacios.length === 0 && <span className="sub">Zona sin espacios</span>}
          </div>
        </div>
      ))}
    </>
  )
}
