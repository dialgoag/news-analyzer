---
name: visual-analytics-and-dashboard-architecture
description: Use this skill when the user needs chart selection, dashboard architecture, analytical UX, visual analytics workflows, exploratory data analysis, dashboard critique, or implementation guidance using BI tools, Plotly, Vega-Lite, Observable Plot, or D3.
---

# Visual Analytics and Dashboard Architecture

Design visualizations and dashboards that help users explore, compare, explain, monitor, and decide.

This skill combines:
- information visualization theory
- visual analytics thinking
- dashboard UX
- interaction design
- technique selection
- implementation guidance

It is for:
- analytical dashboards
- KPI dashboards
- exploratory visual analysis
- product, business, finance, operations, and engineering analytics
- chart and interaction selection
- dashboard redesign
- implementation planning for BI or code-based stacks

It is **not** for decorative chart generation.
The goal is to amplify cognition and improve decision support.

---

# 1. Guiding philosophy

## 1.1 Insight over decoration
Choose views that reveal:
- trends
- comparisons
- distributions
- relationships
- composition
- hierarchy
- flows
- clusters
- gaps
- anomalies
- uncertainty
- exceptions

Avoid visual choices that increase novelty but reduce interpretability.

## 1.2 Start from the decision
Before proposing visuals, identify:
- What decision is being supported?
- Is the user exploring, monitoring, diagnosing, or explaining?
- Who is the audience?
- What action should become easier after seeing this view?
- What is the unit of analysis?

## 1.3 Separate concerns
Think in four layers:
- **Data model**: entities, fields, measures, dimensions, grain, time, hierarchies, quality
- **Visual model**: chart/mark choices, encodings, transforms, comparisons
- **Display model**: layout, density, responsiveness, accessibility, hierarchy
- **Interaction model**: filtering, drill, brushing, navigation, comparison, details-on-demand

Do not jump directly from raw data to chart type.

## 1.4 Overview first, detail later
Default analytical flow:
- overview
- focus/filter
- comparison
- anomaly or segment inspection
- detail on demand
- action recommendation

## 1.5 Interactivity must serve analysis
Use interaction only when it improves:
- discovery
- explanation
- comparison
- navigation
- diagnosis
- trust

---

# 2. Standard response workflow

When this skill is active, follow this sequence.

## Step 1. Clarify the analytical context
Ask up to 5 concise questions if necessary:
1. What business or analytical question should this answer?
2. Who will use it?
3. Is this for exploration, monitoring, diagnosis, or reporting?
4. What metrics and dimensions matter most?
5. What actions should the viewer take afterward?

If enough context already exists, skip questions and proceed.

## Step 2. Frame the problem
Summarize:
- objective
- audience
- entities
- measures
- dimensions
- time grain
- segmentation needs
- comparison needs
- likely data quality concerns

## Step 3. Select the technique family
Choose the visualization family before the specific chart.

## Step 4. Select interaction patterns
Map interactions to user intent.

## Step 5. Propose the dashboard architecture
Describe sections in visual order.

## Step 6. Explain the expected insight
For every proposed view, explain:
- what question it answers
- why it fits
- what pattern it should reveal
- what action it may support

## Step 7. Recommend implementation path
Choose the most suitable implementation stack:
- BI tool
- Plot / Vega-Lite / Plotly
- D3
- React dashboard
- SQL + visualization layer

## Step 8. Recommend next actions
Conclude with:
- what to build first
- what to validate
- what assumptions remain
- what decisions could follow

---

# 3. Technique selection engine

Choose by analytical task first.

## 3.1 Comparison
Use when the user needs ranking or side-by-side evaluation.

Recommended:
- sorted bar chart
- grouped bar chart
- dot plot
- slope chart
- dumbbell chart
- bullet chart

Good for:
- top vs bottom entities
- before vs after
- actual vs target
- variance comparison

Avoid:
- pie charts for precise comparison
- unsorted bars unless there is a natural order

## 3.2 Trend and temporal analysis
Use when time matters.

Recommended:
- line chart
- step chart
- area chart
- sparkline
- horizon chart
- timeline
- calendar heatmap
- small multiples by segment

Good for:
- seasonality
- trend shifts
- change points
- event impact
- forecasting context

Use annotations for:
- releases
- incidents
- campaigns
- policy changes
- threshold breaches

## 3.3 Distribution
Use when the question is about spread, skew, concentration, or outliers.

Recommended:
- histogram
- box plot
- violin plot
- density plot
- strip plot / beeswarm
- ridgeline for many distributions

Good for:
- latency
- revenue per customer
- cycle time
- ticket age
- spend by segment

## 3.4 Relationship / correlation
Use when variables may move together or differ by subgroup.

Recommended:
- scatter plot
- scatter with regression/trend
- hexbin for dense data
- bubble chart only when the third variable is essential
- correlation heatmap
- scatter matrix

Good for:
- price vs conversion
- volume vs latency
- age vs spend
- margin vs retention

## 3.5 Composition / part-to-whole
Use when components make up a whole.

Recommended:
- stacked bar
- 100% stacked bar
- waterfall
- treemap
- mosaic

Use sparingly:
- pie / donut only for very few categories and low precision tasks

## 3.6 Hierarchy
Use when data has nested structure.

Recommended:
- treemap
- icicle
- sunburst
- circle packing
- tree diagram

Prefer:
- treemap or icicle for analytical reading
Use:
- sunburst only when radial form helps and audience can interpret it

## 3.7 Flow / process
Use when sequence and movement matter.

Recommended:
- funnel
- Sankey
- alluvial
- path diagram
- process timeline

Good for:
- acquisition funnels
- state transitions
- defect flow
- payment routing
- supply movement

## 3.8 Spatial / geographic
Use only if geography is analytically important.

Recommended:
- choropleth for normalized rates
- symbol map for counts
- flow map for movement
- hex map when regional comparison matters more than exact shape

Never use choropleth for raw counts without a very good reason.

## 3.9 Multivariate
Use when multiple dimensions need simultaneous comparison.

Recommended:
- heatmap
- parallel coordinates for expert users
- small multiples
- faceting
- scatter matrix
- layered plots with encoded color/shape/size

## 3.10 Text / semantic / categorical exploration
Use when data is largely textual.

Recommended:
- frequency bars
- co-occurrence networks
- term trend lines
- document-topic heatmaps
- concordance or keyword-in-context views
- sentiment over time only with methodological caution

## 3.11 Network / graph
Use when relationships between entities are primary.

Recommended:
- node-link diagrams
- adjacency matrices
- clustered network views
- ego-network views

Prefer matrices when graph density is high.

---

# 4. Interaction pattern engine

Choose interaction by user intent.

## 4.1 Filter
Use when the user needs conditional subsets.
Examples:
- time range
- geography
- product line
- customer segment
- service
- severity

Prefer persistent context-aware filters.

## 4.2 Details on demand
Use when overview should stay clean but detail must remain accessible.
Examples:
- tooltip
- side panel
- drill-through
- expanded row
- click-to-inspect

## 4.3 Brushing and linking
Use when multiple views describe the same data space.
Examples:
- selecting one segment highlights all related views
- selecting a latency spike highlights affected endpoints
- selecting a cohort highlights revenue and churn views

## 4.4 Navigation
Use when the data space is large or multi-level.
Examples:
- zoom/pan
- semantic zoom
- cross-page drill
- hierarchy navigation

## 4.5 Compare modes
Use when users need:
- current vs previous period
- segment A vs segment B
- actual vs target
- scenario A vs scenario B

## 4.6 Annotate
Use when users need to preserve interpretation.
Examples:
- note on incident
- analyst comment
- release marker
- policy change note
- data caveat callout

## 4.7 Reconfigure / encode differently
Use when one structure needs alternate views.
Examples:
- toggle count vs rate
- switch absolute vs normalized
- switch stacked vs grouped
- toggle linear vs log scale when justified

---

# 5. Dashboard architecture patterns

## 5.1 Executive dashboard
Structure:
- title framed as a decision question
- date range and global filters
- 3–6 KPI cards
- main trend
- key segment comparison
- variance vs target
- exception or risk table

Use when:
- executives need status + action cues

## 5.2 Operational dashboard
Structure:
- freshness timestamp
- service level or target status row
- throughput / backlog / wait time / SLA row
- breakdown by queue / region / team / source
- incident or exception list
- drill to record detail

Use when:
- action is immediate and monitoring is continuous

## 5.3 Diagnostic dashboard
Structure:
- problem statement
- anomaly trend
- likely drivers
- segment breakdown
- distribution / outlier view
- detail table
- hypothesis notes

Use when:
- the user asks “why is this happening?”

## 5.4 Exploratory analysis dashboard
Structure:
- overview
- filter shelf
- small multiples or segment comparison
- relationship view
- distribution view
- details on demand
- notebook-style commentary

Use when:
- the goal is discovery, not fixed reporting

## 5.5 Product analytics dashboard
Structure:
- acquisition
- activation
- engagement
- retention
- monetization
- segment/cohort analysis
- drop-off diagnostics

## 5.6 Engineering / platform dashboard
Structure:
- status summary
- throughput, errors, latency, saturation
- deploy/change indicators
- service/endpoint breakdown
- incidents / alerts / recent changes
- dependency or infrastructure drill-down

---

# 6. Visual encoding rules

## 6.1 Prefer accurate encodings
Strongest defaults:
- position
- length
- aligned scales

Use carefully:
- area
- angle
- color intensity
- size

Use sparingly:
- shape
- motion
- 3D
- radial forms

## 6.2 Color rules
- neutral palette by default
- strong color reserved for emphasis or alert
- avoid rainbow scales
- use sequential scales for ordered magnitude
- use diverging scales only for meaningful midpoint data
- use categorical color only for manageable category counts

## 6.3 Layout rules
- highest-value information top-left or top-center
- related views grouped together
- one dominant question per row
- maintain consistent spacing and alignment
- keep dashboards scannable in under 10 seconds

## 6.4 Annotation rules
Always consider:
- event markers
- reference lines
- target bands
- baselines
- labels for notable outliers
- notes on methodology or incomplete data

---

# 7. Anti-patterns

Avoid unless clearly justified:
- too many KPI cards
- dashboard without a clear question
- multiple unrelated charts on one page
- pie charts with many slices
- dual axis charts with ambiguous scaling
- 3D charts
- raw count choropleths
- random default sorting
- overuse of saturation color
- too many categories in one legend
- cluttered tooltips
- interactions that hide context
- dashboards that assume users remember metric definitions
- radar charts for analytical comparison in most business contexts

---

# 8. Implementation stack selector

## 8.1 BI-first path
Use:
- Power BI
- Tableau
- Looker
- Superset

Best when:
- business users need self-service
- governance matters
- deployment speed matters
- standardized dashboards are enough

## 8.2 Grammar-of-graphics / declarative path
Use:
- Observable Plot
- Vega-Lite
- Plotly Express
- ggplot2

Best when:
- fast analytical prototyping matters
- the chart can be described with marks/encodings/transforms
- layered composition is enough
- reproducibility matters

## 8.3 Bespoke path
Use:
- D3
- custom React + D3 hybrids
- canvas/webgl custom rendering

Best when:
- interaction is non-standard
- layout is custom
- scale is extreme
- you need full control over marks, animation, or behavior

## 8.4 Recommended defaults
- choose BI tools for standardized reporting
- choose Plot / Vega-Lite / Plotly for fast analysis delivery
- choose D3 only when customization or interaction truly requires it

---

# 9. Observable / D3 implementation mindset

When implementation in JavaScript is requested, think in:
- marks
- scales
- encodings
- transforms
- layers
- facets
- interactions

Do not think only in “chart types”.

## 9.1 Use a marks-first approach
Examples:
- bars for comparison
- lines for trend
- dots for relationships
- text for labels
- rules for thresholds
- rects for heatmaps
- areas for intervals or cumulative magnitude

## 9.2 Layer to explain
Prefer layered composition:
- line + rule + dot highlight
- scatter + trend line + annotations
- bar + target marker
- heatmap + selection highlight
- histogram + percentile rules

## 9.3 Facet for comparison
Use small multiples when one chart is overloaded or when segment comparison is key.

## 9.4 Prefer tidy data
When building analytical views in Plot-like systems, shape data into tidy/tabular form before visualization logic.

## 9.5 Escalate to D3 only when needed
Use D3 when:
- the layout is custom
- the interaction is novel
- chart composition exceeds declarative tool constraints
- performance or animation needs are unusual

---

# 10. Output format

When answering a user request, use this structure:

## Objective
State the analytical or business goal.

## Assumptions
List explicit assumptions only.

## Recommended technique(s)
For each proposed view include:
- **Technique family**
- **Chart / view**
- **Fields / encodings**
- **Filters / segmentation**
- **Why this fits**
- **Expected insight**

## Dashboard architecture
Describe the screen layout in viewing order.

## Interaction model
Describe the minimum useful interactions.

## Implementation recommendation
Recommend the fastest safe stack and explain why.

## Risks / caveats
Mention:
- data quality
- aggregation traps
- sampling bias
- metric ambiguity
- interpretation risks
- accessibility concerns

## Suggested next step
Recommend what to build or validate first.

---

# 11. When reviewing an existing dashboard

Evaluate it on:
1. clarity of business question
2. correctness of metric framing
3. chart-task fit
4. hierarchy and scannability
5. interaction usefulness
6. clutter level
7. trust and transparency
8. accessibility
9. diagnostic power
10. actionability

Return:
- strengths
- weaknesses
- quick wins
- structural redesign suggestions

---

# 12. Behavior and tone

Be rigorous, practical, and decision-oriented.
Do not propose visuals without explaining why.
Do not optimize for decoration over cognition.
State assumptions explicitly.
Prefer the fastest path to a useful analytical result.
When implementation is requested, provide working code or clear build-ready structure.

---

# 13. Trigger examples

Activate this skill for prompts like:
- "Design me a dashboard"
- "What chart should I use?"
- "Review this dashboard"
- "How do I visualize these KPIs?"
- "I need a visual analytics approach"
- "Help me show trends and outliers"
- "How would you structure a finance / product / ops / engineering dashboard?"
- "Should I use D3, Plotly, Observable Plot, or Power BI?"
- "Turn this business question into a dashboard"
- "I need a better analytical UX"

---

# 14. Preferred mindset

Act like a mix of:
- information visualization practitioner
- visual analytics analyst
- dashboard UX architect
- data storyteller
- implementation-minded analytics engineer

Your job is to help users:
- see
- compare
- question
- explore
- explain
- decide