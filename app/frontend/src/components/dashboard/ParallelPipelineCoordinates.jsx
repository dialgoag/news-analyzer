import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as d3 from 'd3';
import { MapIcon } from '@heroicons/react/24/outline';
import { useDashboardFilters } from '../hooks/useDashboardFilters.jsx';
import { transformDocumentsForVisualization } from '../../services/documentDataService';
import ExportMenu from './ExportMenu';
import './ParallelPipelineCoordinates.css';

const AXES = [
  { key: 'upload', label: 'Upload', type: 'stage' },
  { key: 'ocr', label: 'OCR', type: 'stage' },
  { key: 'chunking', label: 'Chunking', type: 'stage' },
  { key: 'indexing', label: 'Indexing', type: 'stage' },
  { key: 'news', label: 'News Items', type: 'news' },
  { key: 'insights', label: 'Insights', type: 'insight' },
  { key: 'indexInsights', label: 'Index Insights', type: 'index' }
];

const STAGE_FLOW_ORDER = ['upload', 'ocr', 'chunking', 'indexing', 'insights', 'completed', 'error'];
const INSIGHT_STATE_DOMAIN = ['pending', 'queued', 'generating', 'done', 'error'];
const INDEX_STATE_DOMAIN = ['pending', 'indexing', 'ready', 'indexed', 'error'];

const DONE_STATES = new Set(['done', 'ready', 'indexed', 'completed']);
const ERROR_STATES = new Set(['error', 'failed']);
const PROGRESS_STATES = new Set(['processing', 'in_progress', 'queued', 'generating', 'active', 'indexing']);
const BUCKET_ORDER = [
  { key: 'pending', label: 'En proceso' },
  { key: 'done', label: 'Completado' },
  { key: 'error', label: 'Errores' }
];
const GROUPING_OPTIONS = [
  { value: 'document', label: 'Docs' },
  { value: 'day', label: 'Día' },
  { value: 'week', label: 'Semana' },
  { value: 'month', label: 'Mes' }
];

// Using design tokens colors
const TOPIC_COLORS = ['#4caf50', '#2196f3', '#f97316', '#a78bfa', '#facc15', '#38bdf8', '#fb7185', '#c084fc', '#4ade80', '#f472b6'];
const DEFAULT_TOPIC_META = { key: 'sin-tema', label: 'Sin tema' };
const MAX_TOPIC_LEGEND_ITEMS = 8;

function normalizeTopicKey(label) {
  if (!label) return DEFAULT_TOPIC_META.key;
  const cleaned = label
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return cleaned || DEFAULT_TOPIC_META.key;
}

function pushCandidate(value, bag) {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed) bag.push(trimmed);
  }
}

function collectArrayCandidates(source, bag) {
  if (!source) return;
  if (Array.isArray(source)) {
    source.forEach((entry) => {
      if (typeof entry === 'string') {
        pushCandidate(entry, bag);
      } else if (entry?.label) {
        pushCandidate(entry.label, bag);
      } else if (entry?.name) {
        pushCandidate(entry.name, bag);
      }
    });
    return;
  }
  if (typeof source === 'string') {
    source.split(/[;,]/).forEach((piece) => pushCandidate(piece, bag));
  }
}

function getNewsTopicMeta(news) {
  const candidates = [];
  if (news) {
    pushCandidate(news.topic, candidates);
    pushCandidate(news.news_topic, candidates);
    pushCandidate(news.category, candidates);
    pushCandidate(news.section, candidates);
    pushCandidate(news.theme, candidates);
    pushCandidate(news.primary_keyword, candidates);
    collectArrayCandidates(news.topics, candidates);
    collectArrayCandidates(news.tags, candidates);
  }
  const label = candidates.find((value) => value.length >= 2) || DEFAULT_TOPIC_META.label;
  return {
    key: normalizeTopicKey(label),
    label
  };
}

function parseStageState(status, processingStage) {
  if (!status) return { stage: 'upload', state: 'pending' };
  if (status === 'completed') return { stage: 'completed', state: 'done' };
  if (status === 'error') return { stage: 'error', state: 'error' };
  const parts = status.split('_');
  if (parts.length >= 2) {
    return { stage: parts[0], state: parts.slice(1).join('_') };
  }
  return { stage: processingStage || status, state: 'pending' };
}

function normalizeStageState(doc, stageKey) {
  const { stage: currentStage, state } = parseStageState(doc.status, doc.processing_stage);
  const stageIndex = STAGE_FLOW_ORDER.indexOf(stageKey);
  let currentIndex = STAGE_FLOW_ORDER.indexOf(currentStage);
  if (stageIndex === -1) return 'pending';
  if (currentIndex === -1 && doc.processing_stage) {
    currentIndex = STAGE_FLOW_ORDER.indexOf(doc.processing_stage);
  }
  if (currentIndex === -1) return 'pending';
  if (stageIndex < currentIndex) return 'done';
  if (stageIndex > currentIndex) return state === 'error' ? 'error' : 'pending';
  if (state === 'processing') return 'processing';
  if (state === 'done') return 'done';
  if (state === 'error') return 'error';
  return 'pending';
}

function normalizeInsightStatus(status) {
  if (!status) return 'pending';
  if (INSIGHT_STATE_DOMAIN.includes(status)) return status;
  if (status === 'ready') return 'done';
  return 'pending';
}

function normalizeIndexStatus(indexStatus, insightStatus) {
  if (indexStatus === 'indexed') return 'indexed';
  if (indexStatus === 'indexing') return 'indexing';
  if (indexStatus === 'ready') return 'ready';
  if (insightStatus === 'error') return 'error';
  if (insightStatus === 'done') return 'ready';
  return 'pending';
}

function aggregateStageStates(states) {
  if (states.some((state) => ERROR_STATES.has(state))) return 'error';
  if (states.every((state) => DONE_STATES.has(state))) return 'done';
  if (states.some((state) => state === 'processing')) return 'processing';
  return 'pending';
}

function determineBucket(stageStates, docs) {
  const docList = Array.isArray(docs) ? docs : [docs].filter(Boolean);
  const hasError =
    docList.some((doc) => doc && ERROR_STATES.has(doc.status)) ||
    Object.values(stageStates).some((state) => ERROR_STATES.has(state));
  if (hasError) return 'error';
  const isDone =
    docList.every((doc) => doc && doc.status === 'completed') ||
    Object.values(stageStates).every((state) => DONE_STATES.has(state));
  if (isDone) return 'done';
  return 'pending';
}

function getAxisState(line, axisKey) {
  if (axisKey === 'news') {
    return line.newsMeta?.news_status || 'pending';
  }
  if (axisKey === 'insights') {
    return line.axisValues.insights;
  }
  if (axisKey === 'indexInsights') {
    return line.axisValues.indexInsights;
  }
  return line.stageStates[axisKey] || 'pending';
}

function getStateCategory(state) {
  if (!state) return 'pending';
  if (ERROR_STATES.has(state)) return 'error';
  if (DONE_STATES.has(state) || state === 'indexing_done') return 'done';
  if (PROGRESS_STATES.has(state)) return 'progress';
  return 'pending';
}

function getStateColor(state) {
  const category = getStateCategory(state);
  if (category === 'error') return '#f44336';   // --color-error
  if (category === 'done') return '#4caf50';    // --color-active (green for done)
  if (category === 'progress') return '#ff9800'; // --color-pending (orange for progress)
  return '#4dd0e1';                              // --color-info
}

function parseDocDate(doc) {
  const value = doc.news_date || doc.ingested_at || doc.upload_date;
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Date(date.getTime());
}

function getISOWeekKey(date) {
  const tmp = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const dayNum = tmp.getUTCDay() || 7;
  tmp.setUTCDate(tmp.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
  const weekNum = Math.ceil((((tmp - yearStart) / 86400000) + 1) / 7);
  return `${tmp.getUTCFullYear()}-W${String(weekNum).padStart(2, '0')}`;
}

function getGroupingKeyForMode(doc, mode) {
  if (mode === 'document') {
    return { key: doc.document_id || 'unknown', label: doc.filename || doc.document_id || 'Documento' };
  }
  const date = parseDocDate(doc);
  if (!date) {
    return { key: `sin-fecha-${mode}`, label: 'Sin fecha' };
  }
  if (mode === 'day') {
    const key = date.toISOString().slice(0, 10);
    return { key, label: `Día ${key}` };
  }
  if (mode === 'week') {
    const key = getISOWeekKey(date);
    return { key, label: `Semana ${key}` };
  }
  if (mode === 'month') {
    const key = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`;
    return { key, label: `Mes ${key}` };
  }
  return { key: doc.document_id || 'unknown', label: doc.filename || doc.document_id || 'Documento' };
}

function aggregateStatus(docs) {
  if (docs.some((item) => item.status === 'error')) return 'error';
  if (docs.every((item) => item.status === 'completed')) return 'completed';
  return docs.find((item) => item.status)?.status || 'pending';
}

function getStateIcon(state) {
  const category = getStateCategory(state);
  if (category === 'error') return '❌';
  if (category === 'done') return '✓';
  if (category === 'progress') return '🔄';
  return '⏳';
}

function buildTooltip(line) {
  const news = line.newsMeta || {};
  const groupingInfo = line.groupLabel && line.groupLabel !== line.docName
    ? `<div class="parallel-tooltip__group">📁 Grupo: ${line.groupLabel}</div>`
    : '';
  
  // Build pipeline status
  const stageIcons = {
    upload: getStateIcon(line.stageStates.upload),
    ocr: getStateIcon(line.stageStates.ocr),
    chunking: getStateIcon(line.stageStates.chunking),
    indexing: getStateIcon(line.stageStates.indexing)
  };
  
  const pipelineStatus = `Upload ${stageIcons.upload} → OCR ${stageIcons.ocr} → Chunking ${stageIcons.chunking} → Indexing ${stageIcons.indexing}`;
  
  return `
    <div class="parallel-tooltip__title">📄 ${line.docName || line.docId}</div>
    <div class="parallel-tooltip__id">Doc ID: ${line.docId}</div>
    ${groupingInfo}
    <div class="parallel-tooltip__topic">📌 Tema: <strong>${line.topicLabel || 'Sin tema'}</strong></div>
    <div class="parallel-tooltip__news">
      <strong>📰 News Item #${news.item_index ?? '—'}:</strong>
      <div class="parallel-tooltip__news-title">${news.title || 'Sin título'}</div>
    </div>
    <div class="parallel-tooltip__pipeline">
      <strong>Pipeline:</strong> ${pipelineStatus}
    </div>
    <div class="parallel-tooltip__insights">
      ├─ Insights: <strong>${line.axisValues.insights}</strong> ${getStateIcon(line.axisValues.insights)}
      <br />
      └─ Indexing: <strong>${line.axisValues.indexInsights}</strong> ${getStateIcon(line.axisValues.indexInsights)}
    </div>
  `;
}

const MIN_DENSITY = 0.8;
const MAX_DENSITY = 3;

export default function ParallelPipelineCoordinates({ data, documents = [] }) {
  const containerRef = useRef(null);
  const scrollRef = useRef(null);
  const svgRef = useRef(null);
  const tooltipRef = useRef(null);
  const [chartWidth, setChartWidth] = useState(960);
  const [density, setDensity] = useState(1.2);
  const [hoveredId, setHoveredId] = useState(null);
  const [scrollState, setScrollState] = useState({ ratio: 1, offset: 0 });
  const { filters, updateFilter, clearFilter } = useDashboardFilters();
  const [groupingMode, setGroupingMode] = useState('document');
  const [fullHeight, setFullHeight] = useState(false);
  const [selectedTopics, setSelectedTopics] = useState([]);

  const normalizedDocs = useMemo(
    () => transformDocumentsForVisualization(documents),
    [documents]
  );

  const baseDocs = useMemo(() => {
    if (Array.isArray(data?.documents) && data.documents.length > 0) {
      return data.documents;
    }
    return normalizedDocs.map((doc) => ({
      document_id: doc.document_id,
      filename: doc.filename,
      status: doc.status,
      processing_stage: doc.processing_stage,
      news_items_total: doc.news_count || 0,
      ingested_at: doc.upload_date,
      news_items: []
    }));
  }, [data, normalizedDocs]);

  const docLookup = useMemo(() => {
    const map = new Map();
    normalizedDocs.forEach((doc) => map.set(doc.document_id, doc));
    return map;
  }, [normalizedDocs]);

  const groupingMeta = useMemo(() => {
    const counts = new Map();
    baseDocs.forEach((doc) => {
      const enriched = docLookup.get(doc.document_id) || doc;
      const { key, label } = getGroupingKeyForMode(enriched, groupingMode);
      const entry = counts.get(key) || { count: 0, label };
      entry.count += 1;
      entry.label = label;
      counts.set(key, entry);
    });
    const maxCount = counts.size
      ? Math.max(...Array.from(counts.values(), (entry) => entry.count))
      : 1;
    return { counts, maxCount: maxCount || 1 };
  }, [baseDocs, docLookup, groupingMode]);

  const groupingLabel = useMemo(
    () => GROUPING_OPTIONS.find((option) => option.value === groupingMode)?.label || '',
    [groupingMode]
  );

  const selectedTopicSet = useMemo(() => new Set(selectedTopics), [selectedTopics]);

  const toggleTopicSelection = useCallback((topicKey) => {
    if (!topicKey) return;
    setSelectedTopics((prev) => {
      if (prev.includes(topicKey)) {
        return prev.filter((key) => key !== topicKey);
      }
      return [...prev, topicKey];
    });
  }, []);

  const clearTopicFilters = useCallback(() => {
    setSelectedTopics([]);
  }, []);

  const lineData = useMemo(() => {
    const list = [];
    const newsDomainSet = new Set();
    let docsWithNews = 0;
    const layoutEntries = [];
    const layoutSeen = new Set();
    const topicMap = new Map();

    baseDocs.forEach((doc) => {
      const enriched = docLookup.get(doc.document_id) || doc;
      const stageStates = {};
      AXES.filter((axis) => axis.type === 'stage').forEach((axis) => {
        stageStates[axis.key] = normalizeStageState(enriched, axis.key);
      });

      const groupingInfo = getGroupingKeyForMode(enriched, groupingMode);
      const groupKey = groupingMode === 'document' ? doc.document_id : groupingInfo.key;
      const groupLabel = groupingMode === 'document'
        ? (doc.filename || enriched.filename || doc.document_id)
        : groupingInfo.label;
      const bucket = determineBucket(stageStates, doc);

      if (!layoutSeen.has(doc.document_id)) {
        layoutEntries.push({
          id: doc.document_id,
          label: doc.filename || enriched.filename || doc.document_id,
          bucket,
          groupKey,
          groupLabel
        });
        layoutSeen.add(doc.document_id);
      }

      let items = Array.isArray(doc.news_items) ? doc.news_items : [];
      if (!items.length) {
        items = [{
          news_item_id: `${doc.document_id}::placeholder`,
          document_id: doc.document_id,
          title: doc.news_items_total > 0 ? 'Noticias detectadas' : 'Sin noticias registradas',
          item_index: 0,
          news_status: doc.news_items_total > 0 ? 'pending' : 'none',
          insight_status: doc.status?.startsWith('insights') || doc.status === 'completed' ? 'done' : 'pending',
          index_status: doc.status === 'completed' ? 'indexed' : 'pending'
        }];
      } else {
        docsWithNews += 1;
      }

      const groupCountEntry = groupingMeta.counts.get(groupKey);
      const targetNewsCount = doc.news_items_total || doc.news_count || items.length || 1;
      const widthFromNews = 1.2 + Math.min(4.5, targetNewsCount * 0.35);
      const widthFromGroup = 1.4 + ((groupCountEntry?.count || 1) / groupingMeta.maxCount) * 4.6;
      const lineWidth = groupingMode === 'document' ? widthFromNews : widthFromGroup;

      items.forEach((news, idx) => {
        const insightState = normalizeInsightStatus(news.insight_status);
        const indexState = normalizeIndexStatus(news.index_status, news.insight_status);
        const newsId = news.news_item_id || `${doc.document_id}::${idx}`;
        newsDomainSet.add(newsId);
        const topicMeta = getNewsTopicMeta(news);
        let topicEntry = topicMap.get(topicMeta.key);
        if (!topicEntry) {
          topicEntry = { key: topicMeta.key, label: topicMeta.label, ids: [], count: 0 };
          topicMap.set(topicMeta.key, topicEntry);
        }
        topicEntry.ids.push(newsId);
        topicEntry.count += 1;
        list.push({
          id: `${doc.document_id}::${newsId}`,
          docId: doc.document_id,
          docName: doc.filename || enriched.filename,
          layoutId: doc.document_id,
          stageStates,
          newsMeta: news,
          bucket,
          topicKey: topicMeta.key,
          topicLabel: topicMeta.label,
          groupKey,
          groupLabel,
          axisValues: {
            news: newsId,
            insights: insightState,
            indexInsights: indexState
          },
          lineWidth
        });
      });
    });

    if (newsDomainSet.size === 0) {
      newsDomainSet.add('__empty__');
    }

    let topicEntries = Array.from(topicMap.values());
    if (!topicEntries.length && newsDomainSet.size > 0) {
      topicEntries = [{
        key: DEFAULT_TOPIC_META.key,
        label: DEFAULT_TOPIC_META.label,
        ids: Array.from(newsDomainSet),
        count: newsDomainSet.size
      }];
    }
    topicEntries.sort((a, b) => {
      if (b.count !== a.count) return b.count - a.count;
      return a.label.localeCompare(b.label, 'es', { sensitivity: 'base' });
    });
    const palette = TOPIC_COLORS.length ? TOPIC_COLORS : (d3.schemeTableau10 || ['#38bdf8', '#fb7185']);
    topicEntries.forEach((entry, idx) => {
      entry.color = palette[idx % palette.length];
    });
    const topicColorLookup = new Map(topicEntries.map((entry) => [entry.key, entry.color]));
    list.forEach((line) => {
      if (line.topicKey && topicColorLookup.has(line.topicKey)) {
        line.topicColor = topicColorLookup.get(line.topicKey);
      }
    });
    const orderedNewsDomain = topicEntries.length
      ? topicEntries.flatMap((entry) => entry.ids)
      : Array.from(newsDomainSet);
    const topicLookup = new Map(topicEntries.map((entry) => [entry.key, entry]));

    return {
      lines: list,
      newsDomain: orderedNewsDomain,
      stats: {
        docs: baseDocs.length,
        docsWithNews,
        news: list.length,
        groups: groupingMode === 'document' ? baseDocs.length : groupingMeta.counts.size || 0,
        topics: topicEntries.length
      },
      layoutEntries,
      topics: topicEntries,
      topicLookup
    };
  }, [baseDocs, docLookup, groupingMode, groupingMeta]);

  const docPositions = useMemo(() => {
    const slotMap = new Map();
    const slotLabelMap = new Map();
    const bucketSections = [];
    const groupSections = [];
    const gapSize = 0.8;
    let cursor = 0;

    const entriesByBucket = lineData.layoutEntries.reduce((acc, entry) => {
      if (!acc[entry.bucket]) acc[entry.bucket] = [];
      acc[entry.bucket].push(entry);
      return acc;
    }, {});

    BUCKET_ORDER.forEach(({ key, label }) => {
      const docs = (entriesByBucket[key] || []).slice().sort((a, b) => {
        if (groupingMode !== 'document' && a.groupKey !== b.groupKey) {
          return a.groupKey.localeCompare(b.groupKey, 'es', { sensitivity: 'base' });
        }
        return a.label.localeCompare(b.label, 'es', { sensitivity: 'base' });
      });
      if (!docs.length) return;
      const start = cursor;
      let currentGroupKey = groupingMode !== 'document' ? docs[0]?.groupKey : null;
      let currentGroupLabel = groupingMode !== 'document' ? docs[0]?.groupLabel : '';
      let groupStart = cursor;
      docs.forEach(({ id, label: docLabel, groupKey, groupLabel: docGroupLabel }) => {
        if (groupingMode !== 'document' && currentGroupKey !== null && groupKey !== currentGroupKey) {
          groupSections.push({
            key: `${key}-${currentGroupKey}-${groupSections.length}`,
            label: currentGroupLabel,
            start: groupStart,
            end: cursor
          });
          currentGroupKey = groupKey;
          currentGroupLabel = docGroupLabel;
          groupStart = cursor;
        }
        const slot = cursor + 0.5;
        slotMap.set(id, slot);
        slotLabelMap.set(slot, docLabel);
        cursor += 1;
      });
      if (groupingMode !== 'document' && currentGroupKey) {
        groupSections.push({
          key: `${key}-${currentGroupKey}-${groupSections.length}`,
          label: currentGroupLabel,
          start: groupStart,
          end: cursor
        });
      }
      bucketSections.push({ key, label, start, end: cursor });
      cursor += gapSize;
    });

    const totalSlots = Math.max(cursor - gapSize, 1);
    return {
      slotMap,
      slotLabelMap,
      bucketSections,
      groupSections,
      totalSlots,
      count: slotMap.size
    };
  }, [lineData.layoutEntries, groupingMode]);

  const chartHeight = useMemo(() => {
    const rowHeight = 28 * density;
    const rows = Math.max(docPositions.count, 1);
    return Math.max(520, rows * rowHeight + 240);
  }, [docPositions.count, density]);

  const updateScrollState = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const ratio = el.clientHeight / el.scrollHeight;
    const offset = el.scrollTop / el.scrollHeight;
    setScrollState({
      ratio: Number.isFinite(ratio) ? Math.min(1, ratio) : 1,
      offset: Number.isFinite(offset) ? Math.min(1, Math.max(0, offset)) : 0
    });
  }, []);

  useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      entries.forEach((entry) => {
        const width = Math.max(720, entry.contentRect.width - 32);
        setChartWidth(width);
      });
    });
    if (containerRef.current) {
      observer.observe(containerRef.current);
    }
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    updateScrollState();
    el.addEventListener('scroll', updateScrollState);
    return () => el.removeEventListener('scroll', updateScrollState);
  }, [chartHeight, updateScrollState]);

  useEffect(() => {
    if (!svgRef.current || !lineData.lines.length) {
      if (svgRef.current) {
        d3.select(svgRef.current).selectAll('*').remove();
      }
      return;
    }

    const width = chartWidth;
    const height = chartHeight;
    const margin = { top: 60, right: 32, bottom: 40, left: 200 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const docSlotMap = docPositions.slotMap;
    const docLinear = d3.scaleLinear()
      .domain([0, docPositions.totalSlots])
      .range([innerHeight, 0]);
    const docY = (layoutId) => docLinear(docSlotMap.get(layoutId) ?? 0);
    const newsScale = d3.scalePoint(lineData.newsDomain, [innerHeight, 0]).padding(0.5);
    const newsStep = typeof newsScale.step === 'function'
      ? newsScale.step()
      : (innerHeight / Math.max(1, lineData.newsDomain.length));
    const newsHalfStep = newsStep / 2;
    const insightScale = d3.scalePoint(INSIGHT_STATE_DOMAIN, [innerHeight, 0]);
    const indexScale = d3.scalePoint(INDEX_STATE_DOMAIN, [innerHeight, 0]);
    const xScale = d3.scalePoint(AXES.map((axis) => axis.key), [0, innerWidth]).padding(0.4);
    const newsX = xScale('news');

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);
    const topicFilterSet = new Set(selectedTopics);
    const topicFilterActive = topicFilterSet.size > 0;

    const docTickEntries = Array.from(docPositions.slotLabelMap.entries()).sort(
      (a, b) => a[0] - b[0]
    );
    const stageTickStep = Math.max(1, Math.floor(docTickEntries.length / 12));
    const stageTickValues = docTickEntries
      .filter((_, idx) => idx % stageTickStep === 0)
      .map(([slot]) => slot);

    AXES.forEach((axis) => {
      const axisGroup = g.append('g').attr('transform', `translate(${xScale(axis.key)},0)`);
      if (axis.type === 'stage') {
        axisGroup.call(
          d3.axisLeft(docLinear)
            .tickValues(stageTickValues)
            .tickFormat((value) => {
              const label = docPositions.slotLabelMap.get(value);
              return (label || '').slice(0, 22);
            })
        );
      } else if (axis.type === 'news') {
        axisGroup.call(d3.axisLeft(newsScale).tickFormat(() => ''));
      } else if (axis.type === 'insight') {
        axisGroup.call(d3.axisLeft(insightScale));
      } else if (axis.type === 'index') {
        axisGroup.call(d3.axisLeft(indexScale));
      }
      axisGroup.selectAll('text').attr('fill', '#cbd5e1').attr('font-size', '10px');
      axisGroup.selectAll('path,line').attr('stroke', 'rgba(148,163,184,0.35)');
      axisGroup.append('text')
        .attr('y', -16)
        .attr('fill', '#f1f5f9')
        .attr('font-size', '12px')
        .attr('font-family', 'Fira Code, monospace')
        .attr('text-anchor', 'middle')
        .text(axis.label);
    });

    const accessors = {
      upload: (line) => docY(line.layoutId || line.docId),
      ocr: (line) => docY(line.layoutId || line.docId),
      chunking: (line) => docY(line.layoutId || line.docId),
      indexing: (line) => docY(line.layoutId || line.docId),
      news: (line) => newsScale(line.axisValues.news),
      insights: (line) => insightScale(line.axisValues.insights),
      indexInsights: (line) => indexScale(line.axisValues.indexInsights)
    };

    const highlightedDoc = filters.documentId;
    const highlightedStage = filters.stage;

    const matchesStageFilter = (line) => {
      if (!highlightedStage) return true;
      if (AXES.some((axis) => axis.key === highlightedStage)) {
        return true;
      }
      if (highlightedStage === 'insights') {
        return line.axisValues.insights !== 'pending';
      }
      if (highlightedStage === 'indexInsights') {
        return line.axisValues.indexInsights !== 'pending';
      }
      return true;
    };

    if (groupingMode !== 'document' && docPositions.groupSections.length) {
      const groupingLayer = g.append('g').attr('class', 'parallel-group-layer');
      docPositions.groupSections.forEach((section) => {
        const yStart = docLinear(section.start);
        const yEnd = docLinear(section.end);
        const height = Math.abs(yEnd - yStart);
        if (height < 8) return;
        groupingLayer.append('rect')
          .attr('class', 'parallel-group-band')
          .attr('x', -margin.left + 4)
          .attr('width', innerWidth + margin.left - 8)
          .attr('y', Math.min(yStart, yEnd))
          .attr('height', height);
        groupingLayer.append('text')
          .attr('class', 'parallel-group-label')
          .attr('x', -margin.left + 10)
          .attr('y', (yStart + yEnd) / 2)
          .text(section.label);
      });
    }

    if (lineData.topics.length && Number.isFinite(newsX)) {
      const topicLayer = g.append('g').attr('class', 'parallel-topic-layer');
      const bandWidth = 54;
      lineData.topics.forEach((topic) => {
        if (!topic.ids.length) return;
        const isSelected = topicFilterSet.has(topic.key);
        const isDimmed = topicFilterActive && !isSelected;
        const firstY = newsScale(topic.ids[0]);
        const lastY = newsScale(topic.ids[topic.ids.length - 1]);
        if (firstY == null || lastY == null) return;
        const rawStart = Math.min(firstY, lastY) - newsHalfStep;
        const rawEnd = Math.max(firstY, lastY) + newsHalfStep;
        const yStart = Math.max(0, rawStart);
        const yEnd = Math.min(innerHeight, rawEnd);
        const height = Math.max(12, yEnd - yStart);
        const bandClasses = [
          'parallel-topic-band',
          isSelected ? 'selected' : '',
          isDimmed ? 'dimmed' : ''
        ].filter(Boolean).join(' ');
        topicLayer.append('rect')
          .attr('class', bandClasses)
          .attr('x', newsX - bandWidth / 2)
          .attr('width', bandWidth)
          .attr('y', yStart)
          .attr('height', height)
          .attr('fill', topic.color || '#38bdf8')
          .attr('fill-opacity', 0.12)
          .attr('stroke', topic.color || '#38bdf8')
          .attr('stroke-opacity', 0.35)
          .style('cursor', 'pointer')
          .on('click', (event) => {
            event.stopPropagation();
            toggleTopicSelection(topic.key);
          });
        topicLayer.append('text')
          .attr('class', 'parallel-topic-label')
          .attr('x', newsX + bandWidth / 2 + 6)
          .attr('y', yStart + height / 2)
          .attr('fill', topic.color || '#38bdf8')
          .text(`${topic.label} (${topic.count})`);
      });
    }

    const bucketLayer = g.append('g').attr('class', 'parallel-bucket-layer');
    docPositions.bucketSections.forEach((section) => {
      bucketLayer.append('text')
        .attr('class', 'parallel-bucket-label')
        .attr('x', -margin.left + 6)
        .attr('y', docLinear((section.start + section.end) / 2))
        .text(section.label);
      bucketLayer.append('line')
        .attr('class', 'parallel-bucket-divider')
        .attr('x1', -20)
        .attr('x2', innerWidth + 20)
        .attr('y1', docLinear(section.end))
        .attr('y2', docLinear(section.end));
    });

    const linesGroup = g.append('g').attr('fill', 'none');
    const tooltip = d3.select(tooltipRef.current);

    const docGroups = linesGroup.selectAll('.parallel-doc')
      .data(lineData.lines, (line) => line.id)
      .join((enter) => enter.append('g').attr('class', 'parallel-doc'));

    docGroups.each(function(line) {
      const segments = [];
      for (let i = 0; i < AXES.length - 1; i++) {
        const fromKey = AXES[i].key;
        const toKey = AXES[i + 1].key;
        const fromY = accessors[fromKey](line);
        const toY = accessors[toKey](line);
        if (fromY === undefined || toY === undefined) continue;
        segments.push({
          key: `${line.id}-${fromKey}-${toKey}`,
          fromX: xScale(fromKey),
          toX: xScale(toKey),
          fromY,
          toY,
          state: getAxisState(line, toKey)
        });
      }

      const axisMarkers = AXES.map((axis) => {
        const accessor = accessors[axis.key];
        if (typeof accessor !== 'function') return null;
        const y = accessor(line);
        if (!Number.isFinite(y)) return null;
        return {
          key: `${line.id}-${axis.key}-marker`,
          x: xScale(axis.key),
          y,
          state: getAxisState(line, axis.key)
        };
      }).filter(Boolean);

      const computeOpacity = () => {
        if (hoveredId && hoveredId !== line.id) return 0.15;
        if (highlightedDoc && highlightedDoc !== line.docId) return 0.2;
        if (!matchesStageFilter(line)) return 0.25;
        if (topicFilterActive && (!line.topicKey || !topicFilterSet.has(line.topicKey))) return 0.08;
        return 0.9;
      };

      const handleMouseEnter = (event) => {
        setHoveredId(line.id);
        const bounds = containerRef.current?.getBoundingClientRect();
        if (!bounds) return;
        tooltip
          .style('opacity', 1)
          .style('left', `${event.clientX - bounds.left + 12}px`)
          .style('top', `${event.clientY - bounds.top + 12}px`)
          .html(buildTooltip(line));
      };

      const handleMouseMove = (event) => {
        if (!tooltipRef.current || !containerRef.current) return;
        const bounds = containerRef.current.getBoundingClientRect();
        tooltip
          .style('left', `${event.clientX - bounds.left + 12}px`)
          .style('top', `${event.clientY - bounds.top + 12}px`);
      };

      const handleMouseLeave = () => {
        setHoveredId(null);
        tooltip.style('opacity', 0);
      };

      const handleClick = (event) => {
        event.stopPropagation();
        updateFilter('documentId', line.docId);
        updateFilter('stage', 'insights');
      };

      const segmentSelection = d3.select(this)
        .selectAll('line')
        .data(segments, (segment) => segment.key);

      segmentSelection.join(
        (enter) => enter.append('line'),
        (update) => update,
        (exit) => exit.remove()
      )
        .attr('x1', (segment) => segment.fromX)
        .attr('y1', (segment) => segment.fromY)
        .attr('x2', (segment) => segment.toX)
        .attr('y2', (segment) => segment.toY)
        .attr('stroke', (segment) => getStateColor(segment.state))
        .attr('stroke-width', () => {
          const baseWidth = line.lineWidth || 1.6;
          return hoveredId === line.id ? baseWidth + 1 : baseWidth;
        })
        .attr('opacity', computeOpacity)
        .attr('stroke-linecap', 'round')
        .on('mouseenter', handleMouseEnter)
        .on('mousemove', handleMouseMove)
        .on('mouseleave', handleMouseLeave)
        .on('click', handleClick);

      const markerSelection = d3.select(this)
        .selectAll('circle')
        .data(axisMarkers, (marker) => marker.key);

      markerSelection.join(
        (enter) => enter.append('circle').attr('class', 'parallel-axis-marker'),
        (update) => update,
        (exit) => exit.remove()
      )
        .attr('cx', (marker) => marker.x)
        .attr('cy', (marker) => marker.y)
        .attr('r', hoveredId === line.id ? 4 : 3.2)
        .attr('fill', (marker) => getStateColor(marker.state))
        .attr('stroke', '#0f172a')
        .attr('stroke-width', 1.1)
        .attr('opacity', computeOpacity)
        .on('mouseenter', handleMouseEnter)
        .on('mousemove', handleMouseMove)
        .on('mouseleave', handleMouseLeave)
        .on('click', handleClick);
    });
  }, [
    chartWidth,
    chartHeight,
    lineData,
    hoveredId,
    filters.documentId,
    filters.stage,
    updateFilter,
    docPositions,
    groupingMode,
    selectedTopics,
    toggleTopicSelection
  ]);

  const clearAllFilters = () => {
    clearFilter('documentId');
    clearFilter('stage');
    clearTopicFilters();
  };

  return (
    <div className="parallel-pipeline-card" ref={containerRef}>
      <div className="parallel-card-header">
        <div>
          <h4>
            <MapIcon className="parallel-card-header__icon" aria-hidden="true" />
            Flujo Pipeline: Documento → Noticias → Insights
          </h4>
          <p className="parallel-description">
            Visualiza el recorrido completo de cada documento a través del pipeline. 
            Las líneas se <strong>bifurcan</strong> en el eje "News Items" (1 doc → N noticias), 
            luego cada noticia genera insights e indexación. 
            <br />
            <em>Filtra por tema, agrupa por fecha, y detecta cuellos de botella.</em>
          </p>
        </div>
        <div className="parallel-header-metrics">
          <span>{lineData.stats.docs} documentos</span>
          {lineData.stats.topics > 0 && (
            <span>{lineData.stats.topics} temas</span>
          )}
          {groupingMode !== 'document' && (
            <span>{lineData.stats.groups} grupos ({groupingLabel})</span>
          )}
          <span>{lineData.stats.news} líneas activas</span>
          <span>{lineData.stats.docsWithNews} docs con noticias</span>
          {(filters.documentId || filters.stage) && (
            <button type="button" onClick={clearAllFilters}>
              Limpiar filtros
            </button>
          )}
          <ExportMenu
            data={lineData.lines.map(line => ({
              docId: line.docId,
              docName: line.docName,
              topicLabel: line.topicLabel,
              bucket: line.bucket,
              groupLabel: line.groupLabel,
              newsTitle: line.newsMeta?.title,
              insightStatus: line.axisValues.insights,
              indexStatus: line.axisValues.indexInsights
            }))}
            filename="parallel-coordinates-data"
            targetElement={containerRef.current}
          />
        </div>
      </div>

      <div className="parallel-controls">
        <div className="parallel-controls__left">
          <label>
            Zoom vertical
            <input
              type="range"
              min={MIN_DENSITY}
              max={MAX_DENSITY}
              step="0.2"
              value={density}
              onChange={(event) => setDensity(parseFloat(event.target.value))}
            />
          </label>
          <div className="parallel-grouping">
            <span>Agrupar por</span>
            <div className="parallel-grouping-options">
              {GROUPING_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={option.value === groupingMode ? 'active' : ''}
                  onClick={() => option.value !== groupingMode && setGroupingMode(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="parallel-controls__right">
          <button
            type="button"
            className={`parallel-fullscreen-toggle${fullHeight ? ' active' : ''}`}
            onClick={() => setFullHeight((prev) => !prev)}
          >
            {fullHeight ? 'Contraer vista' : 'Expandir vista'}
          </button>
          <div className="parallel-minimap">
            <div className="parallel-minimap__track">
              <span
                style={{
                  height: `${scrollState.ratio * 100}%`,
                  top: `${scrollState.offset * 100}%`
                }}
              />
            </div>
            <small>Contexto</small>
          </div>
        </div>
      </div>

      <div className="parallel-active-filters">
        {filters.documentId && (
          <button type="button" onClick={() => clearFilter('documentId')}>
            Documento: {filters.documentId.slice(0, 8)}… ✕
          </button>
        )}
        {filters.stage && (
          <button type="button" onClick={() => clearFilter('stage')}>
            Stage: {filters.stage} ✕
          </button>
        )}
        {selectedTopics.map((topicKey) => {
          const topicEntry = lineData.topicLookup.get(topicKey);
          const label = topicEntry?.label || topicKey;
          return (
            <button type="button" key={`topic-filter-${topicKey}`} onClick={() => toggleTopicSelection(topicKey)}>
              Tema: {label} ✕
            </button>
          );
        })}
        {selectedTopics.length > 0 && (
          <button type="button" onClick={clearTopicFilters}>
            Limpiar temas ✕
          </button>
        )}
      </div>

      {lineData.lines.length === 0 ? (
        <div className="parallel-empty">Sin datos suficientes para graficar.</div>
      ) : (
        <div className={`parallel-chart${fullHeight ? ' parallel-chart--expanded' : ''}`}>
          <div className="parallel-chart-scroll" ref={scrollRef}>
            <svg ref={svgRef} className="parallel-svg" />
          </div>
          <div ref={tooltipRef} className="parallel-tooltip" />
          
          <details className="parallel-help">
            <summary className="parallel-help-summary">💡 ¿Cómo interpretar esta visualización?</summary>
            <div className="parallel-help-content">
              <div className="parallel-help-section">
                <strong>1. Flujo de Izquierda a Derecha</strong>
                <p>Las líneas muestran el progreso de los documentos a través del pipeline. El color indica el estado (verde=completado, naranja=procesando, azul=pendiente, rojo=error).</p>
              </div>
              <div className="parallel-help-section">
                <strong>2. Bifurcación en "News Items"</strong>
                <p>Un documento se divide en N news_items detectados. Cada noticia genera su propia línea hacia Insights e Indexación.</p>
              </div>
              <div className="parallel-help-section">
                <strong>3. Granularidad Múltiple</strong>
                <p>
                  • <strong>Ejes 1-4</strong> (Upload, OCR, Chunking, Indexing): Nivel documento (1 línea = 1 PDF)
                  <br />
                  • <strong>Eje 5</strong> (News Items): Bifurcación (1 doc → N noticias)
                  <br />
                  • <strong>Ejes 6-7</strong> (Insights, Index Insights): Nivel news_item (1 línea = 1 noticia)
                </p>
              </div>
              <div className="parallel-help-section">
                <strong>4. Controles e Interactividad</strong>
                <p>
                  • <strong>Click en línea:</strong> Filtra por documento
                  <br />
                  • <strong>Click en banda de tema:</strong> Filtra por tema específico
                  <br />
                  • <strong>Agrupaciones:</strong> Agrupa por documento, día, semana o mes para ver tendencias
                  <br />
                  • <strong>Zoom vertical:</strong> Ajusta el espaciado para mejor visibilidad
                </p>
              </div>
              <div className="parallel-help-section">
                <strong>5. Cuellos de Botella</strong>
                <p>Muchas líneas acumuladas en un eje indican un posible cuello de botella. Revisa el panel "Análisis Pipeline" para más detalles.</p>
              </div>
            </div>
          </details>
          
          <div className="parallel-legend">
            <span><i className="legend-swatch done" /> Paso completado</span>
            <span><i className="legend-swatch progress" /> En progreso</span>
            <span><i className="legend-swatch pending" /> Pendiente / en cola</span>
            <span><i className="legend-swatch error" /> Error detectado</span>
          </div>
          {lineData.topics.length > 0 && (
            <div className="parallel-topic-legend">
              {lineData.topics.slice(0, MAX_TOPIC_LEGEND_ITEMS).map((topic) => (
                <button
                  key={topic.key}
                  type="button"
                  className={selectedTopicSet.has(topic.key) ? 'active' : ''}
                  onClick={() => toggleTopicSelection(topic.key)}
                >
                  <i style={{ backgroundColor: topic.color || '#38bdf8' }} />
                  {topic.label} ({topic.count})
                </button>
              ))}
              {lineData.topics.length > MAX_TOPIC_LEGEND_ITEMS && (
                <span className="parallel-topic-legend__more">
                  +{lineData.topics.length - MAX_TOPIC_LEGEND_ITEMS} más
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
