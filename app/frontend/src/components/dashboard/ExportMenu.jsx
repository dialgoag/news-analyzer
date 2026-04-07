/**
 * ExportMenu Component
 * Provides CSV/JSON/PNG export functionality for dashboard data
 */
import React, { useState, useRef } from 'react';
import { 
  ArrowDownTrayIcon, 
  DocumentTextIcon, 
  CodeBracketIcon,
  PhotoIcon
} from '@heroicons/react/24/outline';
import html2canvas from 'html2canvas';
import './ExportMenu.css';

export function ExportMenu({ data, filename = 'dashboard-data', targetElement = null }) {
  const [isOpen, setIsOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const menuRef = useRef(null);

  const exportToCSV = () => {
    if (!data || !Array.isArray(data) || data.length === 0) {
      alert('No hay datos para exportar');
      return;
    }

    const headers = Object.keys(data[0]);
    const csvRows = [
      headers.join(','),
      ...data.map(row => 
        headers.map(header => {
          const value = row[header];
          // Escape commas and quotes
          const escaped = String(value).replace(/"/g, '""');
          return `"${escaped}"`;
        }).join(',')
      )
    ];

    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    downloadBlob(blob, `${filename}.csv`);
    setIsOpen(false);
  };

  const exportToJSON = () => {
    if (!data) {
      alert('No hay datos para exportar');
      return;
    }

    const jsonContent = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonContent], { type: 'application/json' });
    downloadBlob(blob, `${filename}.json`);
    setIsOpen(false);
  };

  const exportToPNG = async () => {
    if (!targetElement) {
      alert('No se especificó un elemento para capturar');
      return;
    }

    setIsExporting(true);
    
    try {
      const canvas = await html2canvas(targetElement, {
        backgroundColor: '#0f172a',
        scale: 2,
        logging: false
      });

      canvas.toBlob((blob) => {
        if (blob) {
          downloadBlob(blob, `${filename}.png`);
        }
        setIsExporting(false);
        setIsOpen(false);
      });
    } catch (error) {
      console.error('Error al exportar PNG:', error);
      alert('Error al generar la imagen');
      setIsExporting(false);
    }
  };

  const downloadBlob = (blob, filename) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="export-menu" ref={menuRef}>
      <button
        className="export-menu__trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Abrir menú de exportación"
        aria-expanded={isOpen}
      >
        <ArrowDownTrayIcon className="export-icon" />
        Exportar
      </button>

      {isOpen && (
        <div className="export-menu__dropdown" role="menu">
          <button
            className="export-menu__item"
            onClick={exportToCSV}
            disabled={!data || isExporting}
            role="menuitem"
          >
            <DocumentTextIcon className="item-icon" />
            <span>
              <strong>CSV</strong>
              <small>Tabla en formato CSV</small>
            </span>
          </button>

          <button
            className="export-menu__item"
            onClick={exportToJSON}
            disabled={!data || isExporting}
            role="menuitem"
          >
            <CodeBracketIcon className="item-icon" />
            <span>
              <strong>JSON</strong>
              <small>Datos estructurados</small>
            </span>
          </button>

          <button
            className="export-menu__item"
            onClick={exportToPNG}
            disabled={!targetElement || isExporting}
            role="menuitem"
          >
            <PhotoIcon className="item-icon" />
            <span>
              <strong>PNG</strong>
              <small>{isExporting ? 'Generando...' : 'Captura de pantalla'}</small>
            </span>
          </button>
        </div>
      )}
    </div>
  );
}

export default ExportMenu;
