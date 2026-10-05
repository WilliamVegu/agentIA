import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Lock,
  Edit3,
  Code,
  CheckCircle2,
  ArrowRight,
  Database,
  FileText,
  Key,
  Link2,
  AlertTriangle,
  Plus,
  Trash2,
  Save,
  X,
  Check,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { useQuarkus } from '../../context/QuarkusContext';
import {
  UserStory,
  BddScenario,
  DatabaseModelProposal,
  TableDefinition,
  ColumnDefinition,
  RelationshipDefinition
} from '../../types/quarkusFactory';

// Helpers para regeneración dinámica de ER Diagram y DDL SQL
function generateMermaidEr(tables: TableDefinition[], relationships: RelationshipDefinition[]): string {
  let diagram = 'erDiagram\n';
  tables.forEach((t) => {
    diagram += `    ${t.name.toUpperCase()} {\n`;
    t.columns.forEach((c) => {
      const type = (c.data_type || 'VARCHAR').replace(/[\(\)\s,]/g, '_');
      const pkFk = c.is_primary_key ? 'PK' : c.is_foreign_key ? 'FK' : '';
      diagram += `        ${type} ${c.name} ${pkFk}\n`;
    });
    diagram += '    }\n';
  });
  relationships.forEach((r) => {
    const symbol = r.relation_type === '1:1' ? '||--||' : r.relation_type === 'N:M' ? '}o--o{' : '||--o{';
    diagram += `    ${r.source_table.toUpperCase()} ${symbol} ${r.target_table.toUpperCase()} : "${r.description.replace(/"/g, "'")}"\n`;
  });
  return diagram;
}

function generateDdlSql(tables: TableDefinition[], relationships: RelationshipDefinition[], engine: string): string {
  let sql = `-- Script DDL generado dinámicamente para ${engine}\n\n`;
  tables.forEach((t) => {
    sql += `CREATE TABLE ${t.name} (\n`;
    const colDefs = t.columns.map((c) => {
      let def = `    ${c.name} ${c.data_type || 'VARCHAR(255)'}`;
      if (c.is_primary_key) def += ' PRIMARY KEY';
      else if (!c.is_nullable) def += ' NOT NULL';
      if (c.is_foreign_key && c.references) def += ` REFERENCES ${c.references}`;
      return def;
    });
    sql += colDefs.join(',\n');
    sql += `\n);\n-- ${t.description}\n\n`;
  });
  return sql;
}

export const Step3ContractControl1: React.FC = () => {
  const { currentOrder, approveContract, isLoading, setActiveStep } = useQuarkus();

  const [activeTab, setActiveTab] = useState<'openapi' | 'stories' | 'database'>('openapi');
  const [approvedBy, setApprovedBy] = useState(currentOrder?.control_1_approval_info?.approved_by || '');
  const [comments, setComments] = useState('Contrato OpenAPI, historias de usuario y modelo relacional aprobados.');
  const [isEditingContract, setIsEditingContract] = useState(false);
  const [contractYaml, setContractYaml] = useState(currentOrder?.openapi_contract || '');
  const [confirmDbChecked, setConfirmDbChecked] = useState(true);

  // Estados locales editables para HU y Modelo de BD
  const [stories, setStories] = useState<UserStory[]>(currentOrder?.user_stories || []);
  const [dbModel, setDbModel] = useState<DatabaseModelProposal | null>(currentOrder?.database_model || null);

  // Estado para edición/creación de historias
  const [editingStoryId, setEditingStoryId] = useState<string | null>(null);
  const [editingStory, setEditingStory] = useState<UserStory | null>(null);
  const [isAddingStory, setIsAddingStory] = useState(false);
  const [newStory, setNewStory] = useState<UserStory>({
    id: `HU-${String((currentOrder?.user_stories?.length || 0) + 1).padStart(2, '0')}`,
    title: '',
    role: 'Como usuario del sistema',
    goal: 'quiero realizar una operación de negocio',
    benefit: 'para cumplir con el requerimiento',
    scenarios: [
      {
        title: 'Escenario exitoso',
        given: 'el sistema está disponible y los datos son válidos',
        when: 'se envía la solicitud',
        then: 'se retorna código 200/201 con la respuesta esperada'
      }
    ]
  });

  // Estado para creación/edición de tablas
  const [isAddingTable, setIsAddingTable] = useState(false);
  const [newTableName, setNewTableName] = useState('');
  const [newTableDesc, setNewTableDesc] = useState('');

  // Estado para agregar columnas a una tabla específica
  const [addingColToTable, setAddingColToTable] = useState<string | null>(null);
  const [newCol, setNewCol] = useState<ColumnDefinition>({
    name: '',
    data_type: 'VARCHAR(255)',
    is_primary_key: false,
    is_foreign_key: false,
    references: null,
    is_nullable: true,
    description: ''
  });

  // Estado para agregar relación
  const [isAddingRel, setIsAddingRel] = useState(false);
  const [newRel, setNewRel] = useState<RelationshipDefinition>({
    source_table: '',
    target_table: '',
    relation_type: '1:N',
    description: 'Relación de negocio'
  });

  // Sincronizar estado cuando cargue un nuevo pedido
  useEffect(() => {
    if (currentOrder) {
      setContractYaml(currentOrder.openapi_contract || '');
      setStories(currentOrder.user_stories || []);
      setDbModel(currentOrder.database_model || null);
      if (currentOrder.control_1_approval_info?.approved_by) {
        setApprovedBy(currentOrder.control_1_approval_info.approved_by);
      }
    }
  }, [currentOrder?.id]);

  const isFrozen = currentOrder?.control_1_approved;

  // Actualizar modelo de base de datos y recalcular ER / DDL
  const updateDbModel = (newTables: TableDefinition[], newRels: RelationshipDefinition[]) => {
    if (!dbModel) return;
    const newEr = generateMermaidEr(newTables, newRels);
    const newDdl = generateDdlSql(newTables, newRels, dbModel.database_engine || 'PostgreSQL');
    setDbModel({
      ...dbModel,
      tables: newTables,
      relationships: newRels,
      mermaid_er_diagram: newEr,
      ddl_sql: newDdl
    });
  };

  // Manejadores de Historias de Usuario
  const startEditStory = (story: UserStory) => {
    setEditingStoryId(story.id);
    setEditingStory(JSON.parse(JSON.stringify(story)));
  };

  const saveEditStory = () => {
    if (!editingStory) return;
    setStories(stories.map((s) => (s.id === editingStory.id ? editingStory : s)));
    setEditingStoryId(null);
    setEditingStory(null);
  };

  const handleAddStory = () => {
    if (!newStory.title.trim()) return;
    setStories([...stories, newStory]);
    setIsAddingStory(false);
    setNewStory({
      id: `HU-${String(stories.length + 2).padStart(2, '0')}`,
      title: '',
      role: 'Como usuario del sistema',
      goal: 'quiero realizar una operación',
      benefit: 'para completar el flujo',
      scenarios: [
        {
          title: 'Escenario exitoso',
          given: 'condición inicial válida',
          when: 'se ejecuta la acción',
          then: 'se obtiene el resultado exitoso'
        }
      ]
    });
  };

  const handleDeleteStory = (id: string) => {
    if (confirm(`¿Estás seguro de eliminar la historia ${id}?`)) {
      setStories(stories.filter((s) => s.id !== id));
    }
  };

  // Manejadores de Tablas de Base de Datos
  const handleCreateTable = () => {
    if (!dbModel || !newTableName.trim()) return;
    const cleanName = newTableName.toLowerCase().trim().replace(/[\s-]+/g, '_');
    const defaultCol: ColumnDefinition = {
      name: 'id',
      data_type: 'UUID',
      is_primary_key: true,
      is_foreign_key: false,
      references: null,
      is_nullable: false,
      description: 'Identificador único (PK)'
    };
    const createdTable: TableDefinition = {
      name: cleanName,
      description: newTableDesc.trim() || `Tabla para gestión de ${cleanName}`,
      columns: [defaultCol]
    };
    updateDbModel([...dbModel.tables, createdTable], dbModel.relationships);
    setNewTableName('');
    setNewTableDesc('');
    setIsAddingTable(false);
  };

  const handleDeleteTable = (tableName: string) => {
    if (!dbModel) return;
    if (confirm(`¿Eliminar la tabla "${tableName}" y sus relaciones asociadas?`)) {
      const remainingTables = dbModel.tables.filter((t) => t.name !== tableName);
      const remainingRels = dbModel.relationships.filter(
        (r) => r.source_table !== tableName && r.target_table !== tableName
      );
      updateDbModel(remainingTables, remainingRels);
    }
  };

  const handleAddColumnToTable = (tableName: string) => {
    if (!dbModel || !newCol.name.trim()) return;
    const cleanColName = newCol.name.toLowerCase().trim().replace(/[\s-]+/g, '_');
    const colToAdd: ColumnDefinition = {
      ...newCol,
      name: cleanColName,
      references: newCol.is_foreign_key ? newCol.references : null
    };

    const updatedTables = dbModel.tables.map((t) => {
      if (t.name === tableName) {
        return {
          ...t,
          columns: [...t.columns, colToAdd]
        };
      }
      return t;
    });

    updateDbModel(updatedTables, dbModel.relationships);
    setAddingColToTable(null);
    setNewCol({
      name: '',
      data_type: 'VARCHAR(255)',
      is_primary_key: false,
      is_foreign_key: false,
      references: null,
      is_nullable: true,
      description: ''
    });
  };

  const handleDeleteColumn = (tableName: string, colName: string) => {
    if (!dbModel) return;
    const updatedTables = dbModel.tables.map((t) => {
      if (t.name === tableName) {
        return {
          ...t,
          columns: t.columns.filter((c) => c.name !== colName)
        };
      }
      return t;
    });
    updateDbModel(updatedTables, dbModel.relationships);
  };

  const handleAddRelationship = () => {
    if (!dbModel || !newRel.source_table || !newRel.target_table) return;
    updateDbModel(dbModel.tables, [...dbModel.relationships, newRel]);
    setIsAddingRel(false);
    setNewRel({
      source_table: '',
      target_table: '',
      relation_type: '1:N',
      description: 'Relación de negocio'
    });
  };

  const handleDeleteRelationship = (idx: number) => {
    if (!dbModel) return;
    const updatedRels = dbModel.relationships.filter((_, i) => i !== idx);
    updateDbModel(dbModel.tables, updatedRels);
  };

  const handleApprove = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!approvedBy.trim()) {
      alert('Por favor ingresa tu nombre y rol como aprobador responsable.');
      return;
    }
    await approveContract(
      approvedBy,
      comments,
      isEditingContract ? contractYaml : undefined,
      confirmDbChecked,
      stories,
      dbModel || undefined
    );
  };

  if (!currentOrder || !currentOrder.openapi_contract) {
    return (
      <div className="text-center p-8 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <p className="text-sm text-slate-500">El contrato OpenAPI aún no ha sido redactado. Ingresa los requerimientos en el Paso 1.</p>
        <button
          onClick={() => setActiveStep(0)}
          className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-semibold"
        >
          Ir al Paso 1: Pedido & Arquetipo
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Banner de Control Humano 1 */}
      <div className="bg-gradient-to-r from-amber-500/15 via-amber-500/5 to-transparent border-l-4 border-amber-500 p-4 rounded-r-xl flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-amber-500 text-white shrink-0 mt-0.5 shadow-sm">
            <Lock className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Control Humano 1: Revisión, Edición y Congelación de Contrato OpenAPI, Historias BDD y Modelo de Base de Datos
              </h3>
              <span className="text-[10px] bg-amber-500 text-white px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
                Compuerta Obligatoria
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
              <strong>Principio Contract-First Dinámico:</strong> Cada cambio que realices o edites en el contrato OpenAPI o en el modelo relacional
              es <strong>interpretado por la IA en tiempo real</strong> para derivar automáticamente las APIs JAX-RS/RESTEasy, los DTOs inmutables (Java 21 Records)
              y las entidades Panache. Una vez aprobado, el contrato queda congelado.
            </p>
          </div>
        </div>

        {isFrozen && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 text-xs font-bold shrink-0">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>ARTEFACTOS CONGELADOS</span>
          </div>
        )}
      </div>

      {/* TABS DE REVISIÓN Y EDICIÓN */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800">
        <button
          type="button"
          onClick={() => setActiveTab('openapi')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
            activeTab === 'openapi'
              ? 'border-red-600 text-red-600 dark:text-red-400 bg-red-50/50 dark:bg-red-950/20'
              : 'border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <Code className="w-4 h-4" />
          <span>Contrato OpenAPI 3.1 (YAML)</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('stories')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
            activeTab === 'stories'
              ? 'border-red-600 text-red-600 dark:text-red-400 bg-red-50/50 dark:bg-red-950/20'
              : 'border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Historias de Usuario BDD ({stories.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('database')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
            activeTab === 'database'
              ? 'border-red-600 text-red-600 dark:text-red-400 bg-red-50/50 dark:bg-red-950/20'
              : 'border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Modelo de BD & Diagrama ER ({dbModel?.tables?.length || 0} Tablas)</span>
        </button>
      </div>

      {/* CONTENIDO DEL TAB 1: CONTRATO OPENAPI */}
      {activeTab === 'openapi' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500 dark:text-slate-400">
              Especificación OpenAPI 3.1.0 · Contrato congelable de interfaces JAX-RS y modelos DTO.
            </span>
            {!isFrozen && (
              <div className="flex items-center gap-2">
                {isEditingContract ? (
                  <button
                    type="button"
                    onClick={() => setIsEditingContract(false)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 transition-all"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Guardar Edición YAML</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsEditingContract(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold transition-all"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    <span>Editar YAML</span>
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="bg-slate-900 text-slate-100 rounded-xl p-4 font-mono text-xs border border-slate-800 shadow-inner overflow-hidden">
            {isEditingContract ? (
              <textarea
                rows={22}
                value={contractYaml}
                onChange={(e) => setContractYaml(e.target.value)}
                className="w-full bg-slate-950 text-emerald-400 font-mono text-xs p-3 rounded-lg border border-slate-700 outline-none focus:ring-2 focus:ring-emerald-500"
              />
            ) : (
              <pre className="max-h-[500px] overflow-auto leading-relaxed select-all">
                {contractYaml}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* CONTENIDO DEL TAB 2: HISTORIAS DE USUARIO BDD */}
      {activeTab === 'stories' && (
        <div className="space-y-4">
          <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 rounded-xl p-4 flex items-start justify-between gap-4">
            <div>
              <h4 className="text-xs font-bold text-blue-900 dark:text-blue-200">
                Validación Funcional: Historias de Usuario con Criterios de Aceptación BDD
              </h4>
              <p className="text-xs text-blue-800/80 dark:text-blue-300/80 mt-1">
                Generadas dinámicamente por la IA para tu pedido. Puedes <strong>modificar textos</strong>, <strong>añadir nuevas historias</strong> o <strong>eliminar</strong> historias que no apliquen.
              </p>
            </div>
            {!isFrozen && (
              <button
                type="button"
                onClick={() => setIsAddingStory(!isAddingStory)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shrink-0 shadow-sm transition-all"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>{isAddingStory ? 'Cancelar Nueva' : 'Añadir Historia de Usuario'}</span>
              </button>
            )}
          </div>

          {/* Formulario para Añadir Nueva Historia */}
          {isAddingStory && (
            <div className="bg-blue-50/50 dark:bg-blue-950/20 border-2 border-blue-300 dark:border-blue-800 rounded-xl p-4 space-y-3">
              <h5 className="text-xs font-bold text-blue-900 dark:text-blue-200 uppercase tracking-wider flex items-center gap-2">
                <Plus className="w-4 h-4" />
                <span>Nueva Historia de Usuario</span>
              </h5>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
                <div>
                  <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">ID</label>
                  <input
                    type="text"
                    value={newStory.id}
                    onChange={(e) => setNewStory({ ...newStory, id: e.target.value })}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-xs"
                  />
                </div>
                <div className="md:col-span-3">
                  <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Título</label>
                  <input
                    type="text"
                    placeholder="Ej: Registrar nuevo pedido de cliente"
                    value={newStory.title}
                    onChange={(e) => setNewStory({ ...newStory, title: e.target.value })}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Rol</label>
                  <input
                    type="text"
                    placeholder="Como [rol]"
                    value={newStory.role}
                    onChange={(e) => setNewStory({ ...newStory, role: e.target.value })}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Objetivo</label>
                  <input
                    type="text"
                    placeholder="quiero [hacer tal acción]"
                    value={newStory.goal}
                    onChange={(e) => setNewStory({ ...newStory, goal: e.target.value })}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                  />
                </div>
                <div>
                  <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Beneficio</label>
                  <input
                    type="text"
                    placeholder="para [obtener este beneficio]"
                    value={newStory.benefit}
                    onChange={(e) => setNewStory({ ...newStory, benefit: e.target.value })}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsAddingStory(false)}
                  className="px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleAddStory}
                  disabled={!newStory.title.trim()}
                  className="px-4 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold disabled:opacity-50"
                >
                  Guardar Historia
                </button>
              </div>
            </div>
          )}

          {/* Listado de Historias */}
          <div className="grid grid-cols-1 gap-4">
            {stories.map((story) => {
              const isItemEditing = editingStoryId === story.id;
              const currentItem = isItemEditing && editingStory ? editingStory : story;

              return (
                <div
                  key={story.id}
                  className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-sm space-y-3"
                >
                  <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 font-mono font-bold text-xs">
                        {story.id}
                      </span>
                      {isItemEditing ? (
                        <input
                          type="text"
                          value={currentItem.title}
                          onChange={(e) =>
                            setEditingStory(editingStory ? { ...editingStory, title: e.target.value } : null)
                          }
                          className="px-2 py-1 text-sm font-bold border rounded bg-white dark:bg-slate-800 border-blue-400"
                        />
                      ) : (
                        <h5 className="text-sm font-bold text-slate-800 dark:text-slate-200">{story.title}</h5>
                      )}
                    </div>

                    {!isFrozen && (
                      <div className="flex items-center gap-2">
                        {isItemEditing ? (
                          <>
                            <button
                              type="button"
                              onClick={saveEditStory}
                              className="flex items-center gap-1 px-2.5 py-1 bg-emerald-600 text-white rounded text-xs font-semibold hover:bg-emerald-700"
                            >
                              <Save className="w-3 h-3" />
                              <span>Guardar</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingStoryId(null);
                                setEditingStory(null);
                              }}
                              className="p-1 text-slate-500 hover:text-slate-700"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={() => startEditStory(story)}
                              className="p-1.5 text-slate-500 hover:text-blue-600 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
                              title="Editar Historia"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteStory(story.id)}
                              className="p-1.5 text-slate-400 hover:text-red-600 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
                              title="Eliminar Historia"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </div>

                  {isItemEditing ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-500">Rol</label>
                        <input
                          type="text"
                          value={currentItem.role}
                          onChange={(e) =>
                            setEditingStory(editingStory ? { ...editingStory, role: e.target.value } : null)
                          }
                          className="w-full p-1.5 border rounded bg-white dark:bg-slate-800"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-500">Objetivo</label>
                        <input
                          type="text"
                          value={currentItem.goal}
                          onChange={(e) =>
                            setEditingStory(editingStory ? { ...editingStory, goal: e.target.value } : null)
                          }
                          className="w-full p-1.5 border rounded bg-white dark:bg-slate-800"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-500">Beneficio</label>
                        <input
                          type="text"
                          value={currentItem.benefit}
                          onChange={(e) =>
                            setEditingStory(editingStory ? { ...editingStory, benefit: e.target.value } : null)
                          }
                          className="w-full p-1.5 border rounded bg-white dark:bg-slate-800"
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-700 dark:text-slate-300 space-y-1 bg-slate-50 dark:bg-slate-800/50 p-3 rounded-lg border border-slate-200/60 dark:border-slate-800/60">
                      <p><strong className="text-slate-900 dark:text-white">{story.role}</strong>,</p>
                      <p><strong>{story.goal}</strong>,</p>
                      <p className="text-slate-600 dark:text-slate-400"><strong>{story.benefit}</strong>.</p>
                    </div>
                  )}

                  {currentItem.scenarios && currentItem.scenarios.length > 0 && (
                    <div className="space-y-2 pt-1">
                      <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
                        Criterios de Aceptación BDD (Given / When / Then):
                      </span>
                      {currentItem.scenarios.map((sc, i) => (
                        <div key={i} className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-xs space-y-1">
                          <span className="font-semibold text-slate-900 dark:text-slate-100 block mb-1">
                            📌 {sc.title}
                          </span>
                          <div className="grid grid-cols-1 gap-1 text-[11px]">
                            <p><span className="font-bold text-emerald-600 dark:text-emerald-400">GIVEN:</span> {sc.given}</p>
                            <p><span className="font-bold text-blue-600 dark:text-blue-400">WHEN:</span> {sc.when}</p>
                            <p><span className="font-bold text-purple-600 dark:text-purple-400">THEN:</span> {sc.then}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* CONTENIDO DEL TAB 3: MODELO DE BASE DE DATOS & DIAGRAMA ER */}
      {activeTab === 'database' && (
        <div className="space-y-5">
          {dbModel ? (
            <>
              {/* Resumen del motor y botones de acción */}
              <div className="bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-900 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div>
                  <h4 className="text-xs font-bold text-purple-900 dark:text-purple-200 flex items-center gap-2">
                    <Database className="w-4 h-4 text-purple-600" />
                    <span>Diseño de Base de Datos Relacional: {dbModel.database_engine}</span>
                  </h4>
                  <p className="text-xs text-purple-800/80 dark:text-purple-300/80 mt-1">
                    Estructura relacional con claves primarias y foráneas garantizadas. Puedes <strong>añadir o quitar tablas</strong>, 
                    <strong>agregar campos</strong> o <strong>establecer relaciones</strong> para adaptar el modelo al pedido.
                  </p>
                </div>
                {!isFrozen && (
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => setIsAddingTable(!isAddingTable)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-semibold transition-all shadow-sm"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>{isAddingTable ? 'Cancelar Tabla' : 'Nueva Tabla'}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsAddingRel(!isAddingRel)}
                      className="flex items-center gap-1.5 px-3 py-1.5 border border-purple-300 dark:border-purple-700 text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/30 rounded-lg text-xs font-semibold transition-all"
                    >
                      <Link2 className="w-3.5 h-3.5" />
                      <span>{isAddingRel ? 'Cancelar Relación' : 'Nueva Relación'}</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Formulario para añadir nueva tabla */}
              {isAddingTable && (
                <div className="p-4 bg-purple-50/50 dark:bg-purple-950/20 border-2 border-purple-300 dark:border-purple-800 rounded-xl space-y-3">
                  <h5 className="text-xs font-bold text-purple-900 dark:text-purple-200 uppercase tracking-wider flex items-center gap-2">
                    <Plus className="w-4 h-4" />
                    <span>Crear Nueva Tabla Relacional</span>
                  </h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div>
                      <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Nombre de la Tabla</label>
                      <input
                        type="text"
                        placeholder="Ej: order_items, payments, customers"
                        value={newTableName}
                        onChange={(e) => setNewTableName(e.target.value)}
                        className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-xs"
                      />
                    </div>
                    <div>
                      <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Descripción / Propósito</label>
                      <input
                        type="text"
                        placeholder="Ej: Registro de líneas de detalle por pedido"
                        value={newTableDesc}
                        onChange={(e) => setNewTableDesc(e.target.value)}
                        className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setIsAddingTable(false)}
                      className="px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      onClick={handleCreateTable}
                      disabled={!newTableName.trim()}
                      className="px-4 py-1.5 text-xs bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-semibold disabled:opacity-50"
                    >
                      Crear Tabla (Con PK id UUID)
                    </button>
                  </div>
                </div>
              )}

              {/* Formulario para añadir nueva relación */}
              {isAddingRel && (
                <div className="p-4 bg-blue-50/50 dark:bg-blue-950/20 border-2 border-blue-300 dark:border-blue-800 rounded-xl space-y-3">
                  <h5 className="text-xs font-bold text-blue-900 dark:text-blue-200 uppercase tracking-wider flex items-center gap-2">
                    <Link2 className="w-4 h-4" />
                    <span>Establecer Nueva Relación entre Tablas</span>
                  </h5>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
                    <div>
                      <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Tabla Origen</label>
                      <select
                        value={newRel.source_table}
                        onChange={(e) => setNewRel({ ...newRel, source_table: e.target.value })}
                        className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-xs"
                      >
                        <option value="">-- Seleccionar --</option>
                        {dbModel.tables.map((t) => (
                          <option key={t.name} value={t.name}>{t.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Cardinalidad</label>
                      <select
                        value={newRel.relation_type}
                        onChange={(e) => setNewRel({ ...newRel, relation_type: e.target.value })}
                        className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-xs"
                      >
                        <option value="1:N">1:N (Uno a Varios)</option>
                        <option value="1:1">1:1 (Uno a Uno)</option>
                        <option value="N:M">N:M (Muchos a Muchos)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Tabla Destino</label>
                      <select
                        value={newRel.target_table}
                        onChange={(e) => setNewRel({ ...newRel, target_table: e.target.value })}
                        className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-xs"
                      >
                        <option value="">-- Seleccionar --</option>
                        {dbModel.tables.map((t) => (
                          <option key={t.name} value={t.name}>{t.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block font-semibold mb-1 text-slate-700 dark:text-slate-300">Descripción</label>
                      <input
                        type="text"
                        placeholder="Ej: Un pedido contiene ítems"
                        value={newRel.description}
                        onChange={(e) => setNewRel({ ...newRel, description: e.target.value })}
                        className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => setIsAddingRel(false)}
                      className="px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      onClick={handleAddRelationship}
                      disabled={!newRel.source_table || !newRel.target_table}
                      className="px-4 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold disabled:opacity-50"
                    >
                      Guardar Relación
                    </button>
                  </div>
                </div>
              )}

              {/* Visor de Tablas y Columnas */}
              <div className="space-y-4">
                <h5 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider flex items-center justify-between">
                  <span>Tablas y Campos Relacionales ({dbModel.tables.length})</span>
                </h5>

                <div className="grid grid-cols-1 gap-4">
                  {dbModel.tables.map((table) => (
                    <div
                      key={table.name}
                      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm"
                    >
                      <div className="bg-slate-100 dark:bg-slate-800 px-4 py-2.5 flex items-center justify-between border-b border-slate-200 dark:border-slate-700">
                        <div className="flex items-center gap-2">
                          <Database className="w-4 h-4 text-purple-600" />
                          <span className="font-mono font-bold text-xs text-slate-900 dark:text-white">
                            {table.name}
                          </span>
                          <span className="text-[11px] text-slate-500 italic">· {table.description}</span>
                        </div>
                        {!isFrozen && (
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => setAddingColToTable(addingColToTable === table.name ? null : table.name)}
                              className="flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300 font-semibold hover:bg-purple-200"
                            >
                              <Plus className="w-3 h-3" />
                              <span>Añadir Columna</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteTable(table.name)}
                              className="p-1 text-slate-400 hover:text-red-600 rounded hover:bg-slate-200 dark:hover:bg-slate-700"
                              title="Eliminar Tabla"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Formulario para añadir columna a esta tabla */}
                      {addingColToTable === table.name && (
                        <div className="p-3 bg-purple-50/40 dark:bg-purple-950/20 border-b border-purple-200 dark:border-purple-800 space-y-2 text-xs">
                          <span className="font-bold text-[11px] text-purple-900 dark:text-purple-300 uppercase tracking-wider block">
                            Añadir Columna a "{table.name}"
                          </span>
                          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-6 gap-2">
                            <div className="md:col-span-2">
                              <label className="block text-[10px] text-slate-500">Nombre Columna</label>
                              <input
                                type="text"
                                placeholder="Ej: total_amount"
                                value={newCol.name}
                                onChange={(e) => setNewCol({ ...newCol, name: e.target.value })}
                                className="w-full p-1.5 border rounded bg-white dark:bg-slate-900 font-mono text-xs"
                              />
                            </div>
                            <div>
                              <label className="block text-[10px] text-slate-500">Tipo de Dato</label>
                              <select
                                value={newCol.data_type}
                                onChange={(e) => setNewCol({ ...newCol, data_type: e.target.value })}
                                className="w-full p-1.5 border rounded bg-white dark:bg-slate-900 font-mono text-xs"
                              >
                                <option value="VARCHAR(255)">VARCHAR(255)</option>
                                <option value="UUID">UUID</option>
                                <option value="INT">INT</option>
                                <option value="BIGINT">BIGINT</option>
                                <option value="DECIMAL(10,2)">DECIMAL(10,2)</option>
                                <option value="BOOLEAN">BOOLEAN</option>
                                <option value="TIMESTAMP">TIMESTAMP</option>
                                <option value="TEXT">TEXT</option>
                              </select>
                            </div>
                            <div>
                              <label className="block text-[10px] text-slate-500">Restricción</label>
                              <div className="flex items-center gap-2 pt-1.5">
                                <label className="flex items-center gap-1 text-[11px] cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={newCol.is_primary_key}
                                    onChange={(e) => setNewCol({ ...newCol, is_primary_key: e.target.checked })}
                                  />
                                  <span>PK</span>
                                </label>
                                <label className="flex items-center gap-1 text-[11px] cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={newCol.is_foreign_key}
                                    onChange={(e) => setNewCol({ ...newCol, is_foreign_key: e.target.checked })}
                                  />
                                  <span>FK</span>
                                </label>
                                <label className="flex items-center gap-1 text-[11px] cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={!newCol.is_nullable}
                                    onChange={(e) => setNewCol({ ...newCol, is_nullable: !e.target.checked })}
                                  />
                                  <span>Not Null</span>
                                </label>
                              </div>
                            </div>
                            <div className="md:col-span-2">
                              <label className="block text-[10px] text-slate-500">
                                {newCol.is_foreign_key ? 'Referencia FK (tabla.campo)' : 'Descripción'}
                              </label>
                              <input
                                type="text"
                                placeholder={newCol.is_foreign_key ? 'orders(id)' : 'Descripción del campo'}
                                value={newCol.is_foreign_key ? (newCol.references || '') : newCol.description}
                                onChange={(e) => {
                                  if (newCol.is_foreign_key) {
                                    setNewCol({ ...newCol, references: e.target.value });
                                  } else {
                                    setNewCol({ ...newCol, description: e.target.value });
                                  }
                                }}
                                className="w-full p-1.5 border rounded bg-white dark:bg-slate-900 text-xs"
                              />
                            </div>
                          </div>
                          <div className="flex justify-end gap-2 pt-1">
                            <button
                              type="button"
                              onClick={() => setAddingColToTable(null)}
                              className="px-2.5 py-1 text-xs rounded border hover:bg-slate-100 dark:hover:bg-slate-800"
                            >
                              Cancelar
                            </button>
                            <button
                              type="button"
                              onClick={() => handleAddColumnToTable(table.name)}
                              disabled={!newCol.name.trim()}
                              className="px-3 py-1 text-xs bg-purple-600 hover:bg-purple-700 text-white rounded font-semibold disabled:opacity-50"
                            >
                              Guardar Campo
                            </button>
                          </div>
                        </div>
                      )}

                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead>
                            <tr className="bg-slate-50 dark:bg-slate-800/40 text-slate-500 font-semibold border-b border-slate-200 dark:border-slate-800">
                              <th className="py-2 px-3">Columna</th>
                              <th className="py-2 px-3">Tipo de Dato</th>
                              <th className="py-2 px-3">Claves / Restricciones</th>
                              <th className="py-2 px-3">Nulable</th>
                              <th className="py-2 px-3">Descripción</th>
                              {!isFrozen && <th className="py-2 px-3 text-right">Acción</th>}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                            {table.columns.map((col) => (
                              <tr key={col.name} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                                <td className="py-2 px-3 font-mono font-bold text-slate-800 dark:text-slate-200">
                                  {col.name}
                                </td>
                                <td className="py-2 px-3 font-mono text-purple-600 dark:text-purple-400">
                                  {col.data_type}
                                </td>
                                <td className="py-2 px-3">
                                  <div className="flex items-center gap-1.5">
                                    {col.is_primary_key && (
                                      <span className="px-1.5 py-0.5 bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 rounded text-[10px] font-bold flex items-center gap-1">
                                        <Key className="w-2.5 h-2.5" /> PK
                                      </span>
                                    )}
                                    {col.is_foreign_key && (
                                      <span className="px-1.5 py-0.5 bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded text-[10px] font-bold flex items-center gap-1">
                                        <Link2 className="w-2.5 h-2.5" /> FK → {col.references || ''}
                                      </span>
                                    )}
                                  </div>
                                </td>
                                <td className="py-2 px-3 text-slate-500">
                                  {col.is_nullable ? 'SÍ' : 'NO (NOT NULL)'}
                                </td>
                                <td className="py-2 px-3 text-slate-600 dark:text-slate-400 text-[11px]">
                                  {col.description}
                                </td>
                                {!isFrozen && (
                                  <td className="py-2 px-3 text-right">
                                    {/* Evitar eliminar la PK id principal si solo queda una */}
                                    {!(col.is_primary_key && table.columns.length === 1) && (
                                      <button
                                        type="button"
                                        onClick={() => handleDeleteColumn(table.name, col.name)}
                                        className="p-1 text-slate-400 hover:text-red-600 rounded"
                                        title="Eliminar Campo"
                                      >
                                        <Trash2 className="w-3 h-3" />
                                      </button>
                                    )}
                                  </td>
                                )}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Relaciones entre Tablas */}
              {dbModel.relationships && dbModel.relationships.length > 0 && (
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
                  <h5 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Link2 className="w-4 h-4 text-blue-500" />
                      <span>Relaciones y Cardinalidad ({dbModel.relationships.length})</span>
                    </span>
                  </h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {dbModel.relationships.map((rel, idx) => (
                      <div key={idx} className="p-3 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 text-xs flex items-center justify-between">
                        <div>
                          <div className="flex items-center gap-2 font-mono font-bold text-slate-900 dark:text-white mb-1">
                            <span>{rel.source_table}</span>
                            <span className="px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-[10px]">
                              {rel.relation_type}
                            </span>
                            <span>{rel.target_table}</span>
                          </div>
                          <p className="text-slate-600 dark:text-slate-400 text-[11px]">{rel.description}</p>
                        </div>
                        {!isFrozen && (
                          <button
                            type="button"
                            onClick={() => handleDeleteRelationship(idx)}
                            className="p-1 text-slate-400 hover:text-red-600 rounded ml-2"
                            title="Eliminar Relación"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Diagrama Mermaid ER Dinámico */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-2">
                <div className="flex items-center justify-between">
                  <h5 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                    Diagrama Entidad-Relación Dinámico (Mermaid erDiagram)
                  </h5>
                  <span className="text-[10px] text-slate-500 font-mono">Actualizado en vivo</span>
                </div>
                <pre className="p-3 bg-slate-950 text-emerald-400 font-mono text-xs rounded-lg overflow-x-auto border border-slate-800">
                  {dbModel.mermaid_er_diagram}
                </pre>
              </div>

              {/* Script DDL SQL Dinámico */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-2">
                <div className="flex items-center justify-between">
                  <h5 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                    Script DDL de Creación de Tablas ({dbModel.database_engine})
                  </h5>
                  <span className="text-[10px] text-slate-500 font-mono">Sincronizado con entidades Panache</span>
                </div>
                <pre className="p-3 bg-slate-950 text-slate-200 font-mono text-xs rounded-lg overflow-x-auto border border-slate-800 max-h-64">
                  {dbModel.ddl_sql}
                </pre>
              </div>

              {/* Criterios de Validación */}
              {dbModel.validation_notes && (
                <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs space-y-1">
                  <span className="font-bold text-emerald-800 dark:text-emerald-300">
                    Criterios de Arquitectura y Normalización Verificados:
                  </span>
                  <ul className="list-disc list-inside text-emerald-700 dark:text-emerald-400 text-[11px] space-y-0.5">
                    {dbModel.validation_notes.map((note, idx) => (
                      <li key={idx}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="p-6 text-center text-xs text-slate-500 bg-white dark:bg-slate-900 rounded-xl border">
              No hay modelo de base de datos generado aún. Completa el Paso 2 de aclaración.
            </div>
          )}
        </div>
      )}

      {/* FORMULARIO DE APROBACIÓN CONTROL 1 */}
      {!isFrozen ? (
        <form onSubmit={handleApprove} className="bg-white dark:bg-slate-900 border-2 border-amber-500/40 rounded-xl p-5 shadow-md space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-2">
            <ShieldCheck className="w-5 h-5 text-amber-500" />
            <h4 className="text-sm font-bold text-slate-900 dark:text-white">
              Aprobación Formal de Control Humano 1
            </h4>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Aprobado por (Nombre y Rol del Usuario) *
              </label>
              <input
                type="text"
                placeholder="Ej: Benjamin (Arquitecto de Software / Líder Técnico)"
                value={approvedBy}
                onChange={(e) => setApprovedBy(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-amber-500"
                required
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Comentarios u Observaciones de la Aprobación
              </label>
              <input
                type="text"
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </div>

          {/* Confirmación explícita del modelo relacional */}
          <div className="pt-1">
            <label className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 cursor-pointer">
              <input
                type="checkbox"
                checked={confirmDbChecked}
                onChange={(e) => setConfirmDbChecked(e.target.checked)}
                className="rounded text-amber-600 focus:ring-amber-500 w-4 h-4"
              />
              <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                Confirmo que las tablas relacionales ({dbModel?.tables?.length || 0}), historias ({stories.length}) y el contrato OpenAPI representan fielmente mi pedido y autorizo congelar el diseño.
              </span>
            </label>
          </div>

          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={() => setActiveStep(1)}
              className="px-4 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
            >
              ← Volver a Aclaración
            </button>

            <button
              type="submit"
              disabled={isLoading || !confirmDbChecked || !approvedBy.trim()}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-bold text-sm shadow-lg hover:shadow-amber-600/30 transition-all disabled:opacity-50"
            >
              {isLoading ? (
                <span>Congelando diseño y activando Agente Arquitecto...</span>
              ) : (
                <>
                  <Lock className="w-4 h-4" />
                  <span>Aprobar y Congelar Contrato, Historias y Modelo Relacional</span>
                </>
              )}
            </button>
          </div>
        </form>
      ) : (
        <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-800 rounded-xl p-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-6 h-6 text-emerald-600" />
            <div>
              <h4 className="text-sm font-bold text-emerald-950 dark:text-emerald-200">
                Control 1 Aprobado Formalmente
              </h4>
              <p className="text-xs text-emerald-800 dark:text-emerald-400 mt-0.5">
                Aprobado por: <strong>{currentOrder.control_1_approval_info?.approved_by}</strong> · Contrato OpenAPI, Historias BDD y Modelo de BD congelados.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setActiveStep(3)}
            className="flex items-center gap-1.5 px-5 py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold shadow-md transition-all"
          >
            <span>Avanzar al Paso 4: Arquitectura</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};
