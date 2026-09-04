export function Badge({ children, tono = '' }) {
  return <span className={`badge ${tono}`}>{children}</span>
}

/** Un tono por estado del modelo, para que el mismo estado se vea igual
 *  en todas las pantallas. */
const TONOS = {
  disponible: 'ok', lista: 'ok', aceptada: 'ok', aprobado: 'ok', activo: 'ok',
  finalizado: 'ok', terminada: 'ok', cerrada: '', recibida: 'ok', cumplido: 'ok',
  atendido: 'ok', surtida_de_almacen: 'ok',
  en_ruta: 'info', en_proceso: 'info', enviado_gerente: 'info', capturado: 'info',
  solicitado: 'info', aceptado: 'info', en_traslado: 'info', confirmada: 'info',
  pendiente: 'warn', en_cola: 'warn', en_espera: 'warn', esperando_peritos: 'warn',
  espera_presupuesto: 'warn', espera_refacciones: 'warn', en_transito: 'warn',
  devuelto: 'warn', en_disputa: 'warn', propuesta: 'warn', difundida: 'warn',
  varada: 'danger', en_arrastre: 'danger', rechazada: 'danger', rechazado: 'danger',
  vencido: 'danger', aplicada: 'danger', baja: 'danger', abierto: 'danger',
  no_asistio: 'danger',
}

export function EstadoBadge({ estado }) {
  return <Badge tono={TONOS[estado] ?? ''}>{String(estado || '—').replace(/_/g, ' ')}</Badge>
}
