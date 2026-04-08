# Dashboard Redesign Analysis - REQ-022

**Fecha**: 2026-04-08  
**Autor**: AI Assistant (Session 58)  
**Propósito**: Análisis detallado para rediseño del dashboard usando visual analytics framework

---

## 1. Analytical Context

### 1.1 Business Questions
**Primary**:
- ¿Cómo están progresando los documentos a través del pipeline?
- ¿Dónde hay cuellos de botella (stages con acumulación)?
- ¿Qué errores necesitan atención inmediata?
- ¿Cuál es la utilización actual vs capacidad de workers?

**Secondary**:
- ¿Qué documentos están estancados y por qué?
- ¿Cuál es la tendencia de procesamiento (improving/declining)?
- ¿Qué tipos de errores son más frecuentes?
- ¿Cuándo fue la última vez que se procesó con éxito?

### 1.2 Audience
- **Primary**: Operations team (monitoring en tiempo real)
- **Secondary**: Developers (debugging y troubleshooting)
- **Tertiary**: Admins (capacity planning)

### 1.3 Dashboard Type
**Operational Dashboard** (Monitoring + Diagnosis)
- Not strategic (Executive Dashboard)
- Not exploratory (Analytical Dashboard)
- Focus: Real-time status + actionable insights

### 1.4 Key Actions Supported
1. **Identify bottlenecks** → Adjust worker capacity
2. **Retry errors** → Batch retry by error type
3. **Monitor progress** → Estimate completion time
4. **Diagnose issues** → Drill down to specific documents/errors

---

## 2. Current Dashboard Analysis (What to Reuse)

### 2.1 Current Structure
```
[Header: Title + Refresh selector]
[KPIs Inline: 4 badges (docs, news, insights, errors)]
[Pipeline Status Table: Stages horizontal con status]
[Workers + Errors: Side-by-side mini widgets]
[Parallel Coordinates: Flow visualization compleja]
[Database Status: Auxiliary collapsible]
```

### 2.2 Reuse Analysis

#### ✅ KEEP & Enhance (40%)
| Component | Status | Enhancement Needed |
|-----------|--------|-------------------|
| `CollapsibleSection.jsx` | ✅ Perfect | None - reuse as-is |
| `useDashboardFilters.jsx` | ✅ Good | Add more filter types (date range, error type) |
| Auto-refresh logic | ✅ Perfect | None - interval selector works well |
| Error resilience (REQ-009) | ✅ Perfect | Maintain timeout handling |
| Heroicons | ✅ Good | Continue using |

#### 🔄 MODIFY (30%)
| Component | Current Issues | Modification Plan |
|-----------|---------------|-------------------|
| `PipelineDashboard.jsx` | Orchestration OK, layout needs reorg | Reorganize into 7-section pattern |
| `KPIsInline.jsx` | Missing trends (sparklines) | Add D3 sparklines for historical context |
| `ParallelPipelineCoordinates.jsx` | Very complex (1233 lines!) | **Decision point**: Simplify OR keep as advanced view |
| `ErrorAnalysisPanel.jsx` | No clear retry flow | Add sorted bar chart + retry actions |

#### ❌ REPLACE (30%)
| Component | Why Replace | Replacement |
|-----------|------------|-------------|
| `PipelineStatusTable.jsx` | Horizontal table not optimal | Sankey or simplified parallel coords |
| `WorkersErrorsInline.jsx` | Badges don't show capacity | Bullet charts (actual vs max) |
| Worker badges | No capacity visualization | Small multiples of bullet charts by worker type |

### 2.3 Data Fetching Analysis
**Current Pattern** (PipelineDashboard.jsx lines 53-120):
- ✅ Good: Uses `Promise.allSettled` for parallel requests
- ✅ Good: Handles failures gracefully
- ❌ Issue: State scattered across 5+ useState hooks
- ❌ Issue: No centralized data transformation

**Recommendation**: Create `useDashboardData` hook to centralize

---

## 3. Chart Selection by Analytical Task

### 3.1 Task: Document/News Progress (FLOW)

**Current**: `ParallelPipelineCoordinates.jsx` (1233 lines, very complex)
- Shows: Document → News bifurcation → Insights → Indexing
- Pros: Shows granular flow, topic filtering, grouping options
- Cons: Very complex, high cognitive load, 1233 lines of code
- Interaction: Brushing, topic selection, grouping (doc/day/week/month)

**Visual Analytics Assessment**:
- **Technique family**: Flow / Process
- **Options**: 
  1. **Sankey diagram**: Better for showing volumes and drops between stages
  2. **Simplified Parallel Coordinates**: Keep concept but reduce complexity
  3. **Funnel chart**: Simpler but loses granularity

**DECISION**:
- **Primary view**: Simplified Sankey (nodes = stages, links = documents flowing)
  - **Why**: Clearer volume visualization, easier to spot bottlenecks
  - **Loses**: Granular per-document tracking (acceptable for operational monitoring)
- **Secondary view** (Optional Advanced): Keep current Parallel Coordinates as collapsible "Advanced View"
  - **Why**: Power users may want granular analysis
  - **Implementation**: Move to separate component, load lazily

**Recommendation**: **Implement Sankey** as primary, **preserve Parallel Coords** as advanced option

### 3.2 Task: Worker Monitoring (COMPARISON + STATUS)

**Current**: Badges showing "X activos / Y idle / Z máx" + utilization bar

**Visual Analytics Assessment**:
- **Technique family**: Comparison (Actual vs Target)
- **Best chart**: **Bullet chart** (Excel at showing actual vs capacity)
- **Why bullet chart**:
  - Shows current value (active workers)
  - Shows max capacity clearly
  - Shows ranges (good/warning/critical)
  - Compact (multiple can fit in small multiples)
- **Why not gauge**: Takes more space, less precise reading
- **Why not simple bar**: Doesn't show target/threshold clearly

**Design**:
```
[OCR Workers]     ████████░░░░░░░░░░ 2/5 (40%)   [Good: 0-3 | Warning: 4 | Critical: 5]
[Indexing Workers] ████░░░░░░░░░░░░░ 1/4 (25%)   [Good: 0-2 | Warning: 3 | Critical: 4]
[Insights Workers] ██████████░░░░░░ 3/3 (100%)  [Good: 0-2 | Warning: 3 | Critical: 3+]
```

**Recommendation**: **Implement bullet charts** in small multiples (one per worker type)

### 3.3 Task: Error Tracking (COMPOSITION + PRIORITY)

**Current**: `ErrorAnalysisPanel` shows groups with count + message, retry button

**Visual Analytics Assessment**:
- **Technique family**: Composition (part-to-whole) + Ranking
- **Best charts**: 
  1. **Sorted horizontal bar chart** (errors by type, ranked by count)
  2. **Timeline** (temporal pattern - when did errors spike?)
- **Interaction**: Click bar → retry errors of that type

**Design**:
```
[Error Bar Chart - Sorted by count]
┌────────────────────────────────────────┐
│ Insufficient context (45) ███████████  │ [Retry All]
│ Rate limit 429 (12)       ████          │ [Retry All]
│ Connection timeout (8)    ██            │ [Retry All]
│ File not found (3)        █             │ [Retry All]
└────────────────────────────────────────┘

[Error Timeline - Last 24h]
Errors/hour
    ^
 20 │         ▄
 15 │       ▄█│
 10 │     ▄█││
  5 │  ▄▄█│││
  0 └─┴─┴─┴─┴→ Time
```

**Recommendation**: **Implement sorted bar chart** + **error timeline**

### 3.4 Task: KPI Monitoring (TREND + COMPARISON)

**Current**: `KPIsInline` shows current count only (no trend, no comparison)

**Visual Analytics Assessment**:
- **Technique family**: Trend + Comparison
- **Best addition**: **Sparklines** (small inline charts showing recent history)
- **Comparison indicator**: ↑↓ vs previous period (e.g., last hour)

**Design**:
```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ 📄 Documentos │ 📰 News      │ ✨ Insights   │ ❌ Errores   │
│     253      │    1,543     │    1,264     │     45       │
│  ▁▂▃▅▇ ↑ 12  │ ▃▄▅▅▆ ↑ 34   │ ▂▃▄▆▇ ↑ 89   │ ▇▆▄▃▂ ↓ 8    │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

**Recommendation**: **Add sparklines** + **comparison indicators** to existing KPIs

### 3.5 Task: Document Detail (DETAIL ON DEMAND)

**Current**: Not visible in main dashboard (requires navigation)

**Visual Analytics Assessment**:
- **Technique family**: Detail on demand
- **Best approach**: **Virtualized table** (collapsible, lazy-loaded)
- **Columns**: Filename, Status, Stage, News count, Insights count, Errors, Actions

**Recommendation**: **Add collapsible document table** with virtualization for performance

---

## 4. Dashboard Architecture (7-Section Operational Pattern)

### 4.1 Proposed Layout

```
┌─────────────────────────────────────────────────────────────┐
│ [1. HEADER]                                                 │
│    Title | Refresh selector | Global filters               │
│    [📊 Pipeline Dashboard • ⟳ 20s • Filter: Date range]    │
├─────────────────────────────────────────────────────────────┤
│ [2. KPI ROW - 4-6 cards with sparklines]                   │
│  ┌──────────┬──────────┬──────────┬──────────┐            │
│  │ Docs     │ News     │ Insights │ Errors   │            │
│  │  253 ↑12 │ 1543 ↑34 │ 1264 ↑89 │  45 ↓8   │            │
│  │ ▁▂▃▅▇    │ ▃▄▅▅▆    │ ▂▃▄▆▇    │ ▇▆▄▃▂    │            │
│  └──────────┴──────────┴──────────┴──────────┘            │
├─────────────────────────────────────────────────────────────┤
│ [3. MAIN ANALYSIS ROW]                                     │
│  ┌─────────────────────────────────┬───────────────────┐   │
│  │ Pipeline Flow (60%)             │ Workers (40%)     │   │
│  │                                 │                   │   │
│  │  [Sankey Diagram]               │ [Bullet Charts]   │   │
│  │   Upload ──→ OCR ──→ Chunking   │  OCR      ████░  │   │
│  │     │         │        │         │  Indexing ██░░░  │   │
│  │     ↓         ↓        ↓         │  Insights ██████ │   │
│  │   Indexing → Insights → Done    │                   │   │
│  │                                 │  [Capacity view]  │   │
│  └─────────────────────────────────┴───────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│ [4. DIAGNOSTIC ROW - Collapsible]                          │
│  ► Error Analysis                                          │
│    [Bar Chart: Errors by type + Timeline + Retry buttons] │
│                                                            │
│  ► Advanced Flow (Optional)                                │
│    [Parallel Coordinates - Lazy loaded]                   │
├─────────────────────────────────────────────────────────────┤
│ [5. DETAIL ROW - Collapsible]                              │
│  ► Document Table (virtualized)                            │
│    [Filename | Status | Stage | News | Insights | Actions]│
│                                                            │
│  ► Worker Activity Log                                     │
│    [Recent worker actions with timestamps]                 │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Information Hierarchy

**Priority 1 (Always visible)**:
- Header (with refresh control)
- KPI Row (current status + trends)

**Priority 2 (Visible by default, collapsible)**:
- Main Analysis Row (Pipeline flow + Workers)

**Priority 3 (Collapsed by default, expandable)**:
- Diagnostic Row (Errors + Advanced views)
- Detail Row (Tables + Logs)

---

## 5. Interaction Model

### 5.1 Primary Interactions

| Interaction | Trigger | Effect |
|-------------|---------|--------|
| **Global filter** | Date range selector in header | All views update to show filtered data |
| **Sankey node click** | Click on stage node (e.g., "OCR") | Highlights related errors, shows docs in that stage |
| **Sankey link hover** | Hover over flow link | Tooltip: "45 docs, 23 in progress, 2 errors" |
| **Bullet chart hover** | Hover on worker bar | Tooltip: "OCR workers: 2 active, 3 idle, 5 max" |
| **Error bar click** | Click error type bar | Shows affected documents, enables batch retry |
| **Retry button** | Click "Retry All" or "Retry Selected" | Triggers API call, shows progress toast |
| **Collapse section** | Click section header | Hides content, saves vertical space |

### 5.2 Brushing & Linking

| Selection | Linked Views Update |
|-----------|-------------------|
| Select stage in Sankey | Error panel filters to errors in that stage; Workers show utilization for that stage |
| Select error type in bar chart | Sankey highlights affected documents; Document table filters to errors |
| Select worker type | Sankey highlights tasks processed by that worker type |
| Select date range (global) | All views update (KPIs, Sankey, Errors, Workers) |

### 5.3 Details on Demand

| Element | Interaction | Detail Shown |
|---------|------------|--------------|
| KPI card | Hover | Historical data (sparkline expands), comparison details |
| Sankey link | Hover | Doc count, avg time in stage, success rate |
| Worker bullet chart | Hover | Active count, idle count, tasks completed, avg task duration |
| Error bar | Click | List of affected documents, retry options |
| Document row | Click | Expands to show full pipeline trace, news items, insights |

---

## 6. Technical Implementation Strategy

### 6.1 Component Hierarchy

```
PipelineDashboard/
├── layout/
│   ├── DashboardHeader.jsx         (title, refresh, filters)
│   ├── CollapsibleSection.jsx      (reuse existing)
│   └── DashboardContainer.jsx      (responsive grid)
├── kpis/
│   ├── KPICard.jsx                 (enhanced with sparkline)
│   ├── KPISparkline.jsx            (D3 mini chart)
│   └── KPIRow.jsx                  (container for 4-6 cards)
├── flow/
│   ├── PipelineSankeyChart.jsx     (NEW - primary flow viz)
│   ├── SankeyLegend.jsx            (states legend)
│   └── ParallelPipelineCoordinates.jsx (move to advanced, lazy load)
├── workers/
│   ├── WorkerStatusPanel.jsx       (container)
│   ├── WorkerBulletChart.jsx       (D3 bullet chart)
│   └── WorkerSmallMultiples.jsx    (grid of bullet charts)
├── errors/
│   ├── ErrorAnalysisPanel.jsx      (redesigned)
│   ├── ErrorBarChart.jsx           (D3 sorted bars)
│   ├── ErrorTimeline.jsx           (D3 sparkline)
│   └── ErrorRetryActions.jsx       (retry buttons + progress)
└── details/
    ├── DocumentTable.jsx           (virtualized table)
    └── WorkerActivityLog.jsx       (recent actions)
```

### 6.2 Data Services

```javascript
// services/dashboardDataService.js (extend existing)
- transformForSankey(data) -> { nodes, links }
- transformForSparklines(data, hours) -> { timestamps, values }
- normalizeDocumentMetrics(doc) -> enriched doc

// services/workerDataService.js (NEW)
- getWorkerCapacity() -> { ocr: {current, max}, indexing: {}, ... }
- transformForBulletCharts(workers) -> bullet chart data
- calculateUtilization(workers) -> percentage by type

// services/errorDataService.js (NEW)
- groupErrorsByType(errors) -> { type, count, docs[], canRetry }
- sortErrorsByPriority(groups) -> sorted array
- prepareErrorTimeline(errors, hours) -> timeline data
```

### 6.3 Hooks

```javascript
// hooks/useDashboardData.jsx (NEW - centralize fetching)
export function useDashboardData(API_URL, token, refreshInterval) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Centralized fetch logic
  // Returns: { summary, analysis, workers, errors, documents, loading, error, refetch }
}

// hooks/useD3Scale.js (NEW - memoized scales)
export function useD3Scale(type, domain, range) {
  return useMemo(() => {
    if (type === 'linear') return d3.scaleLinear().domain(domain).range(range);
    if (type === 'point') return d3.scalePoint(domain, range);
    // ... more scale types
  }, [type, domain, range]);
}

// hooks/useChartDimensions.js (NEW - responsive sizing)
export function useChartDimensions(containerRef) {
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  
  useEffect(() => {
    const observer = new ResizeObserver(entries => {
      // Update dimensions
    });
    // ...
  }, [containerRef]);
  
  return dimensions;
}

// hooks/useDashboardFilters.jsx (enhance existing)
- Add: dateRange filter
- Add: errorType filter
- Add: workerType filter
```

---

## 7. React + D3 Separation

### 7.1 Responsibilities Matrix

| Task | Owner | Pattern |
|------|-------|---------|
| Component structure | React | JSX with hooks |
| SVG DOM creation | React | `<svg><g><path>...` |
| Scale calculations | D3 | `d3.scaleLinear()` |
| Sankey layout | D3 | `d3.sankey()` |
| Path generation | D3 | `d3.line()`, `d3.linkHorizontal()` |
| Transitions | D3 | `transition().duration()` |
| Event handling | React | `onClick`, `onMouseEnter` |
| State management | React | `useState`, `useMemo` |
| Data fetching | React | `useEffect` + axios |
| Tooltip positioning | React | Controlled component |

### 7.2 Example Pattern (Bullet Chart)

```jsx
function WorkerBulletChart({ current, max, ranges }) {
  const svgRef = useRef();
  const { width, height } = useChartDimensions(svgRef);
  
  // D3: Create scale (memoized)
  const xScale = useMemo(() => 
    d3.scaleLinear().domain([0, max]).range([0, width - 40]),
    [max, width]
  );
  
  // React: Render SVG structure
  return (
    <svg ref={svgRef} width="100%" height={40}>
      {/* React renders rects, D3 calculates positions */}
      <rect x={0} y={10} width={xScale(ranges.good)} height={20} fill="#e0f2f1" />
      <rect x={xScale(ranges.good)} y={10} width={xScale(ranges.warning - ranges.good)} height={20} fill="#fff3e0" />
      <rect x={xScale(ranges.warning)} y={10} width={xScale(max - ranges.warning)} height={20} fill="#ffebee" />
      <rect x={0} y={10} width={xScale(current)} height={20} fill="#4caf50" />
      <line x1={xScale(max)} y1={5} x2={xScale(max)} y2={35} stroke="#000" strokeWidth={2} />
    </svg>
  );
}
```

**Key principle**: React creates the DOM structure, D3 provides the geometry calculations

---

## 8. Performance Considerations

### 8.1 Memoization Strategy

```javascript
// Memoize expensive transformations
const sankeyData = useMemo(() => 
  transformForSankey(data), 
  [data]
);

// Memoize D3 scales
const xScale = useMemo(() => 
  d3.scalePoint(stages, [0, width]), 
  [stages, width]
);

// Memoize filtered data
const filteredDocs = useMemo(() => 
  documents.filter(matchesFilters), 
  [documents, filters]
);
```

### 8.2 Lazy Loading

```javascript
// Lazy load heavy components
const ParallelCoordinates = React.lazy(() => 
  import('./ParallelPipelineCoordinates')
);

// Use in collapsible section
{showAdvanced && (
  <Suspense fallback={<div>Loading advanced view...</div>}>
    <ParallelCoordinates data={data} />
  </Suspense>
)}
```

### 8.3 Virtualization

```javascript
// Use react-window for document table
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={400}
  itemCount={documents.length}
  itemSize={50}
  width="100%"
>
  {DocumentRow}
</FixedSizeList>
```

### 8.4 Debouncing

```javascript
// Debounce filter updates
const debouncedUpdateFilter = useMemo(
  () => debounce(updateFilter, 300),
  [updateFilter]
);
```

---

## 9. Accessibility Checklist

### 9.1 Keyboard Navigation
- [ ] All interactive elements are focusable (tabIndex)
- [ ] Enter/Space activates buttons and links
- [ ] Escape closes tooltips and modals
- [ ] Arrow keys navigate within lists/tables
- [ ] Tab order follows visual flow

### 9.2 Semantics
- [ ] Sankey has role="img" + aria-label
- [ ] Bullet charts have descriptive aria-labels
- [ ] Tables have proper thead/tbody structure
- [ ] Buttons have clear aria-labels
- [ ] Status indicators have aria-live regions

### 9.3 Color Independence
- [ ] Error state: red color + ❌ icon
- [ ] Success state: green color + ✓ icon
- [ ] Warning state: orange color + ⚠️ icon
- [ ] Status text complements color coding
- [ ] Contrast ratios meet WCAG AA (4.5:1)

### 9.4 Screen Reader Support
- [ ] Chart data available in accessible table (sr-only)
- [ ] Dynamic updates announced with aria-live
- [ ] Links have meaningful text (not "click here")
- [ ] Images have alt text

---

## 10. Migration Strategy

### 10.1 Phase-by-Phase Implementation

**Phase 1: Foundation (Week 1)**
- [ ] Create new component structure (folders)
- [ ] Implement `useDashboardData` hook
- [ ] Create data service functions
- [ ] Set up new layout grid

**Phase 2: KPIs + Sparklines (Week 1-2)**
- [ ] Enhance `KPICard` with sparklines
- [ ] Implement comparison indicators
- [ ] Test with real data
- [ ] Deploy and validate

**Phase 3: Workers Bullet Charts (Week 2)**
- [ ] Create `WorkerBulletChart` component
- [ ] Implement small multiples layout
- [ ] Add capacity ranges
- [ ] Test interactions

**Phase 4: Error Analysis (Week 2-3)**
- [ ] Create `ErrorBarChart` component
- [ ] Implement `ErrorTimeline`
- [ ] Add retry action buttons
- [ ] Wire up retry API

**Phase 5: Pipeline Flow (Week 3-4)**
- [ ] Implement Sankey chart
- [ ] Add interactions (click, hover)
- [ ] Test with various data sizes
- [ ] Optimize performance

**Phase 6: Details + Advanced (Week 4)**
- [ ] Create virtualized document table
- [ ] Move Parallel Coords to advanced section
- [ ] Implement lazy loading
- [ ] Final accessibility audit

**Phase 7: Polish + Documentation (Week 5)**
- [ ] Responsive design testing
- [ ] Browser compatibility
- [ ] Performance optimization
- [ ] Update documentation

### 10.2 Rollback Plan

Keep old dashboard available during migration:
```javascript
// Add feature flag
const USE_NEW_DASHBOARD = process.env.VITE_NEW_DASHBOARD === 'true';

{USE_NEW_DASHBOARD ? (
  <PipelineDashboardV2 {...props} />
) : (
  <PipelineDashboard {...props} />
)}
```

---

## 11. Success Metrics

### 11.1 Functional Metrics
- [ ] All current functionality preserved
- [ ] Error retry flow clear and working
- [ ] Worker capacity visible at glance
- [ ] Bottlenecks identifiable in <5 seconds
- [ ] Real-time refresh working (<20s lag)

### 11.2 Performance Metrics
- [ ] Initial render <2s
- [ ] Filter update <500ms
- [ ] No unnecessary rerenders (React DevTools)
- [ ] Memoization working (check with Profiler)
- [ ] Virtualization working (1000+ docs)

### 11.3 UX Metrics
- [ ] Dashboard scannable in <10s
- [ ] Key insights visible without scroll
- [ ] Interactions intuitive (no training needed)
- [ ] Tooltips helpful and informative
- [ ] Errors actionable (clear next steps)

### 11.4 Code Quality Metrics
- [ ] React owns structure, D3 handles geometry
- [ ] No ownership conflicts
- [ ] Components <250 lines (except complex charts)
- [ ] Services testable (pure functions)
- [ ] Accessibility score >90 (Lighthouse)

---

## 12. Open Questions & Decisions Needed

### 12.1 Sankey vs Parallel Coordinates
**Question**: Should Sankey fully replace Parallel Coordinates, or keep both?

**Options**:
1. **Sankey only**: Simpler, easier to maintain, lower cognitive load
2. **Sankey primary + Parallel Coords advanced**: Caters to power users, higher complexity
3. **User preference toggle**: Let users choose, most flexible

**Recommendation**: Option 2 (Sankey primary + Parallel advanced)
- Rationale: Sankey better for operational monitoring (main use case)
- Parallel Coords still valuable for deep analysis (secondary use case)
- Lazy loading mitigates performance cost

**Decision needed from user**: ✓

### 12.2 Historical Data for Sparklines
**Question**: How much historical data to show in sparklines?

**Options**:
1. Last 1 hour (12 data points, 5min intervals)
2. Last 24 hours (24 data points, 1h intervals)
3. Configurable (user chooses)

**Recommendation**: Option 1 (Last 1 hour)
- Rationale: Operational dashboard needs recent trends, not long-term history
- 1 hour enough to spot recent changes
- Less data = faster rendering

**Decision**: Proceed with Option 1 unless user requests otherwise

### 12.3 Worker Capacity Ranges
**Question**: What defines "good", "warning", "critical" ranges for workers?

**Recommendation**:
- **Good**: 0-60% utilization (capacity available)
- **Warning**: 61-90% utilization (approaching capacity)
- **Critical**: 91-100% utilization (at capacity)

**Needs validation**: Check with backend limits (REQ-021 exposes limits via API)

---

## 13. Next Steps

1. ✅ **This analysis document** - DONE
2. **Get user approval** for:
   - Sankey vs Parallel Coords decision
   - Overall architecture
   - Chart selections
3. **Start Phase 2**: Data layer implementation
   - Create `useDashboardData` hook
   - Implement data service functions
   - Test with real API data
4. **Start Phase 3**: KPI + Sparklines
   - Enhance existing `KPICard`
   - Implement D3 sparklines
   - Wire up comparison indicators

---

**Document Status**: ✅ COMPLETE - Ready for review and approval  
**Next Action**: Present to user, get approval, proceed with Phase 2
