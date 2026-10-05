import React, { useState, useMemo } from 'react';
import {
  Database,
  Table,
  Code2,
  Download,
  Key,
  Copy,
  Check,
  Search,
  Sparkles,
  Layers,
  FileText,
  Filter,
} from 'lucide-react';
import { CodeViewer } from '../common/CodeViewer';

export type SqlViewTab = 'visual-tables' | 'visual-data' | 'schema-ddl' | 'seed-dml';

interface VisualSqlViewerProps {
  schemaDdl: string;
  seedDml: string;
  dialect?: string;
  entities?: any[];
  serviceName?: string;
  onDownloadSchema?: () => void;
  onDownloadData?: () => void;
  className?: string;
}

function parseSeedDml(dml: string): Record<string, { columns: string[]; rows: string[][] }> {
  const result: Record<string, { columns: string[]; rows: string[][] }> = {};
  if (!dml) return result;

  const lines = dml.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('--')) continue;

    // Pattern: INSERT INTO table (col1, col2, ...) VALUES (val1, val2, ...);
    const insertMatch = trimmed.match(
      /INSERT\s+INTO\s+([A-Za-z0-9_]+)\s*\(([^)]+)\)\s*VALUES\s*\((.+)\);?/i
    );
    if (insertMatch) {
      const table = insertMatch[1].toLowerCase();
      const cols = insertMatch[2].split(',').map((c) => c.trim().replace(/[`"']/g, ''));
      const rawVals = insertMatch[3];
      const vals: string[] = [];
      let inQuote = false;
      let currentVal = '';
      for (let i = 0; i < rawVals.length; i++) {
        const char = rawVals[i];
        if (char === "'" && (i === 0 || rawVals[i - 1] !== '\\')) {
          inQuote = !inQuote;
        } else if (char === ',' && !inQuote) {
          vals.push(currentVal.trim().replace(/^'|'$/g, ''));
          currentVal = '';
          continue;
        }
        currentVal += char;
      }
      if (currentVal.trim()) {
        vals.push(currentVal.trim().replace(/^'|'$/g, ''));
      }

      if (!result[table]) {
        result[table] = { columns: cols, rows: [] };
      }
      result[table].rows.push(vals);
    }
  }
  return result;
}

export const VisualSqlViewer: React.FC<VisualSqlViewerProps> = ({
  schemaDdl = '',
  seedDml = '',
  dialect = 'PostgreSQL 16 & H2',
  entities = [],
  serviceName = 'service',
  onDownloadSchema,
  onDownloadData,
  className = '',
}) => {
  const [activeTab, setActiveTab] = useState<SqlViewTab>('visual-tables');
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [tableSearch, setTableSearch] = useState('');
  const [copiedData, setCopiedData] = useState(false);

  // Parse seed data
  const parsedSeedData = useMemo(() => {
    return parseSeedDml(seedDml);
  }, [seedDml]);

  // Available table names
  const tableNames = useMemo(() => {
    const fromEntities = entities.map((e) => e.tableName || `${e.name.toLowerCase()}s`);
    const fromSeeds = Object.keys(parsedSeedData);
    const combined = Array.from(new Set([...fromEntities, ...fromSeeds]));
    return combined.length > 0 ? combined : ['orders'];
  }, [entities, parsedSeedData]);

  // Set default selected table
  React.useEffect(() => {
    if (tableNames.length > 0 && !selectedTable) {
      setSelectedTable(tableNames[0]);
    }
  }, [tableNames, selectedTable]);

  // Metrics
  const totalTables = tableNames.length;
  const totalColumns = useMemo(() => {
    return entities.reduce((acc, e) => acc + (e.attributes || e.fields || []).length, 0);
  }, [entities]);

  const totalIndexes = useMemo(() => {
    return entities.reduce((acc, e) => {
      const attrs = e.attributes || e.fields || [];
      return acc + attrs.filter((a: any) => a.hasIndex && !a.isPrimaryKey).length;
    }, 0);
  }, [entities]);

  const totalFks = useMemo(() => {
    return entities.reduce((acc, e) => {
      const rels = e.relationships || [];
      return acc + rels.filter((r: any) => ['MANY_TO_ONE', 'ONE_TO_ONE'].includes(r.relationshipType)).length;
    }, 0);
  }, [entities]);

  // Seed rows for currently selected table
  const currentSeedTable = parsedSeedData[selectedTable.toLowerCase()] || null;
  const currentEntity = entities.find(
    (e) => (e.tableName || `${e.name.toLowerCase()}s`).toLowerCase() === selectedTable.toLowerCase()
  );

  const handleCopySeedJson = async () => {
    if (!currentSeedTable) return;
    try {
      const jsonRecords = currentSeedTable.rows.map((row) => {
        const obj: Record<string, string> = {};
        currentSeedTable.columns.forEach((col, idx) => {
          obj[col] = row[idx] ?? '';
        });
        return obj;
      });
      await navigator.clipboard.writeText(JSON.stringify(jsonRecords, null, 2));
      setCopiedData(true);
      setTimeout(() => setCopiedData(false), 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Top Navigation & Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex flex-wrap items-center gap-1.5 p-1 rounded-lg bg-slate-100 dark:bg-slate-800/80 text-xs">
          <button
            type="button"
            onClick={() => setActiveTab('visual-tables')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
              activeTab === 'visual-tables'
                ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>Esquema Visual de Tablas</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('visual-data')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
              activeTab === 'visual-data'
                ? 'bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Table className="w-3.5 h-3.5" />
            <span>Grid Visual de Datos Semilla</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('schema-ddl')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
              activeTab === 'schema-ddl'
                ? 'bg-white dark:bg-slate-900 text-purple-600 dark:text-purple-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>schema.sql (DDL)</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('seed-dml')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-semibold transition-all ${
              activeTab === 'seed-dml'
                ? 'bg-white dark:bg-slate-900 text-amber-600 dark:text-amber-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>data.sql (DML)</span>
          </button>
        </div>

        {/* Global Dialect & Table Quick Stats */}
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2.5 py-1 rounded-full text-[11px] font-mono font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            {dialect}
          </span>
          <span className="hidden sm:inline-block text-[11px] text-slate-400 font-mono">
            {totalTables} tablas • {totalColumns} columnas
          </span>
        </div>
      </div>

      {/* Tab 1: Visual Tables Schema Inspector */}
      {activeTab === 'visual-tables' && (
        <div className="space-y-4">
          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">Total Tablas</span>
              <span className="text-xl font-bold text-slate-900 dark:text-white font-mono">{totalTables}</span>
            </div>
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">Columnas Normalizadas</span>
              <span className="text-xl font-bold text-blue-600 dark:text-blue-400 font-mono">{totalColumns}</span>
            </div>
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">Claves Foráneas (FK)</span>
              <span className="text-xl font-bold text-purple-600 dark:text-purple-400 font-mono">{totalFks}</span>
            </div>
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block">Índices de Rendimiento</span>
              <span className="text-xl font-bold text-emerald-600 dark:text-emerald-400 font-mono">{totalIndexes}</span>
            </div>
          </div>

          {/* Table Cards Grid */}
          <div className="grid grid-cols-1 gap-4">
            {entities.map((entity) => {
              const tableName = entity.tableName || `${entity.name.toLowerCase()}s`;
              const attrs = entity.attributes || entity.fields || [];
              const rels = entity.relationships || [];
              const pkAttr = attrs.find((a: any) => a.isPrimaryKey || a.primaryKey);

              return (
                <div
                  key={entity.name}
                  className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm"
                >
                  <div className="flex flex-wrap items-center justify-between p-4 bg-slate-50/80 dark:bg-slate-850 border-b border-slate-100 dark:border-slate-800 gap-2">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold text-xs shadow-sm">
                        <Database className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-sm text-slate-900 dark:text-white">
                            {tableName}
                          </span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 font-semibold">
                            SQL TABLE
                          </span>
                        </div>
                        <span className="text-[11px] text-slate-500 font-mono">
                          Clase JPA: {entity.name}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 font-mono text-[11px]">
                      {pkAttr && (
                        <span className="px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 font-semibold border border-amber-200 dark:border-amber-900/60">
                          PK: {pkAttr.columnName || pkAttr.name}
                        </span>
                      )}
                      <span className="px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                        {attrs.length} cols
                      </span>
                    </div>
                  </div>

                  <div className="p-4 space-y-3">
                    {/* Columns Table */}
                    <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 text-[11px] uppercase border-b border-slate-200 dark:border-slate-800">
                          <tr>
                            <th className="py-2.5 px-3">Columna</th>
                            <th className="py-2.5 px-3">Tipo SQL</th>
                            <th className="py-2.5 px-2 text-center">Clave</th>
                            <th className="py-2.5 px-2 text-center">Nulo</th>
                            <th className="py-2.5 px-2 text-center">Único</th>
                            <th className="py-2.5 px-3">Valor por Defecto</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                          {attrs.map((attr: any, aIdx: number) => {
                            const isPk = !!attr.isPrimaryKey || !!attr.primaryKey;
                            const colName = attr.columnName || attr.name;
                            const sqlType = attr.sqlType || (isPk ? 'BIGINT' : 'VARCHAR(255)');
                            const isFk = attr.hasIndex && colName.endsWith('_id');

                            return (
                              <tr key={aIdx} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                                <td className="py-2 px-3 font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                                  {isPk && <Key className="w-3.5 h-3.5 text-amber-500 shrink-0" />}
                                  <span>{colName}</span>
                                </td>
                                <td className="py-2 px-3 text-purple-600 dark:text-purple-400 font-bold">
                                  {sqlType}
                                </td>
                                <td className="py-2 px-2 text-center">
                                  {isPk ? (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                                      PK
                                    </span>
                                  ) : isFk ? (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                                      FK
                                    </span>
                                  ) : (
                                    <span className="text-slate-400">—</span>
                                  )}
                                </td>
                                <td className="py-2 px-2 text-center">
                                  {attr.nullable ? (
                                    <span className="text-slate-400">NULL</span>
                                  ) : (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                                      NOT NULL
                                    </span>
                                  )}
                                </td>
                                <td className="py-2 px-2 text-center">
                                  {attr.isUnique ? (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                                      UNIQUE
                                    </span>
                                  ) : (
                                    <span className="text-slate-400">—</span>
                                  )}
                                </td>
                                <td className="py-2 px-3 text-slate-500 font-mono text-[11px]">
                                  {attr.defaultValue || (isPk ? 'AUTO_INCREMENT' : '—')}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {/* Constraints Summary */}
                    {rels.some((r: any) => ['MANY_TO_ONE', 'ONE_TO_ONE'].includes(r.relationshipType)) && (
                      <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-[11px] font-mono text-slate-600 dark:text-slate-400 space-y-1">
                        <span className="font-semibold text-slate-700 dark:text-slate-300 block">
                          Restricciones Foráneas Relacionales:
                        </span>
                        {rels
                          .filter((r: any) => ['MANY_TO_ONE', 'ONE_TO_ONE'].includes(r.relationshipType))
                          .map((r: any, rIdx: number) => {
                            const fkCol = r.joinColumnName || `${r.targetEntity.toLowerCase()}_id`;
                            const targetTable = `${r.targetEntity.toLowerCase()}s`;
                            return (
                              <div key={rIdx} className="text-slate-600 dark:text-slate-400">
                                • FOREIGN KEY ({fkCol}) ➔ {targetTable}(id) ON DELETE CASCADE
                              </div>
                            );
                          })}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 2: Visual Seed Data Grid */}
      {activeTab === 'visual-data' && (
        <div className="space-y-4">
          {/* Table Picker & Actions */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Seleccionar Tabla para Inspección:
              </label>
              <select
                value={selectedTable}
                onChange={(e) => setSelectedTable(e.target.value)}
                className="px-3 py-1.5 text-xs font-mono rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {tableNames.map((name) => {
                  const seedCount = parsedSeedData[name.toLowerCase()]?.rows?.length || 1;
                  return (
                    <option key={name} value={name}>
                      {name} ({seedCount} {seedCount === 1 ? 'registro' : 'registros'})
                    </option>
                  );
                })}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopySeedJson}
                disabled={!currentSeedTable}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
              >
                {copiedData ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-500" />
                    <span>Copiado como JSON</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copiar como JSON</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Explanatory Banner */}
          <div className="p-3 rounded-xl bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/50 flex items-start gap-2.5 text-xs text-emerald-900 dark:text-emerald-200">
            <Table className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <strong className="font-semibold block">
                Visualización de Datos Semilla & Fixtures de Prueba (data.sql)
              </strong>
              <p className="text-[11px] text-emerald-700 dark:text-emerald-300 leading-relaxed">
                Muestra los registros prefabricados de prueba extraídos del script relacional DML. Estos registros garantizan precondiciones válidas al arrancar la base de datos en pruebas unitarias y de integración.
              </p>
            </div>
          </div>

          {/* Interactive Data Grid */}
          {currentSeedTable && currentSeedTable.rows.length > 0 ? (
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
              <div className="px-4 py-3 bg-slate-50/80 dark:bg-slate-850 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-slate-900 dark:text-white">
                    Registros en `{selectedTable}`
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold">
                    {currentSeedTable.rows.length} {currentSeedTable.rows.length === 1 ? 'FILA' : 'FILAS'}
                  </span>
                </div>
                <span className="text-[11px] text-slate-500 font-mono">
                  {currentSeedTable.columns.length} columnas
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-700 dark:text-slate-300 uppercase text-[11px] border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3 w-12 text-center text-slate-400">#</th>
                      {currentSeedTable.columns.map((col, idx) => (
                        <th key={idx} className="py-2.5 px-3">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {currentSeedTable.rows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-2.5 px-3 text-center text-slate-400 font-semibold select-none">
                          {rIdx + 1}
                        </td>
                        {row.map((val, cIdx) => (
                          <td key={cIdx} className="py-2.5 px-3 text-slate-800 dark:text-slate-200">
                            {val === 'CURRENT_TIMESTAMP' ? (
                              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 font-bold">
                                🕒 NOW()
                              </span>
                            ) : !isNaN(Number(val)) && val.trim() !== '' ? (
                              <span className="text-blue-600 dark:text-blue-400 font-bold font-mono">
                                {val}
                              </span>
                            ) : val === 'TRUE' || val === 'FALSE' ? (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300">
                                {val}
                              </span>
                            ) : (
                              <span>{val}</span>
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            /* Fallback Grid based on Entity attributes */
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
              <div className="px-4 py-3 bg-slate-50/80 dark:bg-slate-850 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                <span className="font-mono font-bold text-slate-900 dark:text-white">
                  Vista Previa Estructurada de Registros: `{selectedTable}`
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 font-bold">
                  1 REGISTRO DERIVADO
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-700 dark:text-slate-300 uppercase text-[11px] border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3 w-12 text-center text-slate-400">#</th>
                      {(currentEntity?.attributes || []).map((attr: any, idx: number) => (
                        <th key={idx} className="py-2.5 px-3">
                          {attr.columnName || attr.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 text-center text-slate-400 font-semibold select-none">
                        1
                      </td>
                      {(currentEntity?.attributes || []).map((attr: any, idx: number) => {
                        const isPk = !!attr.isPrimaryKey || !!attr.primaryKey;
                        const sampleVal = isPk
                          ? '1'
                          : attr.javaType === 'BigDecimal'
                          ? '99.99'
                          : attr.javaType === 'Instant'
                          ? 'CURRENT_TIMESTAMP'
                          : `Sample ${attr.name}`;
                        return (
                          <td key={idx} className="py-2.5 px-3 text-slate-800 dark:text-slate-200">
                            {sampleVal === 'CURRENT_TIMESTAMP' ? (
                              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 font-bold">
                                🕒 NOW()
                              </span>
                            ) : isPk ? (
                              <span className="text-amber-600 dark:text-amber-400 font-bold">1</span>
                            ) : (
                              <span>{sampleVal}</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: schema.sql (DDL Script) */}
      {activeTab === 'schema-ddl' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Script DDL ANSI / PostgreSQL 16 (Compatible con H2):
            </span>
            {onDownloadSchema && (
              <button
                type="button"
                onClick={onDownloadSchema}
                className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 hover:bg-blue-100 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Descargar schema.sql</span>
              </button>
            )}
          </div>
          <CodeViewer
            code={schemaDdl || '-- Esquema SQL no generado'}
            language="sql"
            filename="src/main/resources/schema.sql"
            maxHeight="max-h-[420px]"
          />
        </div>
      )}

      {/* Tab 4: data.sql (DML Script) */}
      {activeTab === 'seed-dml' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Script DML de Semillas & Fixtures de Datos:
            </span>
            {onDownloadData && (
              <button
                type="button"
                onClick={onDownloadData}
                className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Descargar data.sql</span>
              </button>
            )}
          </div>
          <CodeViewer
            code={seedDml || '-- Semillas SQL no generadas'}
            language="sql"
            filename="src/main/resources/data.sql"
            maxHeight="max-h-[420px]"
          />
        </div>
      )}
    </div>
  );
};

