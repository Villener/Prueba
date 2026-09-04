/** Cómo se cuenta lo que el usuario tecleó en los buscadores de refacción.
 *
 * Vive en core/ y no junto a una de las pantallas: lo usan AlmacenPage y
 * BuscadorPieza, y BuscadorPieza se re-exporta desde ui/index.js, que a su vez
 * lo importa AlmacenPage. Colgarlo de cualquiera de las dos cierra un ciclo de
 * imports y el helper llega sin inicializar a quien lo pida primero.
 */

// Letras de verdad que lleva el término: los * son comodines, no texto.
// El servidor cuenta igual, así que las dos puntas exigen lo mismo y no se
// dispara una petición que sólo puede volver con "faltan letras".
export const letras = (q) => q.replace(/\*/g, '').trim().length
