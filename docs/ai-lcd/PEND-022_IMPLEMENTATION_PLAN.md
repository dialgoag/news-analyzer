# Plan de Implementación: PEND-022 - Dashboard Visual Improvements

**Fecha**: 2026-04-07  
**Estimación**: 6-8 horas  
**Prioridad**: ALTA

---

## 📋 Cambios en Documentación

### Antes de Código
- [x] Actualizar `PENDING_BACKLOG.md` con PEND-022
- [x] Crear `DASHBOARD_VISUAL_IMPROVEMENTS_PLAN.md`
- [ ] Registrar en `CONSOLIDATED_STATUS.md` cuando complete

### Durante Implementación
- [ ] Actualizar `SESSION_LOG.md` con decisiones técnicas

---

## 🎨 Fase 1: Design Tokens Base (2h)

### 1.1 Crear `design-tokens.css`
**Ubicación**: `app/frontend/src/styles/design-tokens.css`

**Contenido**:
```css
/* Importar Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');

:root {
  /* Tipografía */
  --font-heading: 'Fira Code', monospace;
  --font-body: 'Fira Sans', sans-serif;
  
  /* Tamaños de texto */
  --text-xl: 1.875rem;  /* 30px */
  --text-lg: 1.125rem;  /* 18px */
  --text-md: 0.875rem;  /* 14px */
  --text-sm: 0.875rem;  /* 14px */
  --text-xs: 0.75rem;   /* 12px */
  
  /* Espaciado (sistema 4px) */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  
  /* Estados de datos */
  --color-active: #4caf50;
  --color-pending: #ff9800;
  --color-completed: #2196f3;
  --color-error: #f44336;
  --color-warning: #ff5722;
  --color-info: #4dd0e1;
  
  /* Elementos de interfaz */
  --bg-base: #0f172a;
  --bg-panel: #1e1e2e;
  --border-color: #334155;
  --text-primary: #f1f5f9;
  --text-secondary: #cbd5e1;
  --text-disabled: #64748b;
  
  /* Transiciones */
  --transition-fast: 150ms ease;
  --transition-normal: 200ms ease;
  --transition-slow: 300ms ease;
}
```

**Verificación**:
- [ ] Archivo creado
- [ ] Variables CSS definidas
- [ ] Google Fonts importados

---

### 1.2 Importar en `main.jsx`
**Ubicación**: `app/frontend/src/main.jsx`

**Cambio**:
```jsx
import './styles/design-tokens.css'; // NUEVO
import './index.css';
```

**Verificación**:
- [ ] Import agregado
- [ ] Fonts cargan en DevTools

---

### 1.3 Actualizar `PipelineDashboard.css`
**Ubicación**: `app/frontend/src/components/PipelineDashboard.css`

**Cambios**:
- Reemplazar colores hardcoded por variables CSS
- Aplicar sistema de espaciado
- Usar `font-family: var(--font-body)`

**Verificación**:
- [ ] Variables CSS usadas
- [ ] No hay colores hardcoded
- [ ] Espaciado consistente

---

## 🧩 Fase 2: Componentes Core (2-3h)

### 2.1 Crear `KPICard.jsx`
**Ubicación**: `app/frontend/src/components/dashboard/KPICard.jsx`

**Componente**:
```jsx
import React from 'react';
import './KPICard.css';

export function KPICard({ icon, label, value, total, percentage, status, trend }) {
  return (
    <div className={`kpi-card kpi-card--${status}`}>
      <div className="kpi-card__icon">{icon}</div>
      <span className="kpi-card__label">{label}</span>
      <div className="kpi-card__value">
        {value}{total && `/${total}`}
      </div>
      {percentage !== undefined && (
        <span className="kpi-card__percentage">{Math.round(percentage)}%</span>
      )}
      {trend && <span className="kpi-card__trend">{trend}</span>}
    </div>
  );
}
```

**CSS**:
```css
.kpi-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: var(--space-3);
  transition: var(--transition-normal);
  cursor: pointer;
}

.kpi-card:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: var(--color-info);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(77, 208, 225, 0.15);
}

.kpi-card__icon {
  width: 24px;
  height: 24px;
  margin-bottom: var(--space-2);
  color: var(--color-info);
}

.kpi-card__label {
  font-family: var(--font-body);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: block;
}

.kpi-card__value {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.kpi-card__percentage {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
```

**Verificación**:
- [ ] Componente creado
- [ ] CSS aplicado
- [ ] Hover funciona
- [ ] Fira Code en números

---

### 2.2 Instalar Heroicons
**Comando**:
```bash
cd app/frontend && npm install @heroicons/react
```

**Verificación**:
- [ ] Paquete instalado
- [ ] package.json actualizado

---

### 2.3 Refactorizar `PipelineSummaryCard.jsx`
**Ubicación**: `app/frontend/src/components/dashboard/PipelineSummaryCard.jsx`

**Cambios**:
- Usar `KPICard` component
- Importar Heroicons (DocumentTextIcon, BoltIcon, ClockIcon)
- Crear progress bar stacked con legend

**Verificación**:
- [ ] KPICard integrado
- [ ] Iconos SVG (no emojis)
- [ ] Progress bar con estados (completed/processing/pending)
- [ ] Legend visible

---

### 2.4 Mejorar `CollapsibleSection.jsx`
**Ubicación**: `app/frontend/src/components/dashboard/CollapsibleSection.jsx`

**Cambios**:
- Agregar prop `priority` ('high' | 'medium' | 'low')
- Agregar prop `badge` (número opcional)
- Importar ChevronRightIcon de Heroicons
- Aplicar estilos por prioridad

**CSS**:
```css
.collapsible-section--high {
  border: 2px solid var(--color-error);
  background: rgba(244, 67, 54, 0.05);
}

.collapsible-section--medium {
  border: 1px solid var(--border-color);
}

.collapsible-section--low {
  border: 1px solid rgba(255, 255, 255, 0.05);
  opacity: 0.8;
}
```

**Verificación**:
- [ ] Prioridades visuales funcionan
- [ ] Chevron animado (rotate 90deg)
- [ ] Badge visible si existe
- [ ] Focus states para keyboard

---

## 📊 Fase 3: Visualizaciones (2h)

### 3.1 Mejorar `WorkerLoadCard.jsx`
**Ubicación**: `app/frontend/src/components/dashboard/WorkerLoadCard.jsx`

**Cambios**:
- Optimizar D3 chart con color scale por estado
- Agregar tooltips informativos
- Usar transiciones smooth (300ms)

**Verificación**:
- [ ] Color coding por estado
- [ ] Tooltips con worker_id, status, load, docs
- [ ] Transiciones smooth

---

### 3.2 Optimizar `ErrorAnalysisPanel.jsx`
**Ubicación**: `app/frontend/src/components/dashboard/ErrorAnalysisPanel.jsx`

**Cambios**:
- Crear error cards con severity bar
- Agregar iconos (ExclamationTriangleIcon)
- Color coding por tipo de error

**Verificación**:
- [ ] Error cards visibles
- [ ] Severity bar proporcional
- [ ] Acciones (ver docs, reintentar) funcionales

---

## ✨ Fase 4: Features + Polish (1-2h)

### 4.1 Crear `ExportMenu.jsx`
**Ubicación**: `app/frontend/src/components/dashboard/ExportMenu.jsx`

**Funcionalidad**:
- Export CSV (métricas)
- Export JSON (datos completos)
- Export PNG (screenshot del dashboard)

**Verificación**:
- [ ] Dropdown menu funcional
- [ ] CSV export descarga
- [ ] JSON export descarga
- [ ] PNG export (html2canvas)

---

### 4.2 Responsive Testing
**Breakpoints**:
- Mobile: 375px
- Tablet: 768px
- Desktop: 1024px, 1440px

**Verificación**:
- [ ] Layouts adaptan en cada breakpoint
- [ ] KPI Cards stack en mobile
- [ ] Tablas scroll horizontalmente
- [ ] Texto legible en todos los tamaños

---

### 4.3 Accesibilidad
**Checklist**:
- [ ] Contraste mínimo 4.5:1 (WCAG AA)
- [ ] Focus states visibles (outline 2px)
- [ ] Keyboard navigation funciona
- [ ] ARIA labels en iconos
- [ ] prefers-reduced-motion respetado

---

### 4.4 Testing Final
**Comandos**:
```bash
# Build frontend
cd app/frontend && npm run build

# Rebuild containers
cd app && docker compose build frontend --no-cache

# Deploy
docker compose up -d frontend

# Verificar logs
docker compose logs frontend | head -50
```

**Verificación Manual**:
- [ ] Dashboard carga sin errores
- [ ] Fonts cargan (Fira Code/Sans)
- [ ] Colores consistentes
- [ ] Hover states funcionan
- [ ] Export menu funcional
- [ ] Responsive en mobile/tablet

---

## 📚 Documentación Post-Implementación

### Actualizar `CONSOLIDATED_STATUS.md`
```markdown
### Fix #XXX: Dashboard Visual Improvements (PEND-022) ✅
**Fecha**: 2026-04-07
**Ubicación**: 
- `app/frontend/src/styles/design-tokens.css` (nuevo)
- `app/frontend/src/components/dashboard/KPICard.jsx` (nuevo)
- `app/frontend/src/components/dashboard/ExportMenu.jsx` (nuevo)
- `app/frontend/src/components/PipelineSummaryCard.jsx` (refactorizado)
- `app/frontend/src/components/dashboard/CollapsibleSection.jsx` (mejorado)

**Problema**: Dashboard sin design system consistente, emojis como iconos, sin accesibilidad WCAG AA

**Solución**: 
- CSS variables consistentes (Visual Analytics Guidelines)
- Fira Code + Fira Sans
- Heroicons SVG (reemplazado emojis)
- KPICard component reutilizable
- Export menu (CSV/JSON/PNG)
- Accesibilidad WCAG AA

**Impacto**: 
- Dashboard profesional
- Contraste 4.5:1 mínimo
- Keyboard navigation completa
- Export functions operativas

**⚠️ NO rompe**: 
- Pipeline monitoreo ✅
- Auto-refresh ✅
- Collapsible sections ✅
- D3 visualizations ✅

**Verificación**:
- [x] Design tokens aplicados
- [x] Heroicons instalados
- [x] KPICard funcional
- [x] Export menu operativo
- [x] Accesibilidad WCAG AA
- [x] Responsive mobile/tablet
```

### Actualizar `SESSION_LOG.md`
```markdown
## 2026-04-07

### Cambio: Dashboard Visual Improvements (PEND-022)
- **Decisión**: Aplicar design system profesional antes de nuevas features
- **Alternativas consideradas**: 
  1. Solo arreglar colores → Rechazado: no resuelve inconsistencias
  2. Implementar REQ-014 primero → Rechazado: falta base sólida
  3. Design system completo → **Elegido**: crea base para futuras mejoras
- **Impacto en roadmap**: REQ-014 se beneficiará de esta base
- **Riesgo**: Cambios visuales requieren testing exhaustivo (mitigado con plan por fases)
```

---

## ✅ Checklist Final

### Pre-Delivery
- [ ] Todos los archivos creados/modificados
- [ ] npm build sin errores
- [ ] Docker build exitoso
- [ ] Testing manual completado
- [ ] Documentación actualizada

### Post-Deploy
- [ ] Dashboard carga correctamente
- [ ] Performance <2s render inicial
- [ ] No hay errores en consola
- [ ] Accesibilidad verificada
- [ ] Responsive verificado

---

**Última actualización**: 2026-04-07  
**Estado**: LISTO PARA IMPLEMENTAR
