/**
 * API configuration - timeouts parametrizables desde variables de entorno.
 * Permite aumentar timeouts en entornos lentos o con muchos datos.
 *
 * Variables (opcionales):
 * - VITE_API_TIMEOUT_MS: timeout para GET (summary, analysis, workers, etc.)
 * - VITE_API_TIMEOUT_ACTION_MS: timeout para POST (retry, requeue, etc.)
 */

const parseNum = (val, defaultVal) => {
  const n = parseInt(val, 10);
  return Number.isFinite(n) && n > 0 ? n : defaultVal;
};

export const API_TIMEOUT_MS = parseNum(
  import.meta.env.VITE_API_TIMEOUT_MS,
  60000 // 60s default (antes 15-20s)
);

export const API_TIMEOUT_ACTION_MS = parseNum(
  import.meta.env.VITE_API_TIMEOUT_ACTION_MS,
  90000 // 90s para retry/requeue (operaciones pesadas)
);
