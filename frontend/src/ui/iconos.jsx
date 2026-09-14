/** Iconos de la interfaz.
 *
 * UN SOLO archivo decide que dibujo representa cada concepto. Antes eran emojis
 * literales repartidos por veinte archivos y el mismo concepto salia con dos
 * dibujos distintos segun quien escribiera la pantalla: el taller era 🔧 en el
 * menu y tambien en Ordenes, pero las averias eran ⚠️ en un lado y 🚨 en otro.
 *
 * Y el emoji lo dibuja el SISTEMA OPERATIVO, no la aplicacion: el mismo 🅿️ se ve
 * azul en Windows, gris en Android y con otro trazo en iPhone. En una pantalla
 * que presume de sala de control industrial eso desentona, y encima no hay forma
 * de alinearlo con el texto ni de que siga el tema oscuro.
 *
 * Estos son SVG de trazo que heredan `currentColor`: siguen el color del texto
 * que los rodea, asi que el tema claro y el oscuro funcionan sin una sola regla
 * de CSS extra.
 *
 * Los nombres son del DOMINIO, no del dibujo. Quien cambie manana el icono de
 * "averias" toca este archivo y nada mas; si las pantallas importaran
 * `TriangleAlert` directamente, habria que perseguirlo por todo el proyecto.
 */
import {
  ArrowLeft,
  ArrowLeftRight,
  Banknote,
  BarChart3,
  Bell,
  CalendarDays,
  Circle,
  CircleAlert,
  CircleCheck,
  ClipboardCheck,
  ClipboardList,
  Download,
  FileText,
  History,
  Inbox,
  LayoutDashboard,
  MapPin,
  Moon,
  Package,
  PencilLine,
  Printer,
  Search,
  Siren,
  SquareParking,
  Sun,
  TriangleAlert,
  Truck,
  Users,
  Wrench,
  X,
} from 'lucide-react'

/* --------------------------------------------------- menu de cada modulo --- */
export const IcoUnidad = Truck               // la unidad del chofer
export const IcoPrestamos = ArrowLeftRight   // la responsabilidad cambia de manos
export const IcoTaller = Wrench
export const IcoAverias = TriangleAlert
export const IcoCuadrilla = Users
export const IcoCumplimiento = ClipboardCheck
export const IcoSolicitudes = Inbox
export const IcoAgenda = CalendarDays
export const IcoPlano = SquareParking        // el croquis son cajones
export const IcoAlmacen = Package
export const IcoOrdenes = ClipboardList
export const IcoPresupuestos = Banknote
export const IcoReportes = FileText
export const IcoHoja = Printer               // se imprime y se entrega en papel
export const IcoCapturar = PencilLine
export const IcoPendientes = Search
export const IcoAlertas = Siren
export const IcoArrastres = Truck
export const IcoHistorial = History
export const IcoTablero = LayoutDashboard
export const IcoIncumplimiento = CircleAlert
export const IcoIndicadores = BarChart3

/* ------------------------------------------------------------ transversal --- */
export const IcoCampana = Bell
export const IcoTemaOscuro = Moon
export const IcoTemaClaro = Sun
export const IcoCerrar = X
export const IcoVolver = ArrowLeft
export const IcoUbicacion = MapPin
export const IcoListo = CircleCheck
export const IcoPendiente = Circle      // lo que todavia no ocurre
export const IcoTecnico = Wrench
export const IcoNota = PencilLine
export const IcoVacio = Inbox                // el estado "aqui no hay nada"
export const IcoBuscar = Search
export const IcoImprimir = Printer
export const IcoDescargar = Download
