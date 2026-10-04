import type { ExecutionMode } from '../../services/sessionService';

export function ExecutionModeSelector({ value, onChange }: { value: ExecutionMode; onChange: (value: ExecutionMode) => void }) {
  return <label className="block text-sm space-y-2">
    <span className="font-semibold">Ejecución de este microservicio</span>
    <select aria-label="Ejecución de este microservicio" className="block w-full rounded border p-2 dark:bg-slate-800" value={value} onChange={e => onChange(e.target.value as ExecutionMode)}>
      <option value="SOURCE_ONLY">Sin Docker — generar y exportar fuentes</option>
      <option value="DOCKER">Con Docker — compilar, probar y desplegar</option>
    </select>
    <span className="block text-xs text-slate-500">Sin Docker permite terminar en laboratorios sin virtualización. Las pruebas de ejecución figurarán como no ejecutadas.</span>
  </label>;
}
