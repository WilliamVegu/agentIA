import React from 'react';

export function verificationMessage(session?: { executionMode?: string; verificationOutcome?: string; errorMessage?: string } | null) {
  const outcome = session?.verificationOutcome;
  if (outcome === 'OUTDATED') return 'Evidencia obsoleta: las fuentes cambiaron. Reintente la verificación sobre el proyecto actual; no hay aprobación vigente.';
  if (outcome === 'INTERRUPTED') return 'Verificación interrumpida. No se confirma el resultado de las pruebas; puede reintentar.';
  if (outcome === 'FAILED') return 'Pruebas fallidas. El resultado anterior se conserva aunque continúe sin Docker.';
  if (outcome === 'PASSED') return session?.executionMode === 'SOURCE_ONLY' ?
    'Resultado anterior aprobado. No hay nueva ejecución en modo fuentes.' : 'Pruebas de ejecución aprobadas según la evidencia de la sesión.';
  if (session?.executionMode === 'SOURCE_ONLY' || outcome === 'SKIPPED_BY_CHOICE') return 'Ejecución omitida por elección: las pruebas generadas son artefactos, no pruebas ejecutadas.';
  if (outcome === 'ENVIRONMENT_UNAVAILABLE') return 'Ejecución no disponible: reintente o continúe sin Docker desde Despliegue.';
  return 'Verificación pendiente o sin evidencia de ejecución confirmada.';
}

export const VerificationStatus: React.FC<{ session?: Parameters<typeof verificationMessage>[0] }> = ({ session }) => (
  <div role="status" className="p-3 rounded-lg border text-xs space-y-1">
    <p>{verificationMessage(session)}</p>
    {session?.errorMessage && <p>{session.errorMessage}</p>}
  </div>
);
