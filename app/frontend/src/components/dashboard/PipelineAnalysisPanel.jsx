/**
 * PipelineAnalysisPanel — etapas del pipeline + (admin) despacho ON/OFF y LLM insights.
 * Checkbox "Procesar": marcado = paso activo en BD; desmarcado = pausado.
 */

import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { API_TIMEOUT_MS } from '../../config/apiConfig';
import './PipelineAnalysisPanel.css';

const stageColors = {
  upload: '#f59e0b',
  ocr: '#3b82f6',
  chunking: '#8b5cf6',
  indexing: '#ec4899',
  insights: '#10b981',
  'indexing insights': '#06b6d4',
};

/** Nombre de etapa (API analysis) → id en pipeline_runtime_kv */
const STAGE_PAUSE_KEY = {
  OCR: 'ocr',
  Chunking: 'chunking',
  Indexing: 'indexing',
  Insights: 'insights',
  'Indexing Insights': 'indexing_insights',
};

const PROVIDER_OPTIONS = [
  { id: 'openai', label: 'OpenAI' },
  { id: 'perplexity', label: 'Perplexity' },
  { id: 'ollama', label: 'Local' },
];

function orderFromSlots(slots) {
  const seen = new Set();
  const out = [];
  for (const s of slots) {
    if (s && !seen.has(s)) {
      seen.add(s);
      out.push(s);
    }
  }
  return out;
}

function slotsFromOrder(order) {
  const base = Array.isArray(order) ? [...order] : [];
  while (base.length < 3) base.push('');
  return base.slice(0, 3);
}

export function PipelineAnalysisPanel({ API_URL, token, refreshTrigger, isAdmin = false }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [pauseSteps, setPauseSteps] = useState([]);
  const [providerMode, setProviderMode] = useState('auto');
  const [providerSlots, setProviderSlots] = useState(['openai', 'perplexity', 'ollama']);
  const [availableProviders, setAvailableProviders] = useState([]);
  const [envLlm, setEnvLlm] = useState('');
  const [envLlmModel, setEnvLlmModel] = useState('');
  const [ollamaModel, setOllamaModel] = useState('');
  const [ollamaModels, setOllamaModels] = useState([]);
  const [saving, setSaving] = useState(false);
  const [runtimeErr, setRuntimeErr] = useState(null);

  const applyRuntimePayload = useCallback((data) => {
    if (!data) return;
    if (Array.isArray(data.pause_steps)) setPauseSteps(data.pause_steps);
    if (data.provider_mode) setProviderMode(data.provider_mode === 'manual' ? 'manual' : 'auto');
    if (Array.isArray(data.provider_order)) setProviderSlots(slotsFromOrder(data.provider_order));
    if (Array.isArray(data.available_providers)) setAvailableProviders(data.available_providers);
    if (data.env_llm_provider !== undefined) setEnvLlm(data.env_llm_provider || '');
    if (data.env_llm_model !== undefined) setEnvLlmModel(data.env_llm_model || '');
    if (Object.prototype.hasOwnProperty.call(data, 'ollama_model')) {
      setOllamaModel(data.ollama_model ? String(data.ollama_model) : '');
    }
    if (Array.isArray(data.ollama_models)) setOllamaModels(data.ollama_models);
  }, []);

  const isPaused = useCallback(
    (stepId) => !!pauseSteps.find((p) => p.id === stepId)?.paused,
    [pauseSteps]
  );

  const persistRuntime = async (patch) => {
    if (!isAdmin || !token) return;
    setSaving(true);
    setRuntimeErr(null);
    try {
      const { data } = await axios.put(`${API_URL}/api/admin/insights-pipeline`, patch, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: API_TIMEOUT_MS,
      });
      applyRuntimePayload(data);
    } catch (e) {
      setRuntimeErr(e.response?.data?.detail || e.message || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    const fetchAll = async () => {
      if (!token) return;
      try {
        setLoading(true);
        const analysisReq = axios.get(`${API_URL}/api/dashboard/analysis`, {
          headers: { Authorization: `Bearer ${token}` },
          timeout: API_TIMEOUT_MS,
        });
        if (isAdmin) {
          const [aRes, pRes] = await Promise.all([
            analysisReq,
            axios.get(`${API_URL}/api/admin/insights-pipeline`, {
              headers: { Authorization: `Bearer ${token}` },
              timeout: API_TIMEOUT_MS,
            }),
          ]);
          setAnalysis(aRes.data);
          applyRuntimePayload(pRes.data);
        } else {
          const aRes = await analysisReq;
          setAnalysis(aRes.data);
        }
        setError(null);
        setRuntimeErr(null);
      } catch (err) {
        console.error('Error fetching pipeline analysis:', err);
        setError(err.message || 'Error de conexión');
      } finally {
        setLoading(false);
      }
    };

    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [API_URL, token, refreshTrigger, isAdmin, applyRuntimePayload]);

  if (loading && !analysis) {
    return (
      <div className="pipeline-analysis-panel">
        <div className="panel-loading">Cargando análisis de pipeline...</div>
      </div>
    );
  }

  if (!analysis && error) {
    return (
      <div className="pipeline-analysis-panel">
        <div className="panel-error">⚠️ Error: {error}</div>
      </div>
    );
  }

  if (!analysis || !analysis.pipeline) {
    return null;
  }

  const { stages, total_blockers } = analysis.pipeline;

  return (
    <div className="pipeline-analysis-panel">
      <div className="panel-header">
        <h3>🔄 Análisis de Pipeline</h3>
        {total_blockers > 0 && (
          <span className="blockers-badge">
            ⚠️ {total_blockers} Bloqueo{total_blockers > 1 ? 's' : ''} Detectado{total_blockers > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {isAdmin && (
        <div className="pipeline-admin-toolbar">
          <p className="pipeline-admin-hint">
            <strong>Despacho:</strong> marca &quot;Procesar&quot; en cada tarjeta para que ese paso reciba workers.
            Desmarcado = <strong>pausado</strong> (persistente en BD). Upload no tiene interruptor aquí.
          </p>
          <div className="pipeline-admin-actions">
            <button
              type="button"
              className="btn-runtime btn-runtime-on"
              disabled={saving}
              onClick={() => persistRuntime({ resume_all: true })}
            >
              Todo activo
            </button>
            <button
              type="button"
              className="btn-runtime btn-runtime-off"
              disabled={saving}
              onClick={() => persistRuntime({ pause_all: true })}
            >
              Pausar todo
            </button>
            {saving && <span className="runtime-saving">Guardando…</span>}
          </div>
          {runtimeErr && <div className="runtime-err">{runtimeErr}</div>}
        </div>
      )}

      <div className="pipeline-stages">
        {stages.map((stage) => {
          const isBlocked = stage.blockers && stage.blockers.length > 0;
          const hasReady = stage.ready_for_next > 0;
          const errorTasks = stage.error_tasks ?? 0;
          const totalTasks = stage.pending_tasks + stage.processing_tasks + stage.completed_tasks + errorTasks;
          const completionPercent =
            totalTasks > 0 ? Math.round((stage.completed_tasks / totalTasks) * 100) : 0;
          const pauseKey = STAGE_PAUSE_KEY[stage.name];
          const colorKey = stage.name.toLowerCase();

          return (
            <div key={stage.name} className={`stage-card ${isBlocked ? 'blocked' : ''}`}>
              <div className="stage-header">
                <div className="stage-title">
                  <div className="stage-title-row">
                    <span
                      className="stage-icon"
                      style={{ backgroundColor: stageColors[colorKey] || '#6b7280' }}
                    >
                      {stage.name.charAt(0)}
                    </span>
                    <div className="stage-title-main">
                      <div className="stage-name-row">
                        <div className="stage-name">{stage.name.toUpperCase()}</div>
                        {isAdmin && pauseKey && (
                          <label
                            className={`stage-run-toggle ${isPaused(pauseKey) ? 'is-paused' : ''}`}
                            title="Desmarcado = pausado (no nuevos workers para este paso)"
                          >
                            <input
                              type="checkbox"
                              checked={!isPaused(pauseKey)}
                              disabled={saving}
                              onChange={(e) => {
                                const procesar = e.target.checked;
                                persistRuntime({ pause_steps: { [pauseKey]: !procesar } });
                              }}
                            />
                            <span>Procesar</span>
                          </label>
                        )}
                        {isAdmin && !pauseKey && (
                          <span className="stage-run-na" title="Sin clave pause.* en runtime">
                            —
                          </span>
                        )}
                      </div>
                      <div className="stage-progress">
                        <div className="progress-bar">
                          <div
                            className="progress-fill"
                            style={{
                              width: `${completionPercent}%`,
                              backgroundColor: stageColors[colorKey] || '#6b7280',
                            }}
                          />
                        </div>
                        <span className="progress-text">{completionPercent}%</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="stage-stats">
                  <div className="stat-item">
                    <span className="stat-label">Pendientes</span>
                    <span className="stat-value pending">{stage.pending_tasks}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Procesando</span>
                    <span className="stat-value processing">{stage.processing_tasks}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Completados</span>
                    <span className="stat-value completed">{stage.completed_tasks}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Errores</span>
                    <span className="stat-value error">❌ {stage.error_tasks ?? 0}</span>
                  </div>
                  {stage.paused_tasks != null && stage.paused_tasks > 0 && (
                    <div className="stat-item">
                      <span className="stat-label">Pausados</span>
                      <span className="stat-value paused">⏸️ {stage.paused_tasks}</span>
                    </div>
                  )}
                  {stage.granularity === 'news_item' &&
                    (stage.docs_with_all_insights_done != null || stage.docs_with_pending_insights != null) && (
                      <div
                        className="stat-item stat-hint"
                        title="Vista documento: 1 doc → N news_items → N insights"
                      >
                        <span className="stat-label">Docs</span>
                        <span className="stat-value">
                          ✓{stage.docs_with_all_insights_done ?? 0} ⏳{stage.docs_with_pending_insights ?? 0}
                        </span>
                      </div>
                    )}
                  {stage.granularity === 'document' &&
                    (stage.total_chunks > 0 || stage.news_items_count > 0) && (
                      <div
                        className="stat-item stat-hint"
                        title="Por documento; chunks internos por news_item"
                      >
                        <span className="stat-label">Chunks/News</span>
                        <span className="stat-value">
                          {stage.total_chunks ?? 0} / {stage.news_items_count ?? 0}
                        </span>
                      </div>
                    )}
                </div>
              </div>

              {isAdmin && stage.name === 'Insights' && (
                <details className="stage-llm-details">
                  <summary className="stage-llm-summary">
                    LLM insights ({providerMode === 'manual' ? 'orden manual' : `env: ${envLlm || '—'}`}
                    {envLlmModel ? ` / ${envLlmModel}` : ''})
                  </summary>
                  <div className="stage-llm-body">
                    <div className="llm-ollama-row">
                      <label className="llm-ollama-label" htmlFor="ins-ollama-model">
                        Modelo Ollama (insights)
                      </label>
                      <select
                        id="ins-ollama-model"
                        className="llm-ollama-select"
                        value={ollamaModel}
                        disabled={saving}
                        onChange={(e) => {
                          const v = e.target.value;
                          setOllamaModel(v);
                          persistRuntime({ ollama_model: v || null });
                        }}
                      >
                        <option value="">
                          Automático (OLLAMA_LLM_MODEL → LLM_MODEL si provider=ollama → mistral)
                        </option>
                        {ollamaModel &&
                          !ollamaModels.some((m) => m.name === ollamaModel) && (
                            <option value={ollamaModel}>{ollamaModel} (guardado)</option>
                          )}
                        {ollamaModels.map((m) => (
                          <option key={m.name} value={m.name}>
                            {m.name}
                            {m.size != null ? ` (${Math.round(Number(m.size) / 1e9)} GB)` : ''}
                          </option>
                        ))}
                      </select>
                      {ollamaModels.length === 0 && (
                        <span className="llm-ollama-hint" title="Servicio Ollama o /api/tags">
                          Sin modelos listados; comprueba que rag-ollama esté arriba y tengas pull.
                        </span>
                      )}
                    </div>
                    <label className="llm-radio">
                      <input
                        type="radio"
                        name="ins_llm_mode"
                        checked={providerMode === 'auto'}
                        disabled={saving}
                        onChange={() => {
                          setProviderMode('auto');
                          persistRuntime({ provider_mode: 'auto' });
                        }}
                      />
                      Automático (.env)
                    </label>
                    <label className="llm-radio">
                      <input
                        type="radio"
                        name="ins_llm_mode"
                        checked={providerMode === 'manual'}
                        disabled={saving}
                        onChange={() => {
                          setProviderMode('manual');
                          persistRuntime({
                            provider_mode: 'manual',
                            provider_order: orderFromSlots(providerSlots),
                          });
                        }}
                      />
                      Orden manual
                    </label>
                    {providerMode === 'manual' && (
                      <div className="llm-slots">
                        {[0, 1, 2].map((i) => (
                          <select
                            key={i}
                            className="llm-slot-select"
                            value={providerSlots[i] || ''}
                            disabled={saving}
                            onChange={(e) => {
                              const next = [...providerSlots];
                              next[i] = e.target.value;
                              for (let j = 0; j < 3; j++) {
                                if (j !== i && e.target.value && next[j] === e.target.value) next[j] = '';
                              }
                              setProviderSlots(next);
                              persistRuntime({
                                provider_mode: 'manual',
                                provider_order: orderFromSlots(next),
                              });
                            }}
                          >
                            <option value="">—</option>
                            {PROVIDER_OPTIONS.map((p) => {
                              const cfg = availableProviders.find((a) => a.id === p.id);
                              const suf = cfg && !cfg.configured ? ' (sin key)' : '';
                              return (
                                <option key={p.id} value={p.id}>
                                  {p.label}
                                  {suf}
                                </option>
                              );
                            })}
                          </select>
                        ))}
                      </div>
                    )}
                  </div>
                </details>
              )}

              {hasReady && (
                <div className="ready-indicator">
                  ✅ {stage.ready_for_next} documento{stage.ready_for_next > 1 ? 's' : ''} listo
                  {stage.ready_for_next > 1 ? 's' : ''} para siguiente etapa
                </div>
              )}

              {isBlocked && (
                <div className="blockers-section">
                  <div className="blockers-title">⚠️ Bloqueos detectados:</div>
                  {stage.blockers.map((blocker, idx) => (
                    <div key={idx} className="blocker-item">
                      <div className="blocker-reason">
                        <strong>Razón:</strong> {blocker.reason}
                        {blocker.count > 0 && <span className="blocker-count"> ({blocker.count})</span>}
                      </div>
                      <div className="blocker-solution">
                        <strong>Solución:</strong> {blocker.solution}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!isBlocked && !hasReady && stage.pending_tasks === 0 && stage.processing_tasks === 0 && (
                <div className="stage-status-message">✅ Stage funcionando normalmente</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default PipelineAnalysisPanel;
