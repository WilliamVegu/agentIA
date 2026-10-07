# Validación de la integración — 7 de octubre de 2026

La rama `dual-systems-selector` contiene Spring Boot en la raíz y el Studio Quarkus recuperado de `5d9b190`, con las plantillas nativas de `c5bda02` integradas y corregidas en `systems/quarkus/`. `Quarkus_refact_2` sigue siendo una fuente Spring Boot; el análisis está en los informes del directorio superior.

La copia autorizada de Spring se verificó contra el checkout original: 1.446 archivos idénticos byte a byte, incluidos los cambios locales solicitados. `source-snapshots.json` registra las huellas finales de 573 archivos Quarkus y su base de recuperación; `integration/verify_sources.py` comprobó ambos conjuntos. El checkout original avanzó a un commit nuevo durante la revisión; la copia autorizada ya tomada para la rama nueva no se alteró.

Las seis pruebas del lanzador y 53 comprobaciones de navegador pasaron. El navegador abrió ambos estudios, recorrió sus diez pestañas, comprobó la separación de datos y recuperó las especificaciones tras reiniciar. La interfaz Quarkus superó 65 pruebas y el build de producción. Su backend superó 533 pruebas, con tres omitidas, y 27 pruebas focalizadas tras las últimas correcciones.

La API Quarkus completó un pipeline offline y entregó un ZIP con fuentes nativas, sin atribuir pruebas Java ejecutadas a ese pipeline. El proyecto Java generado se compiló con Maven 3.9.11 y Java 21; sus seis pruebas Maven aprobaron. El servicio generado arrancó y respondió a salud, creación y lectura; la comprobación HTTP completa se interrumpió al usar una especificación de prueba que declaraba opcional un campo esperado como obligatorio. El script de prueba quedó corregido, pero esa segunda comprobación HTTP no quedó terminada antes del push.

Spring Boot conserva sus fuentes. Su suite heredada registró 1.409 aprobadas, 58 fallidas y 42 omitidas; la interfaz tuvo 105 aprobadas. No se atribuyen esas fallas a cambios de esta rama. No se verificaron proveedores IA externos ni despliegue real con Docker. El Studio Quarkus recuperado conserva acceso demo local, sin autenticación de servidor.
