import React, { useState, useMemo } from 'react';
import {
  Boxes,
  Database,
  Workflow,
  Code2,
  Key,
  ShieldCheck,
  Search,
  ArrowRight,
  Layers,
  Sparkles,
  Copy,
  Check,
  Maximize2,
  Minimize2,
  Table,
  Link2,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { MermaidViewer } from '../common/MermaidViewer';
import { ErDiagramCanvas } from './ErDiagramCanvas';

export type ModelViewMode = 'erd-canvas' | 'logical' | 'physical' | 'graph' | 'mermaid';

interface AttributeDef {
  name: string;
  columnName?: string;
  javaType?: string;
  sqlType?: string;
  type?: string;
  length?: number;
  nullable?: boolean;
  isPrimaryKey?: boolean;
  primaryKey?: boolean;
  isUnique?: boolean;
  hasIndex?: boolean;
  defaultValue?: string;
  validationRules?: string[];
}

interface RelationshipDef {
  sourceEntity: string;
  targetEntity: string;
  relationshipType: 'ONE_TO_MANY' | 'MANY_TO_ONE' | 'ONE_TO_ONE' | 'MANY_TO_MANY' | string;
  joinColumnName?: string;
  inversePropertyName?: string;
  cascadeType?: string;
  fetchType?: string;
  description?: string;
  joinTableName?: string;
}

interface EntityDef {
  name: string;
  tableName?: string;
  packageName?: string;
  description?: string;
  attributes?: AttributeDef[];
  fields?: AttributeDef[];
  relationships?: RelationshipDef[];
  hasAuditFields?: boolean;
}

interface VisualDataModelViewerProps {
  entities: EntityDef[];
  serviceName?: string;
  packageName?: string;
  mermaidChart?: string;
  activeEntityName?: string | null;
  onSelectEntity?: (name: string) => void;
  className?: string;
}

export const VisualDataModelViewer: React.FC<VisualDataModelViewerProps> = ({
  entities = [],
  serviceName = 'service',
  packageName = 'com.corp.service',
  mermaidChart = '',
  activeEntityName = null,
  onSelectEntity,
  className = '',
}) => {
  const [viewMode, setViewMode] = useState<ModelViewMode>('erd-canvas');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedEntityName, setSelectedEntityName] = useState<string | null>(
    activeEntityName || (entities.length > 0 ? entities[0].name : null)
  );
  const [isExpandedAll, setIsExpandedAll] = useState(true);
  const [collapsedCards, setCollapsedCards] = useState<Record<string, boolean>>({});

  // Synchronize when external active entity changes
  React.useEffect(() => {
    if (activeEntityName) {
      setSelectedEntityName(activeEntityName);
    }
  }, [activeEntityName]);

  const handleCardClick = (name: string) => {
    setSelectedEntityName(name);
    if (onSelectEntity) {
      onSelectEntity(name);
    }
  };

  const toggleCollapse = (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCollapsedCards((prev) => ({
      ...prev,
      [name]: !prev[name],
    }));
  };

  // Filter entities by search term
  const filteredEntities = useMemo(() => {
    if (!searchTerm.trim()) return entities;
    const term = searchTerm.toLowerCase();
    return entities.filter((e) => {
      const nameMatch = e.name.toLowerCase().includes(term);
      const tableMatch = (e.tableName || '').toLowerCase().includes(term);
      const attrs = e.attributes || e.fields || [];
      const attrMatch = attrs.some(
        (a) =>
          a.name.toLowerCase().includes(term) ||
          (a.columnName || '').toLowerCase().includes(term) ||
          (a.javaType || a.type || '').toLowerCase().includes(term) ||
          (a.sqlType || '').toLowerCase().includes(term)
      );
      return nameMatch || tableMatch || attrMatch;
    });
  }, [entities, searchTerm]);

  // Total metrics
  const totalAttributes = useMemo(() => {
    return entities.reduce((acc, e) => acc + (e.attributes || e.fields || []).length, 0);
  }, [entities]);

  const totalRelationships = useMemo(() => {
    return entities.reduce((acc, e) => acc + (e.relationships || []).length, 0);
  }, [entities]);

  // Color helper for Java types
  const getJavaTypeBadge = (typeStr: string) => {
    const t = (typeStr || 'String').toLowerCase();
    if (t.includes('long') || t.includes('integer') || t.includes('int')) {
      return 'bg-blue-100 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-900';
    }
    if (t.includes('decimal') || t.includes('double') || t.includes('float')) {
      return 'bg-purple-100 dark:bg-purple-950/80 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-900';
    }
    if (t.includes('instant') || t.includes('date') || t.includes('time')) {
      return 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900';
    }
    if (t.includes('boolean')) {
      return 'bg-rose-100 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-900';
    }
    if (t.includes('uuid')) {
      return 'bg-cyan-100 dark:bg-cyan-950/80 text-cyan-700 dark:text-cyan-300 border-cyan-200 dark:border-cyan-900';
    }
    return 'bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900';
  };

  // Human-readable relationship formatters
  const getCardinalityLabel = (type: string) => {
    switch (type) {
      case 'ONE_TO_MANY':
        return { short: '1 : N', full: 'Uno a Muchos', color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300' };
      case 'MANY_TO_ONE':
        return { short: 'N : 1', full: 'Muchos a Uno', color: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300' };
      case 'ONE_TO_ONE':
        return { short: '1 : 1', full: 'Uno a Uno', color: 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300' };
      case 'MANY_TO_MANY':
        return { short: 'N : M', full: 'Muchos a Muchos', color: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300' };
      default:
        return { short: 'Rel', full: type, color: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300' };
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Visual Navigation Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        {/* Mode Selector Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 p-1 rounded-lg bg-slate-100 dark:bg-slate-800/80 text-xs">
          <button
            type="button"
            onClick={() => setViewMode('erd-canvas')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
              viewMode === 'erd-canvas'
                ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Workflow className="w-3.5 h-3.5" />
            <span>Diagrama ER Relacional</span>
          </button>

          <button
            type="button"
            onClick={() => setViewMode('logical')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
              viewMode === 'logical'
                ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Boxes className="w-3.5 h-3.5" />
            <span>Modelo Lógico (Dominio)</span>
          </button>

          <button
            type="button"
            onClick={() => setViewMode('physical')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
              viewMode === 'physical'
                ? 'bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>Modelo Físico (Tablas SQL)</span>
          </button>

          <button
            type="button"
            onClick={() => setViewMode('graph')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
              viewMode === 'graph'
                ? 'bg-white dark:bg-slate-900 text-purple-600 dark:text-purple-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Workflow className="w-3.5 h-3.5" />
            <span>Grafo ER Interactivo</span>
          </button>

          <button
            type="button"
            onClick={() => setViewMode('mermaid')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
              viewMode === 'mermaid'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>Mermaid erDiagram</span>
          </button>
        </div>

        {/* Search & Stats */}
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Buscar entidad, columna, tipo..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 w-48 sm:w-64"
            />
          </div>

          <div className="hidden sm:flex items-center gap-2 text-[11px] font-mono text-slate-500 dark:text-slate-400">
            <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800">
              {entities.length} entidades
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800">
              {totalAttributes} atributos
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800">
              {totalRelationships} relaciones
            </span>
          </div>
        </div>
      </div>

      {/* Explanatory Banner per Mode */}
      {viewMode === 'erd-canvas' && (
        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex items-start gap-2.5 text-xs text-slate-800 dark:text-slate-200">
          <Workflow className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <strong className="font-semibold block">
              Diagrama Entidad-Relación Dinámico (Modelo Visual con Conectores & Cardinalidad)
            </strong>
            <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
              Generado automáticamente para este microservicio. Presenta tablas con claves primarias (🔑), claves foráneas (🗝️), conectores ortogonales y etiquetas de cardinalidad como (1,1), (0,n) y (1,n). Arrastra las cajas para organizarlas como prefieras.
            </p>
          </div>
        </div>
      )}

      {viewMode === 'erd-canvas' && (
        <ErDiagramCanvas
          entities={filteredEntities}
          serviceName={serviceName}
        />
      )}

      {viewMode === 'logical' && (
        <div className="p-3 rounded-xl bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900/50 flex items-start gap-2.5 text-xs text-blue-900 dark:text-blue-200">
          <Boxes className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <strong className="font-semibold block">
              Vista de Modelo Lógico (Entidades de Dominio & Contratos JPA)
            </strong>
            <p className="text-[11px] text-blue-700 dark:text-blue-300 leading-relaxed">
              Muestra las clases de entidad Jakarta Persistence (JPA), propiedades fuertemente tipadas en Java (Long, BigDecimal, Instant, UUID), reglas de validación de negocio (@NotNull, @NotBlank) y relaciones cardinales de dominio (1:N, N:1, 1:1, N:M) independientes del motor físico.
            </p>
          </div>
        </div>
      )}

      {viewMode === 'physical' && (
        <div className="p-3 rounded-xl bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/50 flex items-start gap-2.5 text-xs text-emerald-900 dark:text-emerald-200">
          <Database className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <strong className="font-semibold block">
              Vista de Modelo Físico Relacional (Tablas SQL & Restricciones)
            </strong>
            <p className="text-[11px] text-emerald-700 dark:text-emerald-300 leading-relaxed">
              Representación física exacta compatible con PostgreSQL 16 y H2: tablas normalizadas (snake_case), tipos SQL nativos (BIGINT, VARCHAR, TIMESTAMP WITH TIME ZONE), claves primarias autonuméricas, claves foráneas referenciales e índices de rendimiento.
            </p>
          </div>
        </div>
      )}

      {viewMode === 'graph' && (
        <div className="p-3 rounded-xl bg-purple-50/70 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-900/50 flex items-start gap-2.5 text-xs text-purple-900 dark:text-purple-200">
          <Workflow className="w-4 h-4 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <strong className="font-semibold block">
              Grafo Interactivo de Entidades y Relaciones (ER Visual)
            </strong>
            <p className="text-[11px] text-purple-700 dark:text-purple-300 leading-relaxed">
              Mapa visual navegable de dependencias de datos. Haga clic en cualquier entidad para aislar sus conexiones entrantes/salientes, examinar sus claves foráneas y explorar la cardinalidad.
            </p>
          </div>
        </div>
      )}

      {/* Mode 1: Logical Data Model */}
      {viewMode === 'logical' && (
        <div className="grid grid-cols-1 gap-4">
          {filteredEntities.map((entity) => {
            const isSelected = selectedEntityName === entity.name;
            const isCollapsed = collapsedCards[entity.name] || false;
            const attrs = entity.attributes || entity.fields || [];
            const rels = entity.relationships || [];
            const tableName = entity.tableName || `${entity.name.toLowerCase()}s`;

            return (
              <div
                key={entity.name}
                onClick={() => handleCardClick(entity.name)}
                className={`rounded-2xl border transition-all overflow-hidden ${
                  isSelected
                    ? 'border-blue-500 dark:border-blue-500 shadow-md ring-1 ring-blue-500/20'
                    : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
                } bg-white dark:bg-slate-900`}
              >
                {/* Entity Header */}
                <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-gradient-to-r from-blue-50/50 to-indigo-50/40 dark:from-slate-850 dark:to-slate-900 border-b border-slate-100 dark:border-slate-800">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-sm font-bold text-sm">
                      <Boxes className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-slate-900 dark:text-white font-mono">
                          {entity.name}
                        </h4>
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-blue-100 text-blue-800 dark:bg-blue-900/60 dark:text-blue-300 font-semibold">
                          @Entity
                        </span>
                        {isSelected && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500 text-white">
                            Activo
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono mt-0.5 flex items-center gap-2">
                        <span>Paquete: {entity.packageName || `${packageName}.model`}</span>
                        <span>•</span>
                        <span>Tabla Mapeada: <code className="text-slate-700 dark:text-slate-300">{tableName}</code></span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                      {attrs.length} campos
                    </span>
                    <span className="text-[11px] font-mono px-2 py-1 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400">
                      {rels.length} relaciones
                    </span>
                    <button
                      type="button"
                      onClick={(e) => toggleCollapse(entity.name, e)}
                      className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500"
                    >
                      {isCollapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {!isCollapsed && (
                  <div className="p-4 space-y-4">
                    {/* Entity Description */}
                    {entity.description && (
                      <p className="text-xs text-slate-600 dark:text-slate-400 italic">
                        {entity.description}
                      </p>
                    )}

                    {/* Attributes Table */}
                    <div>
                      <div className="text-xs font-bold text-slate-700 dark:text-slate-300 mb-2 uppercase tracking-wide flex items-center gap-1.5">
                        <span>Propiedades de Dominio JPA ({attrs.length})</span>
                      </div>
                      <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                        <table className="w-full text-left text-xs font-mono">
                          <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 text-[11px] uppercase border-b border-slate-200 dark:border-slate-800">
                            <tr>
                              <th className="py-2.5 px-3">Propiedad Java</th>
                              <th className="py-2.5 px-3">Tipo Java</th>
                              <th className="py-2.5 px-3 text-center">Clave</th>
                              <th className="py-2.5 px-3 text-center">Unicidad</th>
                              <th className="py-2.5 px-3 text-center">Nulabilidad</th>
                              <th className="py-2.5 px-3">Validaciones de Negocio</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                            {attrs.map((attr, aIdx) => {
                              const javaType = attr.javaType || attr.type || 'String';
                              const isPk = !!attr.isPrimaryKey || !!attr.primaryKey;
                              return (
                                <tr
                                  key={aIdx}
                                  className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                                >
                                  <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                                    {isPk && <Key className="w-3.5 h-3.5 text-amber-500 shrink-0" />}
                                    <span>{attr.name}</span>
                                  </td>
                                  <td className="py-2.5 px-3">
                                    <span
                                      className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${getJavaTypeBadge(
                                        javaType
                                      )}`}
                                    >
                                      {javaType}
                                    </span>
                                  </td>
                                  <td className="py-2.5 px-3 text-center">
                                    {isPk ? (
                                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                                        🔑 PK
                                      </span>
                                    ) : (
                                      <span className="text-slate-400">—</span>
                                    )}
                                  </td>
                                  <td className="py-2.5 px-3 text-center">
                                    {attr.isUnique ? (
                                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                                        ⭐ Único
                                      </span>
                                    ) : (
                                      <span className="text-slate-400">—</span>
                                    )}
                                  </td>
                                  <td className="py-2.5 px-3 text-center">
                                    {attr.nullable ? (
                                      <span className="text-slate-500 font-normal">Opcional</span>
                                    ) : (
                                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                                        Obligatorio
                                      </span>
                                    )}
                                  </td>
                                  <td className="py-2.5 px-3 text-slate-600 dark:text-slate-400">
                                    {attr.validationRules && attr.validationRules.length > 0 ? (
                                      <div className="flex flex-wrap gap-1">
                                        {attr.validationRules.map((rule, rIdx) => (
                                          <span
                                            key={rIdx}
                                            className="px-1.5 py-0.5 rounded text-[10px] bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-900/60"
                                          >
                                            {rule}
                                          </span>
                                        ))}
                                      </div>
                                    ) : (
                                      <span className="text-slate-400">—</span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Relationships Section */}
                    {rels.length > 0 && (
                      <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                        <div className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide flex items-center gap-1.5">
                          <Link2 className="w-3.5 h-3.5 text-indigo-500" />
                          <span>Relaciones de Dominio ({rels.length})</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {rels.map((rel, rIdx) => {
                            const cardInfo = getCardinalityLabel(rel.relationshipType);
                            return (
                              <div
                                key={rIdx}
                                onClick={() => handleCardClick(rel.targetEntity)}
                                className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer transition-all flex flex-col gap-1.5 text-xs font-mono"
                              >
                                <div className="flex items-center justify-between">
                                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${cardInfo.color}`}>
                                    {cardInfo.short} • {cardInfo.full}
                                  </span>
                                  <span className="text-[10px] text-slate-500 flex items-center gap-0.5">
                                    <span>Ir a entidad</span>
                                    <ExternalLink className="w-3 h-3" />
                                  </span>
                                </div>
                                <div className="flex items-center gap-1.5 font-bold text-slate-900 dark:text-white">
                                  <span>{entity.name}</span>
                                  <ArrowRight className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                                  <span className="text-blue-600 dark:text-blue-400">{rel.targetEntity}</span>
                                </div>
                                <div className="text-[11px] text-slate-500 dark:text-slate-400 space-y-0.5">
                                  {rel.joinColumnName && (
                                    <div>FK: <code className="text-slate-700 dark:text-slate-300">{rel.joinColumnName}</code></div>
                                  )}
                                  {rel.inversePropertyName && (
                                    <div>Inverso: <code className="text-slate-700 dark:text-slate-300">{rel.inversePropertyName}</code></div>
                                  )}
                                  <div className="text-[10px] text-slate-400">
                                    Cascade: {rel.cascadeType || 'ALL'} • Fetch: {rel.fetchType || 'LAZY'}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Mode 2: Physical Relational Model (Tablas SQL) */}
      {viewMode === 'physical' && (
        <div className="grid grid-cols-1 gap-4">
          {filteredEntities.map((entity) => {
            const isSelected = selectedEntityName === entity.name;
            const isCollapsed = collapsedCards[entity.name] || false;
            const attrs = entity.attributes || entity.fields || [];
            const rels = entity.relationships || [];
            const tableName = entity.tableName || `${entity.name.toLowerCase()}s`;

            return (
              <div
                key={entity.name}
                onClick={() => handleCardClick(entity.name)}
                className={`rounded-2xl border transition-all overflow-hidden ${
                  isSelected
                    ? 'border-emerald-500 dark:border-emerald-500 shadow-md ring-1 ring-emerald-500/20'
                    : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
                } bg-white dark:bg-slate-900`}
              >
                {/* Table Header */}
                <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-gradient-to-r from-emerald-50/50 to-teal-50/40 dark:from-slate-850 dark:to-slate-900 border-b border-slate-100 dark:border-slate-800">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-emerald-600 text-white flex items-center justify-center shadow-sm font-bold text-sm">
                      <Database className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-slate-900 dark:text-white font-mono">
                          TABLA: {tableName}
                        </h4>
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300 font-semibold">
                          PostgreSQL 16 / H2
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono mt-0.5">
                        Mapeo JPA hacia clase: <code className="text-slate-700 dark:text-slate-300">{entity.name}</code>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                      {attrs.length} columnas SQL
                    </span>
                    <button
                      type="button"
                      onClick={(e) => toggleCollapse(entity.name, e)}
                      className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500"
                    >
                      {isCollapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {!isCollapsed && (
                  <div className="p-4 space-y-4">
                    {/* Columns Table */}
                    <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 text-[11px] uppercase border-b border-slate-200 dark:border-slate-800">
                          <tr>
                            <th className="py-2.5 px-3">Columna SQL</th>
                            <th className="py-2.5 px-3">Tipo de Dato SQL</th>
                            <th className="py-2.5 px-3 text-center">Clave</th>
                            <th className="py-2.5 px-3 text-center">Nulabilidad</th>
                            <th className="py-2.5 px-3 text-center">Restricciones</th>
                            <th className="py-2.5 px-3">Valor por Defecto</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                          {attrs.map((attr, aIdx) => {
                            const isPk = !!attr.isPrimaryKey || !!attr.primaryKey;
                            const colName = attr.columnName || attr.name;
                            const sqlType = attr.sqlType || (isPk ? 'BIGINT' : 'VARCHAR(255)');
                            const isFk = attr.hasIndex && colName.endsWith('_id');

                            return (
                              <tr
                                key={aIdx}
                                className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                              >
                                <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                                  {isPk && <Key className="w-3.5 h-3.5 text-amber-500 shrink-0" />}
                                  <span>{colName}</span>
                                </td>
                                <td className="py-2.5 px-3 font-bold text-purple-600 dark:text-purple-400">
                                  {sqlType}
                                </td>
                                <td className="py-2.5 px-3 text-center">
                                  {isPk ? (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                                      PRIMARY KEY
                                    </span>
                                  ) : isFk ? (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                                      FOREIGN KEY
                                    </span>
                                  ) : (
                                    <span className="text-slate-400">—</span>
                                  )}
                                </td>
                                <td className="py-2.5 px-3 text-center">
                                  {attr.nullable ? (
                                    <span className="text-slate-400 font-mono">NULL</span>
                                  ) : (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                                      NOT NULL
                                    </span>
                                  )}
                                </td>
                                <td className="py-2.5 px-3 text-center">
                                  {attr.isUnique && (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 mr-1">
                                      UNIQUE
                                    </span>
                                  )}
                                  {attr.hasIndex && !isPk && (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300">
                                      INDEX
                                    </span>
                                  )}
                                  {!attr.isUnique && (!attr.hasIndex || isPk) && (
                                    <span className="text-slate-400">—</span>
                                  )}
                                </td>
                                <td className="py-2.5 px-3 text-slate-500 font-mono text-[11px]">
                                  {attr.defaultValue || (isPk ? 'GENERATED AS IDENTITY' : '—')}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {/* Physical Foreign Key Constraints */}
                    {rels.some((r) => r.relationshipType in { MANY_TO_ONE: 1, ONE_TO_ONE: 1 }) && (
                      <div className="space-y-1.5 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs font-mono">
                        <strong className="text-slate-700 dark:text-slate-300 block mb-1">
                          🔗 Restricciones de Clave Foránea Físicas (DDL):
                        </strong>
                        {rels
                          .filter((r) => ['MANY_TO_ONE', 'ONE_TO_ONE'].includes(r.relationshipType))
                          .map((r, rIdx) => {
                            const fkCol = r.joinColumnName || `${r.targetEntity.toLowerCase()}_id`;
                            const targetTable = `${r.targetEntity.toLowerCase()}s`;
                            return (
                              <div key={rIdx} className="text-[11px] text-slate-600 dark:text-slate-400">
                                <code className="text-blue-600 dark:text-blue-400">
                                  ALTER TABLE {tableName} ADD CONSTRAINT fk_{tableName}_{fkCol} FOREIGN KEY ({fkCol}) REFERENCES {targetTable}(id) ON DELETE CASCADE;
                                </code>
                              </div>
                            );
                          })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Mode 3: Interactive Visual ER Graph */}
      {viewMode === 'graph' && (
        <div className="space-y-4">
          <div className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 min-h-[380px] flex flex-col justify-center">
            {/* Visual Node Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredEntities.map((entity) => {
                const isSelected = selectedEntityName === entity.name;
                const attrs = entity.attributes || entity.fields || [];
                const rels = entity.relationships || [];
                const tableName = entity.tableName || `${entity.name.toLowerCase()}s`;
                const pk = attrs.find((a) => a.isPrimaryKey || a.primaryKey) || attrs[0];

                return (
                  <div
                    key={entity.name}
                    onClick={() => handleCardClick(entity.name)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all shadow-sm ${
                      isSelected
                        ? 'border-blue-500 bg-white dark:bg-slate-900 ring-2 ring-blue-500/20 shadow-md scale-[1.02]'
                        : 'border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 hover:border-slate-400'
                    }`}
                  >
                    {/* Node Header */}
                    <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2 mb-2">
                      <div className="flex items-center gap-2">
                        <Boxes className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                        <span className="font-bold text-sm text-slate-900 dark:text-white font-mono">
                          {entity.name}
                        </span>
                      </div>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                        {tableName}
                      </span>
                    </div>

                    {/* Node Summary */}
                    <div className="space-y-1.5 font-mono text-[11px]">
                      {pk && (
                        <div className="flex items-center justify-between text-amber-700 dark:text-amber-300">
                          <span className="flex items-center gap-1 font-semibold">
                            <Key className="w-3 h-3 text-amber-500" />
                            {pk.name}
                          </span>
                          <span className="text-[10px] font-bold">[PK] {pk.javaType || pk.type || 'Long'}</span>
                        </div>
                      )}

                      <div className="text-slate-500 dark:text-slate-400 pt-1 border-t border-dashed border-slate-100 dark:border-slate-800 flex items-center justify-between">
                        <span>{attrs.length} atributos</span>
                        <span>{rels.length} enlaces</span>
                      </div>
                    </div>

                    {/* Active Entity Connections Indicator */}
                    {rels.length > 0 && (
                      <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800 space-y-1">
                        <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                          Conexiones:
                        </span>
                        {rels.map((rel, rIdx) => (
                          <div
                            key={rIdx}
                            className="flex items-center justify-between text-[11px] font-mono text-slate-600 dark:text-slate-400"
                          >
                            <span className="text-blue-600 dark:text-blue-400 font-semibold truncate">
                              ➔ {rel.targetEntity}
                            </span>
                            <span className="text-[10px] px-1 rounded bg-slate-100 dark:bg-slate-800">
                              {getCardinalityLabel(rel.relationshipType).short}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Selected Entity Inspector in Graph Mode */}
            {selectedEntityName && (
              <div className="mt-6 p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-slate-900 dark:text-white">
                    Inspector de Relaciones para Entidad: <span className="text-blue-600 dark:text-blue-400 font-mono">{selectedEntityName}</span>
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">
                    Haga clic en otra entidad para alternar el enfoque
                  </span>
                </div>

                {(() => {
                  const ent = entities.find((e) => e.name === selectedEntityName);
                  if (!ent) return null;
                  const outgoing = ent.relationships || [];
                  const incoming = entities.flatMap((other) =>
                    (other.relationships || [])
                      .filter((r) => r.targetEntity === selectedEntityName)
                      .map((r) => ({ ...r, origin: other.name }))
                  );

                  return (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 font-mono text-[11px]">
                      <div className="p-3 rounded-lg bg-blue-50/50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/40">
                        <strong className="text-blue-800 dark:text-blue-300 block mb-1 font-sans text-xs">
                          Relaciones Salientes ({outgoing.length}):
                        </strong>
                        {outgoing.length > 0 ? (
                          outgoing.map((r, idx) => (
                            <div key={idx} className="flex items-center gap-2 py-0.5">
                              <span className="text-blue-600 font-bold">{selectedEntityName}</span>
                              <span className="text-slate-400">──({getCardinalityLabel(r.relationshipType).short})──&gt;</span>
                              <strong className="text-slate-900 dark:text-white">{r.targetEntity}</strong>
                              {r.joinColumnName && <span className="text-slate-400">({r.joinColumnName})</span>}
                            </div>
                          ))
                        ) : (
                          <span className="text-slate-400 italic">No tiene relaciones salientes</span>
                        )}
                      </div>

                      <div className="p-3 rounded-lg bg-indigo-50/50 dark:bg-indigo-950/30 border border-indigo-100 dark:border-indigo-900/40">
                        <strong className="text-indigo-800 dark:text-indigo-300 block mb-1 font-sans text-xs">
                          Relaciones Entrantes ({incoming.length}):
                        </strong>
                        {incoming.length > 0 ? (
                          incoming.map((r, idx) => (
                            <div key={idx} className="flex items-center gap-2 py-0.5">
                              <strong className="text-slate-900 dark:text-white">{r.origin}</strong>
                              <span className="text-slate-400">──({getCardinalityLabel(r.relationshipType).short})──&gt;</span>
                              <span className="text-indigo-600 font-bold">{selectedEntityName}</span>
                            </div>
                          ))
                        ) : (
                          <span className="text-slate-400 italic">No tiene relaciones entrantes</span>
                        )}
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Mode 4: Raw Mermaid erDiagram */}
      {viewMode === 'mermaid' && (
        <div className="space-y-3">
          <MermaidViewer
            chart={mermaidChart || 'erDiagram\n    EMPTY_SCHEMA'}
            title={`Diagrama Entidad-Relación: ${serviceName}`}
          />
        </div>
      )}
    </div>
  );
};

