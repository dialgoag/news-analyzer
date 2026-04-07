/**
 * CollapsibleSection — REQ-014.2
 * Accordion-style collapsible wrapper for dashboard panels.
 * Updated with Heroicons + Accessibility + Priority variants
 */
import React, { useState } from 'react';
import { ChevronRightIcon, ChevronDownIcon } from '@heroicons/react/24/solid';
import './CollapsibleSection.css';

export function CollapsibleSection({ 
  title, 
  icon: IconComponent, 
  defaultCollapsed = false, 
  children, 
  badge,
  priority = 'normal' // 'high', 'normal', 'low'
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  const toggleCollapse = () => setCollapsed(!collapsed);

  return (
    <div className={`collapsible-section collapsible-section--${priority} ${collapsed ? 'collapsed' : 'expanded'}`}>
      <button
        className="collapsible-section-header"
        onClick={toggleCollapse}
        aria-expanded={!collapsed}
        aria-controls={`collapsible-content-${title.replace(/\s+/g, '-')}`}
      >
        {collapsed ? (
          <ChevronRightIcon className="collapse-icon" aria-hidden="true" />
        ) : (
          <ChevronDownIcon className="collapse-icon" aria-hidden="true" />
        )}
        
        {IconComponent && (
          <IconComponent className="section-icon" aria-hidden="true" />
        )}
        
        <span className="section-title">{title}</span>
        
        {badge && (
          <span className="section-badge" aria-label={`${badge} items`}>
            {badge}
          </span>
        )}
      </button>
      
      {!collapsed && (
        <div 
          className="collapsible-section-content"
          id={`collapsible-content-${title.replace(/\s+/g, '-')}`}
          role="region"
        >
          {children}
        </div>
      )}
    </div>
  );
}
