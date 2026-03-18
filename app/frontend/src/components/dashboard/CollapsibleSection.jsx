/**
 * CollapsibleSection — REQ-014.2
 * Accordion-style collapsible wrapper for dashboard panels.
 */
import React, { useState } from 'react';
import './CollapsibleSection.css';

export function CollapsibleSection({ title, icon = '📋', defaultCollapsed = false, children, badge }) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <div className={`collapsible-section ${collapsed ? 'collapsed' : ''}`}>
      <div
        className="collapsible-section-header"
        onClick={() => setCollapsed(!collapsed)}
      >
        <span className="collapse-icon">{collapsed ? '▶' : '▼'}</span>
        <span className="section-title">{icon} {title}</span>
        {badge && <span className="section-badge">{badge}</span>}
      </div>
      {!collapsed && <div className="collapsible-section-content">{children}</div>}
    </div>
  );
}
