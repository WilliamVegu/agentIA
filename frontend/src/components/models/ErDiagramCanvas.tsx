import React, { useState, useRef, useMemo, useEffect, useCallback } from 'react';
import {
  Key,
  Link2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Download,
  Layers,
  Move,
  Maximize2,
  Minimize2,
  Sparkles,
  Database,
  Boxes,
  HelpCircle,
} from 'lucide-react';

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

interface ErDiagramCanvasProps {
  entities: EntityDef[];
  serviceName?: string;
  className?: string;
}

interface NodePosition {
  x: number;
  y: number;
}

interface NormalizedRelation {
  id: string;
  fromEntity: string;
  toEntity: string;
  type: string;
  fromCardinality: string;
  toCardinality: string;
  label?: string;
  joinColumn?: string;
}

const CARD_WIDTH = 230;
const ROW_HEIGHT = 24;
const HEADER_HEIGHT = 44;
const FOOTER_HEIGHT = 28;

export const ErDiagramCanvas: React.FC<ErDiagramCanvasProps> = ({
  entities = [],
  serviceName = 'Microservicio',
  className = '',
}) => {
  const [notation, setNotation] = useState<'physical' | 'logical'>('physical');
  const [positions, setPositions] = useState<Record<string, NodePosition>>({});
  const [zoom, setZoom] = useState(1);
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [showLegend, setShowLegend] = useState(false);
  const [draggingEntity, setDraggingEntity] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<SVGSVGElement>(null);

  // Compute card height dynamically based on attributes count
  const getCardHeight = useCallback((entity: EntityDef) => {
    const attrs = entity.attributes || entity.fields || [];
    return HEADER_HEIGHT + Math.max(attrs.length, 1) * ROW_HEIGHT + FOOTER_HEIGHT + 10;
  }, []);

  // Compute automated clean layout (Topological / Hierarchical placement)
  const computeAutoLayout = useCallback(() => {
    if (!entities || entities.length === 0) return {};

    const inDegree: Record<string, number> = {};
    const adj: Record<string, string[]> = {};

    entities.forEach((e) => {
      inDegree[e.name] = 0;
      adj[e.name] = [];
    });

    entities.forEach((e) => {
      (e.relationships || []).forEach((r) => {
        if (adj[e.name] && !adj[e.name].includes(r.targetEntity)) {
          adj[e.name].push(r.targetEntity);
          if (inDegree[r.targetEntity] !== undefined) {
            inDegree[r.targetEntity]++;
          }
        }
      });
    });

    // Tier assignment
    const tiers: string[][] = [[], [], []];
    entities.forEach((e) => {
      const relCount = (e.relationships || []).length;
      if (inDegree[e.name] === 0 && relCount > 0) {
        tiers[0].push(e.name);
      } else if (relCount > 0) {
        tiers[1].push(e.name);
      } else {
        tiers[2].push(e.name);
      }
    });

    // If tiers are empty or unbalanced, distribute evenly in a 3-column grid
    const newPositions: Record<string, NodePosition> = {};
    const cols = Math.min(Math.max(Math.ceil(Math.sqrt(entities.length)), 2), 3);
    const xGap = 340;
    const yGap = 30;

    let colY = [40, 40, 40, 40];

    entities.forEach((entity, idx) => {
      const col = idx % cols;
      const x = 50 + col * xGap;
      const y = colY[col];
      newPositions[entity.name] = { x, y };
      colY[col] += getCardHeight(entity) + yGap;
    });

    return newPositions;
  }, [entities, getCardHeight]);

  // Initialize or reset positions when entities change
  useEffect(() => {
    setPositions(computeAutoLayout());
  }, [entities, computeAutoLayout]);

  // Extract normalized unique relationships
  const normalizedRelations = useMemo<NormalizedRelation[]>(() => {
    const list: NormalizedRelation[] = [];
    const seen = new Set<string>();

    entities.forEach((entity) => {
      (entity.relationships || []).forEach((rel, rIdx) => {
        const pairKey = [entity.name, rel.targetEntity].sort().join('___');
        if (seen.has(pairKey)) return;
        seen.add(pairKey);

        let fromCard = '(1,1)';
        let toCard = '(0,n)';

        if (rel.relationshipType === 'ONE_TO_MANY') {
          fromCard = '(1,1)';
          toCard = '(1,n)';
        } else if (rel.relationshipType === 'MANY_TO_ONE') {
          fromCard = '(0,n)';
          toCard = '(1,1)';
        } else if (rel.relationshipType === 'ONE_TO_ONE') {
          fromCard = '(1,1)';
          toCard = '(0,1)';
        } else if (rel.relationshipType === 'MANY_TO_MANY') {
          fromCard = '(0,n)';
          toCard = '(0,n)';
        }

        list.push({
          id: `${entity.name}-${rel.targetEntity}-${rIdx}`,
          fromEntity: entity.name,
          toEntity: rel.targetEntity,
          type: rel.relationshipType,
          fromCardinality: fromCard,
          toCardinality: toCard,
          label: rel.inversePropertyName || rel.joinColumnName || undefined,
          joinColumn: rel.joinColumnName,
        });
      });
    });

    return list;
  }, [entities]);

  // Calculate bounding box of all cards to size canvas
  const canvasSize = useMemo(() => {
    let maxX = 900;
    let maxY = 600;
    Object.entries(positions).forEach(([name, pos]) => {
      const ent = entities.find((e) => e.name === name);
      const h = ent ? getCardHeight(ent) : 250;
      if (pos.x + CARD_WIDTH + 80 > maxX) maxX = pos.x + CARD_WIDTH + 80;
      if (pos.y + h + 80 > maxY) maxY = pos.y + h + 80;
    });
    return { width: maxX, height: maxY };
  }, [positions, entities, getCardHeight]);

  // Mouse handlers for dragging table cards
  const handleMouseDown = (entityName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const currentPos = positions[entityName] || { x: 50, y: 50 };
    setDraggingEntity(entityName);
    setSelectedEntity(entityName);
    setDragOffset({
      x: e.clientX / zoom - currentPos.x,
      y: e.clientY / zoom - currentPos.y,
    });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!draggingEntity) return;
    const newX = Math.max(10, Math.round(e.clientX / zoom - dragOffset.x));
    const newY = Math.max(10, Math.round(e.clientY / zoom - dragOffset.y));
    setPositions((prev) => ({
      ...prev,
      [draggingEntity]: { x: newX, y: newY },
    }));
  };

  const handleMouseUp = () => {
    setDraggingEntity(null);
  };

  // Helper to compute orthogonal connector path between two boxes
  const calculatePath = (
    fromPos: NodePosition,
    fromHeight: number,
    toPos: NodePosition,
    toHeight: number
  ) => {
    let startX = 0;
    let startY = 0;
    let endX = 0;
    let endY = 0;

    // Horizontal placement
    if (fromPos.x + CARD_WIDTH < toPos.x) {
      // From is on the left of To
      startX = fromPos.x + CARD_WIDTH;
      startY = fromPos.y + fromHeight * 0.35;
      endX = toPos.x;
      endY = toPos.y + toHeight * 0.35;
    } else if (toPos.x + CARD_WIDTH < fromPos.x) {
      // To is on the left of From
      startX = fromPos.x;
      startY = fromPos.y + fromHeight * 0.35;
      endX = toPos.x + CARD_WIDTH;
      endY = toPos.y + toHeight * 0.35;
    } else {
      // Overlapping horizontally: connect vertically
      startX = fromPos.x + CARD_WIDTH / 2;
      endX = toPos.x + CARD_WIDTH / 2;
      if (fromPos.y < toPos.y) {
        startY = fromPos.y + fromHeight;
        endY = toPos.y;
      } else {
        startY = fromPos.y;
        endY = toPos.y + toHeight;
      }
      return {
        d: `M ${startX} ${startY} L ${startX} ${(startY + endY) / 2} L ${endX} ${(startY + endY) / 2} L ${endX} ${endY}`,
        startLabelPos: { x: startX + 10, y: startY + (endY > startY ? 16 : -16) },
        endLabelPos: { x: endX + 10, y: endY + (endY > startY ? -16 : 16) },
      };
    }

    // Standard orthogonal elbow path: horizontal -> vertical -> horizontal
    const midX = (startX + endX) / 2;
    const pathD = `M ${startX} ${startY} L ${midX} ${startY} L ${midX} ${endY} L ${endX} ${endY}`;

    const startLabelPos = {
      x: startX + (endX > startX ? 14 : -14),
      y: startY - 10,
    };
    const endLabelPos = {
      x: endX + (endX > startX ? -20 : 20),
      y: endY - 10,
    };

    return {
      d: pathD,
      startLabelPos,
      endLabelPos,
    };
  };

  const handleDownloadSvg = () => {
    if (!canvasRef.current) return;
    const svgData = new XMLSerializer().serializeToString(canvasRef.current);
    const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `erd-${serviceName.toLowerCase().replace(/[^a-z0-9]/g, '-')}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className={`rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm flex flex-col ${className}`}
    >
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-50 dark:bg-slate-850 border-b border-slate-200 dark:border-slate-800 text-xs">
        {/* Notation Selector */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-slate-200/80 dark:bg-slate-800 font-semibold">
          <button
            type="button"
            onClick={() => setNotation('physical')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
              notation === 'physical'
                ? 'bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>Físico Relacional (SQL)</span>
          </button>
          <button
            type="button"
            onClick={() => setNotation('logical')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all ${
              notation === 'logical'
                ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Boxes className="w-3.5 h-3.5" />
            <span>Lógico de Negocio (JPA)</span>
          </button>
        </div>

        {/* Canvas Controls */}
        <div className="flex items-center gap-2">
          {/* Zoom controls */}
          <div className="flex items-center gap-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-0.5">
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(0.5, Number((z - 0.1).toFixed(2))))}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded text-slate-600 dark:text-slate-300"
              title="Reducir zoom"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-[11px] font-mono px-1.5 font-bold text-slate-700 dark:text-slate-300 min-w-10 text-center">
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(1.5, Number((z + 0.1).toFixed(2))))}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded text-slate-600 dark:text-slate-300"
              title="Aumentar zoom"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setZoom(1)}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded text-slate-500 text-[10px] font-mono font-bold"
              title="Restablecer zoom a 100%"
            >
              1:1
            </button>
          </div>

          {/* Auto layout button */}
          <button
            type="button"
            onClick={() => setPositions(computeAutoLayout())}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 font-semibold text-xs transition-colors"
            title="Auto-organizar diagrama"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Auto-organizar</span>
          </button>

          {/* Legend toggle */}
          <button
            type="button"
            onClick={() => setShowLegend(!showLegend)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 font-semibold text-xs"
          >
            <HelpCircle className="w-3.5 h-3.5 text-blue-500" />
            <span className="hidden sm:inline">Leyenda</span>
          </button>

          {/* Export SVG */}
          <button
            type="button"
            onClick={handleDownloadSvg}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-sm transition-colors"
            title="Descargar diagrama vectorial SVG"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Descargar SVG</span>
          </button>
        </div>
      </div>

      {/* Legend Banner (if opened) */}
      {showLegend && (
        <div className="p-3 bg-blue-50/80 dark:bg-slate-800 border-b border-blue-100 dark:border-slate-700 text-xs text-slate-700 dark:text-slate-300 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono">
            <span className="flex items-center gap-1">
              <span className="w-4 h-4 rounded bg-slate-900 text-white flex items-center justify-center text-[10px]">
                🔑
              </span>
              <strong>Clave Primaria (PK)</strong>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-4 h-4 rounded bg-emerald-600 text-white flex items-center justify-center text-[10px]">
                🗝️
              </span>
              <strong>Clave Foránea (FK)</strong>
            </span>
            <span className="flex items-center gap-1">
              <code className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 font-bold">(1,1)</code>
              <span>Uno y exactamente uno</span>
            </span>
            <span className="flex items-center gap-1">
              <code className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 font-bold">(0,n) / (1,n)</code>
              <span>Cero o muchos / Uno o muchos</span>
            </span>
            <span className="flex items-center gap-1">
              <code className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-700 font-bold">(0,1)</code>
              <span>Cero o uno (Opcional)</span>
            </span>
          </div>
          <span className="text-[10px] text-slate-500 italic">
            Arrastra las cajas con el mouse para reorganizar las tablas como desees.
          </span>
        </div>
      )}

      {/* Interactive Diagram Canvas Area */}
      <div
        ref={containerRef}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        className="relative overflow-auto min-h-[540px] max-h-[700px] bg-slate-100/70 dark:bg-slate-950 p-4 select-none cursor-default"
        style={{
          backgroundImage:
            'radial-gradient(circle, rgba(148, 163, 184, 0.25) 1px, transparent 1px)',
          backgroundSize: '20px 20px',
        }}
      >
        <div
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: '0 0',
            width: canvasSize.width,
            height: canvasSize.height,
            position: 'relative',
          }}
        >
          {/* SVG Overlay for Connectors */}
          <svg
            ref={canvasRef}
            width={canvasSize.width}
            height={canvasSize.height}
            className="absolute inset-0 pointer-events-none z-10"
          >
            <defs>
              {/* Markers for Line Ends */}
              <marker
                id="erd-arrow"
                viewBox="0 0 10 10"
                refX="6"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 8 5 L 0 9 z" fill="#64748b" />
              </marker>
              <marker
                id="erd-circle"
                viewBox="0 0 10 10"
                refX="5"
                refY="5"
                markerWidth="6"
                markerHeight="6"
              >
                <circle cx="5" cy="5" r="3" fill="#ffffff" stroke="#64748b" strokeWidth="2" />
              </marker>
            </defs>

            {/* Render Orthogonal Lines */}
            {normalizedRelations.map((rel) => {
              const fromPos = positions[rel.fromEntity];
              const toPos = positions[rel.toEntity];
              const fromEntity = entities.find((e) => e.name === rel.fromEntity);
              const toEntity = entities.find((e) => e.name === rel.toEntity);

              if (!fromPos || !toPos || !fromEntity || !toEntity) return null;

              const fromH = getCardHeight(fromEntity);
              const toH = getCardHeight(toEntity);

              const { d, startLabelPos, endLabelPos } = calculatePath(
                fromPos,
                fromH,
                toPos,
                toH
              );

              const isHighlighted =
                selectedEntity === rel.fromEntity || selectedEntity === rel.toEntity;

              return (
                <g key={rel.id} className="transition-all">
                  {/* Line Background Glow when highlighted */}
                  {isHighlighted && (
                    <path
                      d={d}
                      fill="none"
                      stroke="#3b82f6"
                      strokeWidth="6"
                      strokeOpacity="0.25"
                      strokeLinecap="round"
                    />
                  )}

                  {/* Main Orthogonal Connector */}
                  <path
                    d={d}
                    fill="none"
                    stroke={isHighlighted ? '#2563eb' : '#64748b'}
                    strokeWidth={isHighlighted ? '2.5' : '1.8'}
                    strokeLinecap="square"
                    strokeLinejoin="round"
                  />

                  {/* Cardinality Badge at From (Source) */}
                  <g transform={`translate(${startLabelPos.x}, ${startLabelPos.y})`}>
                    <rect
                      x="-14"
                      y="-10"
                      width="34"
                      height="16"
                      rx="4"
                      fill="#ffffff"
                      stroke={isHighlighted ? '#3b82f6' : '#cbd5e1'}
                      strokeWidth="1.2"
                      className="shadow-sm"
                    />
                    <text
                      x="3"
                      y="2"
                      textAnchor="middle"
                      fontSize="10"
                      fontWeight="bold"
                      fill={isHighlighted ? '#1d4ed8' : '#334155'}
                      fontFamily="monospace"
                    >
                      {rel.fromCardinality}
                    </text>
                  </g>

                  {/* Cardinality Badge at To (Target) */}
                  <g transform={`translate(${endLabelPos.x}, ${endLabelPos.y})`}>
                    <rect
                      x="-14"
                      y="-10"
                      width="34"
                      height="16"
                      rx="4"
                      fill="#ffffff"
                      stroke={isHighlighted ? '#3b82f6' : '#cbd5e1'}
                      strokeWidth="1.2"
                      className="shadow-sm"
                    />
                    <text
                      x="3"
                      y="2"
                      textAnchor="middle"
                      fontSize="10"
                      fontWeight="bold"
                      fill={isHighlighted ? '#1d4ed8' : '#334155'}
                      fontFamily="monospace"
                    >
                      {rel.toCardinality}
                    </text>
                  </g>
                </g>
              );
            })}
          </svg>

          {/* Entity Cards rendered on the canvas */}
          {entities.map((entity) => {
            const pos = positions[entity.name] || { x: 50, y: 50 };
            const isSelected = selectedEntity === entity.name;
            const attrs = entity.attributes || entity.fields || [];
            const tableName = (entity.tableName || `${entity.name.toLowerCase()}s`).toUpperCase();
            const displayName = notation === 'physical' ? tableName : entity.name;

            return (
              <div
                key={entity.name}
                onMouseDown={(e) => handleMouseDown(entity.name, e)}
                style={{
                  transform: `translate(${pos.x}px, ${pos.y}px)`,
                  width: CARD_WIDTH,
                  position: 'absolute',
                }}
                className={`z-20 rounded-xl overflow-hidden shadow-lg border transition-shadow cursor-grab active:cursor-grabbing ${
                  isSelected
                    ? 'border-blue-500 ring-2 ring-blue-500/30 shadow-xl'
                    : 'border-slate-300 dark:border-slate-700 hover:border-slate-400'
                } bg-white dark:bg-slate-900`}
              >
                {/* Entity Table Header (Classic ERD Style like Photo) */}
                <div
                  className={`px-3 py-2.5 flex items-center justify-between border-b ${
                    isSelected
                      ? 'bg-slate-700 text-white border-slate-800'
                      : 'bg-gradient-to-b from-slate-200 to-slate-300 dark:from-slate-750 dark:to-slate-800 text-slate-800 dark:text-slate-100 border-slate-300 dark:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-1.5 overflow-hidden">
                    <span className="font-mono font-bold text-xs tracking-wider uppercase truncate">
                      {displayName}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono px-1 rounded bg-black/10 dark:bg-white/10 shrink-0">
                    {attrs.length}
                  </span>
                </div>

                {/* Attributes Body */}
                <div className="py-1 divide-y divide-slate-100 dark:divide-slate-800/60 font-mono text-[11px]">
                  {attrs.map((attr, aIdx) => {
                    const isPk = !!attr.isPrimaryKey || !!attr.primaryKey;
                    const colName = attr.columnName || attr.name;
                    const attrName = notation === 'physical' ? colName : attr.name;
                    const isFk =
                      !isPk &&
                      (attr.hasIndex ||
                        colName.toLowerCase().endsWith('_id') ||
                        colName.toLowerCase().startsWith('cod_'));

                    const typeStr =
                      notation === 'physical'
                        ? (attr.sqlType || (isPk ? 'BIGINT' : 'VARCHAR')).split('(')[0].toLowerCase()
                        : attr.javaType || attr.type || 'String';

                    return (
                      <div
                        key={aIdx}
                        className={`px-3 py-1 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/40 ${
                          isPk
                            ? 'font-bold text-slate-900 dark:text-white bg-amber-50/30 dark:bg-amber-950/20'
                            : isFk
                            ? 'text-slate-800 dark:text-slate-200'
                            : 'text-slate-600 dark:text-slate-400'
                        }`}
                      >
                        <div className="flex items-center gap-1.5 truncate">
                          {/* Key Icon: Black key for PK, Green/Slate for FK, or space */}
                          {isPk ? (
                            <span
                              className="w-3.5 h-3.5 rounded bg-slate-900 text-white flex items-center justify-center text-[9px] shrink-0"
                              title="Primary Key"
                            >
                              🔑
                            </span>
                          ) : isFk ? (
                            <span
                              className="w-3.5 h-3.5 rounded bg-emerald-700 text-white flex items-center justify-center text-[9px] shrink-0"
                              title="Foreign Key"
                            >
                              🗝️
                            </span>
                          ) : (
                            <span className="w-3.5 shrink-0" />
                          )}
                          <span className="truncate">{attrName}</span>
                        </div>

                        <span className="text-[10px] text-slate-400 shrink-0 font-normal ml-2">
                          {typeStr}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* Footer Compartment with Key Icon (Mirroring the reference image) */}
                <div className="px-3 py-1.5 bg-slate-50 dark:bg-slate-850 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-[10px] text-slate-400">
                  <div className="flex items-center gap-1">
                    <Key className="w-3 h-3 text-slate-500" />
                    <span className="font-mono text-[9px]">
                      {entity.tableName || `${entity.name.toLowerCase()}s`}
                    </span>
                  </div>
                  <span className="font-mono text-[9px]">PostgreSQL 16</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer bar with Microservice context summary */}
      <div className="px-4 py-2 bg-slate-50 dark:bg-slate-850 border-t border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600 dark:text-slate-400 font-mono">
        <div>
          Modelo Generado Dinámicamente para:{' '}
          <strong className="text-slate-900 dark:text-white">{serviceName}</strong> (
          {entities.length} tablas, {normalizedRelations.length} relaciones)
        </div>
        <div className="text-[11px] text-slate-500">
          Notación: {notation === 'physical' ? 'Física Relacional ANSI/SQL' : 'Lógica de Dominio JPA'}
        </div>
      </div>
    </div>
  );
};
