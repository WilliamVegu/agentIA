# Estado de la validación de integración — 7 de octubre de 2026

**Borrador local, sin publicación.** Ver [comparación de ramas](../COMPARACION_RAMAS_QUARKUS.md): `Quarkus_refact_2` contiene Spring Boot; `Quarkus_refact` contiene Quarkus con fallos reproducidos. El selector inicial y el lanzador están creados, pero la fuente Quarkus definitiva todavía no se ha sustituido.

La copia inicial conservó 1446 archivos Spring Boot actuales y 1171 archivos regulares de `Quarkus_refact_2`; el gitlink histórico de esta última también se conserva en el índice. El árbol Git importado de esta fuente tiene hash `21cc702345e6de04d69ebf21e8e66bd4947f0476`, idéntico a su origen. La verificación de huellas pasa después de las suites.

Validación del nuevo código: seis pruebas del lanzador aprobadas; 53 comprobaciones de navegador del selector y dos copias Spring aprobadas; cinco puertos cerrados al terminar el apagado; especificaciones propias persistidas después de reiniciar, ausentes en la otra copia. El selector se comprobó a 1440 y 390 píxeles de ancho.

Los conteos completos de las suites están en `suite-counts.json`. Hay fallos en las suites heredadas, y la fábrica real Quarkus tiene problemas funcionales descritos y reproducidos en la comparación. No se afirma aprobación integral de ambos sistemas.

Las pruebas no modificaron las fuentes de las aplicaciones ni publicaron el borrador. Las sesiones de prueba y los ZIP de auditoría son datos nuevos de las copias aisladas. Las comprobaciones reales de proveedor IA, compilación Java, Docker y publicación Git quedan fuera de la evidencia obtenida.
