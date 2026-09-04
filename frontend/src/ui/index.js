/** Componentes compartidos por todos los modulos.
 *
 * Se importan desde aqui para que las pantallas no dependan de en que archivo
 * quedo cada pieza:  import { Card, Tabla } from '../../ui/index.js'
 */
export { Card } from './Card.jsx'
export { Kpi } from './Kpi.jsx'
export { Badge, EstadoBadge } from './Badge.jsx'
export { Aviso, Empty, Regla, Spinner } from './Feedback.jsx'
export { Modal } from './Modal.jsx'
export { Tabla } from './Tabla.jsx'
export { ToastProvider, useToast } from './Toast.jsx'
export { useApi } from './useApi.js'
export { BuscadorPieza } from './BuscadorPieza.jsx'
export { BuscadorUnidad } from './BuscadorUnidad.jsx'
