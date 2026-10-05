import React, { useState } from 'react';
import { Copy, Check, Eye, Code as CodeIcon } from 'lucide-react';

interface MermaidViewerProps {
  chart: string;
  title?: string;
  className?: string;
}

interface ParsedErEntity {
  name: string;
  attributes: Array<{
    type: string;
    name: string;
    key?: string;
  }>;
}

interface ParsedErRelation {
  source: string;
  target: string;
  cardinality: string;
  label?: string;
}

function parseErRelations(chartText: string): ParsedErRelation[] {
  const relations: ParsedErRelation[] = [];
  const lines = chartText.split('\n');
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith('%%') || line.toLowerCase().startsWith('erdiagram')) continue;
    const relMatch = line.match(/^([A-Za-z0-9_\-]+)\s*(\|\|--o\{|\|\|--\|\{|\|\|--\|\||\}o--o\{|}\|--o\{|\|o--o\{|\}o--\|\{)\s*([A-Za-z0-9_\-]+)(?:\s*:\s*["']?([^"'\n]+)["']?)?/);
    if (relMatch) {
      relations.push({
        source: relMatch[1].trim(),
        cardinality: relMatch[2].trim(),
        target: relMatch[3].trim(),
        label: relMatch[4] ? relMatch[4].trim() : undefined,
      });
    }
  }
  return relations;
}

function parseErDiagram(chartText: string): ParsedErEntity[] {
  const entities: ParsedErEntity[] = [];
  const blockRegex = /([A-Za-z0-9_]+)\s*\{([^}]*)\}/g;
  let match: RegExpExecArray | null;

  while ((match = blockRegex.exec(chartText)) !== null) {
    const entName = match[1].trim();
    if (entName.toLowerCase() === 'erdiagram') continue;

    const body = match[2];
    const rawLines = body.split('\n');
    const attributes: Array<{ type: string; name: string; key?: string }> = [];

    for (const rawLine of rawLines) {
      const trimmed = rawLine.trim();
      if (!trimmed || trimmed.startsWith('%%')) continue;
      const parts = trimmed.split(/\s+/);
      if (parts.length >= 2) {
        const type = parts[0];
        const name = parts[1];
        const key = parts.slice(2).join(' ') || undefined;
        attributes.push({ type, name, key });
      } else if (parts.length === 1) {
        attributes.push({ type: '', name: parts[0] });
      }
    }

    entities.push({ name: entName, attributes });
  }

  if (entities.length === 0) {
    const lines = chartText.split('\n').map((l) => l.trim());
    for (const line of lines) {
      if (line.includes('{')) {
        const entName = line.split('{')[0].trim();
        if (entName && entName.toLowerCase() !== 'erdiagram') {
          entities.push({ name: entName, attributes: [] });
        }
      }
    }
  }

  return entities;
}

interface FlowNode {
  id: string;
  label: string;
  subgraph?: string;
}

interface FlowEdge {
  from: string;
  to: string;
  label?: string;
}

interface FlowSubgraph {
  id: string;
  title: string;
  nodeIds: string[];
}

interface ParsedFlowDiagram {
  subgraphs: FlowSubgraph[];
  nodes: FlowNode[];
  edges: FlowEdge[];
}

function parseFlowDiagram(chartText: string): ParsedFlowDiagram {
  const subgraphs: FlowSubgraph[] = [];
  const nodeMap = new Map<string, FlowNode>();
  const edges: FlowEdge[] = [];
  let currentSubgraph: FlowSubgraph | null = null;

  const lines = chartText.split('\n');

  // Helper to extract clean node label and id from a chunk like `NodeId["Label"]` or `NodeId`
  const extractNodeInfo = (chunk: string): { id: string; label: string } | null => {
    const trimmed = chunk.trim();
    if (!trimmed) return null;

    // Pattern matching Id[Label], Id(Label), Id([Label]), Id[(Label)], Id{Label}
    const match = trimmed.match(/^([A-Za-z0-9_\-\.]+)\s*(?:\[\[|\[\(|\[|\(\[|\(|\{|\>)(.+?)(?:\]\]|\)\]|\]|\)\]|\)|\}|\])$/);
    if (match) {
      const id = match[1].trim();
      let label = match[2].trim();
      if ((label.startsWith('"') && label.endsWith('"')) || (label.startsWith("'") && label.endsWith("'"))) {
        label = label.slice(1, -1);
      }
      return { id, label };
    }

    // Plain ID without brackets
    const plainMatch = trimmed.match(/^([A-Za-z0-9_\-\.]+)$/);
    if (plainMatch) {
      const id = plainMatch[1].trim();
      return { id, label: id };
    }

    return null;
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith('%%')) continue;

    // Ignore header directives
    if (/^(graph|flowchart)\s+[A-Za-z0-9]+/.test(line)) continue;

    // Subgraph start
    const subMatch = line.match(/^subgraph\s+([A-Za-z0-9_\-]+)(?:\s*\[?["']?([^\]"']+)["']?\]?)?/i);
    if (subMatch) {
      const subId = subMatch[1];
      const subTitle = subMatch[2] || subId;
      currentSubgraph = { id: subId, title: subTitle.trim(), nodeIds: [] };
      subgraphs.push(currentSubgraph);
      continue;
    }

    // Subgraph end
    if (line.toLowerCase() === 'end') {
      currentSubgraph = null;
      continue;
    }

    // Check for edge: A --> B or A -->|text| B or A -.-> B or A ==> B
    const edgeMatch = line.match(/^(.+?)\s*(-->|==>|-\.->|---|-->\|[^|]+\|)\s*(.+)$/);
    if (edgeMatch) {
      const leftPart = edgeMatch[1].trim();
      const arrowPart = edgeMatch[2].trim();
      const rightPart = edgeMatch[3].trim();

      let edgeLabel: string | undefined = undefined;
      if (arrowPart.includes('|')) {
        const pipeMatch = arrowPart.match(/\|([^|]+)\|/);
        if (pipeMatch) edgeLabel = pipeMatch[1].trim();
      } else if (rightPart.startsWith('|')) {
        const rightPipeMatch = rightPart.match(/^\|([^|]+)\|\s*(.+)$/);
        if (rightPipeMatch) {
          edgeLabel = rightPipeMatch[1].trim();
        }
      }

      const leftNode = extractNodeInfo(leftPart);
      const rightNode = extractNodeInfo(rightPart.replace(/^\|[^|]+\|\s*/, ''));

      if (leftNode) {
        if (!nodeMap.has(leftNode.id)) {
          nodeMap.set(leftNode.id, {
            ...leftNode,
            subgraph: currentSubgraph?.id,
          });
          if (currentSubgraph) currentSubgraph.nodeIds.push(leftNode.id);
        }
      }

      if (rightNode) {
        if (!nodeMap.has(rightNode.id)) {
          nodeMap.set(rightNode.id, {
            ...rightNode,
            subgraph: currentSubgraph?.id,
          });
          if (currentSubgraph) currentSubgraph.nodeIds.push(rightNode.id);
        }
      }

      if (leftNode && rightNode) {
        edges.push({
          from: leftNode.id,
          to: rightNode.id,
          label: edgeLabel,
        });
      }
      continue;
    }

    // Standalone node definition inside line
    const singleNode = extractNodeInfo(line);
    if (singleNode && !nodeMap.has(singleNode.id)) {
      nodeMap.set(singleNode.id, {
        ...singleNode,
        subgraph: currentSubgraph?.id,
      });
      if (currentSubgraph) currentSubgraph.nodeIds.push(singleNode.id);
    }
  }

  return {
    subgraphs,
    nodes: Array.from(nodeMap.values()),
    edges,
  };
}

function getNodeColorClass(label: string, id: string): { bg: string; border: string; text: string; badge: string } {
  const text = `${label} ${id}`.toLowerCase();
  if (text.includes('controller') || text.includes('rest') || text.includes('api') || text.includes('inbound') || text.includes('client') || text.includes('gateway')) {
    return {
      bg: 'bg-blue-50 dark:bg-blue-950/40',
      border: 'border-blue-200 dark:border-blue-900/60',
      text: 'text-blue-700 dark:text-blue-300',
      badge: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    };
  }
  if (text.includes('port') || text.includes('interface') || text.includes('contract')) {
    return {
      bg: 'bg-indigo-50 dark:bg-indigo-950/40',
      border: 'border-indigo-200 dark:border-indigo-900/60',
      text: 'text-indigo-700 dark:text-indigo-300',
      badge: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
    };
  }
  if (text.includes('service') || text.includes('domain') || text.includes('core') || text.includes('usecase') || text.includes('logic')) {
    return {
      bg: 'bg-purple-50 dark:bg-purple-950/40',
      border: 'border-purple-200 dark:border-purple-900/60',
      text: 'text-purple-700 dark:text-purple-300',
      badge: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
    };
  }
  if (text.includes('repo') || text.includes('adapter') || text.includes('persistence') || text.includes('outbound') || text.includes('db') || text.includes('sql') || text.includes('postgres') || text.includes('mysql') || text.includes('data')) {
    return {
      bg: 'bg-emerald-50 dark:bg-emerald-950/40',
      border: 'border-emerald-200 dark:border-emerald-900/60',
      text: 'text-emerald-700 dark:text-emerald-300',
      badge: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200',
    };
  }
  return {
    bg: 'bg-slate-50 dark:bg-slate-900',
    border: 'border-slate-200 dark:border-slate-800',
    text: 'text-slate-800 dark:text-slate-200',
    badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  };
}

export const MermaidViewer: React.FC<MermaidViewerProps> = ({
  chart,
  title = 'Diagrama de Arquitectura / ER',
  className = '',
}) => {
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<'diagram' | 'source'>('diagram');

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(chart);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const isEr = chart.includes('erDiagram');
  const parsedEntities = React.useMemo(() => (isEr ? parseErDiagram(chart) : []), [isEr, chart]);
  const parsedRelations = React.useMemo(() => (isEr ? parseErRelations(chart) : []), [isEr, chart]);
  const parsedFlow = React.useMemo(() => (!isEr ? parseFlowDiagram(chart) : { subgraphs: [], nodes: [], edges: [] }), [isEr, chart]);

  return (
    <div className={`rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/60 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 text-xs">
        <span className="font-semibold text-slate-800 dark:text-slate-200">
          {title}
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode(viewMode === 'diagram' ? 'source' : 'diagram')}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:text-blue-600 transition-colors"
            title="Alternar vista de código / diagrama"
          >
            {viewMode === 'diagram' ? (
              <>
                <CodeIcon className="w-3.5 h-3.5" />
                <span>Ver Código</span>
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5" />
                <span>Ver Diagrama</span>
              </>
            )}
          </button>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:text-blue-600 transition-colors"
            title="Copiar definición Mermaid"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-500" />
                <span className="text-emerald-600 dark:text-emerald-400">Copiado</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copiar</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="p-4 overflow-x-auto min-h-[220px]">
        {viewMode === 'source' ? (
          <pre className="text-xs font-mono text-slate-800 dark:text-slate-200 whitespace-pre leading-relaxed">
            {chart}
          </pre>
        ) : (
          <div className="flex flex-col gap-3 items-center justify-center py-4">
            {isEr ? (
              <div className="w-full max-w-3xl bg-white dark:bg-slate-950 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-inner space-y-4">
                <div className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide">
                  Entidades de Datos ({parsedEntities.length})
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {parsedEntities.map((ent, idx) => (
                    <div key={idx} className="p-3 bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                      <div className="text-xs font-bold text-slate-900 dark:text-white border-b pb-1 mb-2 border-slate-200 dark:border-slate-800 font-mono">
                        {ent.name}
                      </div>
                      <div className="text-[11px] text-slate-600 dark:text-slate-400 font-mono space-y-0.5">
                        {ent.attributes.length > 0 ? (
                          ent.attributes.map((attr, aIdx) => (
                            <div key={aIdx} className="truncate">
                              + {attr.name} {attr.type ? `: ${attr.type}` : ''} {attr.key ? `[${attr.key}]` : ''}
                            </div>
                          ))
                        ) : (
                          <div className="text-slate-400 italic">Sin atributos definidos</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {parsedRelations.length > 0 && (
                  <div className="pt-3 border-t border-slate-200 dark:border-slate-800 space-y-2">
                    <div className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wide">
                      Relaciones y Cardinalidad ({parsedRelations.length})
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
                      {parsedRelations.map((rel, rIdx) => (
                        <div
                          key={rIdx}
                          className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800"
                        >
                          <span className="font-bold text-slate-800 dark:text-slate-200">{rel.source}</span>
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300">
                            {rel.cardinality}
                          </span>
                          <span className="font-bold text-blue-600 dark:text-blue-400">{rel.target}</span>
                          {rel.label && (
                            <span className="text-[10px] text-slate-500 italic">({rel.label})</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : parsedFlow.nodes.length > 0 ? (
              <div className="w-full max-w-3xl flex flex-col gap-4">
                {/* Subgraphs or Grouped Layout */}
                {parsedFlow.subgraphs.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {parsedFlow.subgraphs.map((sub, sIdx) => {
                      const subNodes = parsedFlow.nodes.filter((n) => n.subgraph === sub.id);
                      return (
                        <div
                          key={sIdx}
                          className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-950/70 shadow-sm flex flex-col gap-2.5"
                        >
                          <div className="text-xs font-bold text-slate-700 dark:text-slate-300 border-b border-slate-100 dark:border-slate-800 pb-1.5 flex items-center justify-between">
                            <span>{sub.title}</span>
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                              {subNodes.length} nodos
                            </span>
                          </div>
                          <div className="flex flex-col gap-2">
                            {subNodes.map((node) => {
                              const style = getNodeColorClass(node.label, node.id);
                              return (
                                <div
                                  key={node.id}
                                  className={`p-2.5 rounded-lg border ${style.bg} ${style.border} transition-all`}
                                >
                                  <div className={`text-xs font-bold ${style.text}`}>
                                    {node.label}
                                  </div>
                                  {node.label !== node.id && (
                                    <div className="text-[10px] font-mono text-slate-500 dark:text-slate-400 mt-0.5">
                                      id: {node.id}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  /* Linear / Flow layout when no subgraphs */
                  <div className="flex flex-col gap-2 items-center w-full">
                    {parsedFlow.nodes.map((node, nIdx) => {
                      const style = getNodeColorClass(node.label, node.id);
                      const outgoing = parsedFlow.edges.filter((e) => e.from === node.id);
                      return (
                        <React.Fragment key={node.id}>
                          <div
                            className={`w-full max-w-xl p-3 rounded-lg border ${style.bg} ${style.border} text-center shadow-sm`}
                          >
                            <div className={`text-xs font-bold ${style.text}`}>
                              {node.label}
                            </div>
                            {node.label !== node.id && (
                              <div className="text-[11px] font-mono text-slate-500 dark:text-slate-400 mt-0.5">
                                {node.id}
                              </div>
                            )}
                          </div>
                          {nIdx < parsedFlow.nodes.length - 1 && (
                            <div className="flex flex-col items-center text-slate-400 dark:text-slate-600 font-bold text-xs py-0.5">
                              {outgoing.length > 0 && outgoing[0].label && (
                                <span className="text-[10px] font-mono text-slate-500 mb-0.5">
                                  {outgoing[0].label}
                                </span>
                              )}
                              <span>↓</span>
                            </div>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </div>
                )}

                {/* Connections / Interacciones Table */}
                {parsedFlow.edges.length > 0 && (
                  <div className="mt-2 p-3 bg-white dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800">
                    <div className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2 uppercase tracking-wider flex items-center justify-between">
                      <span>Interacciones & Flujo de Dependencias ({parsedFlow.edges.length})</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono">
                      {parsedFlow.edges.map((edge, eIdx) => {
                        const fromLabel = parsedFlow.nodes.find((n) => n.id === edge.from)?.label || edge.from;
                        const toLabel = parsedFlow.nodes.find((n) => n.id === edge.to)?.label || edge.to;
                        return (
                          <div
                            key={eIdx}
                            className="flex items-center gap-1.5 p-2 rounded bg-slate-50 dark:bg-slate-900 border border-slate-100 dark:border-slate-800/60"
                          >
                            <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">
                              {fromLabel}
                            </span>
                            <span className="text-blue-500 font-bold">→</span>
                            <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">
                              {toLabel}
                            </span>
                            {edge.label && (
                              <span className="text-[10px] text-slate-500 ml-auto italic">
                                ({edge.label})
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="w-full max-w-2xl flex flex-col gap-2 items-center">
                {/* Fallback Representation */}
                <div className="w-full p-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900/60 text-center">
                  <div className="text-xs font-bold text-blue-700 dark:text-blue-300">Capa 1: Controllers (REST Endpoints)</div>
                  <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 font-mono">@RestController /api/v1/*</div>
                </div>
                <div className="text-slate-400 dark:text-slate-600 font-bold">↓</div>
                <div className="w-full p-3 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900/60 text-center">
                  <div className="text-xs font-bold text-indigo-700 dark:text-indigo-300">Capa 2: Services (Business Logic)</div>
                  <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 font-mono">@Service Spring Transactional</div>
                </div>
                <div className="text-slate-400 dark:text-slate-600 font-bold">↓</div>
                <div className="w-full p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 text-center">
                  <div className="text-xs font-bold text-emerald-700 dark:text-emerald-300">Capa 3: Repositories (Data Access)</div>
                  <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 font-mono">@Repository JpaRepository</div>
                </div>
                <div className="text-slate-400 dark:text-slate-600 font-bold">↓</div>
                <div className="w-full p-3 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-center">
                  <div className="text-xs font-bold text-slate-800 dark:text-slate-200">Capa 4: Models & SQL (PostgreSQL / MySQL / H2)</div>
                  <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 font-mono">Jakarta @Entity & Liquibase/DDL</div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
