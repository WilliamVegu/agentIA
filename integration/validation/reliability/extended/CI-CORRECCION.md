# Corrección de GitHub Actions — 2026-10-09

La ejecución 37953693737 sobre 88f8d08 falló en los cuatro jobs Python; ambos frontends aprobaron.

- Linux: siete errores por estudio al comparar hashes de JSON históricos capturados con CRLF contra checkout LF. Se admiten únicamente esas dos representaciones de saltos de línea, conservando la comprobación de contenido y sin recapturar los resultados esperados.
- Windows: las suites de backend aprobaron (1582 Spring / 669 Quarkus); el verificador rechazó el lockfile Gradle publicado porque el manifiesto de revisiones incluía accidentalmente el estado local del archivo, que fue excluido del push. Se retira esa revisión; el hash histórico original del archivo sigue siendo obligatorio. La copia local del usuario se conserva.
- Se aplica el mismo tratamiento LF/CRLF a la identidad del manifiesto histórico. Una regresión comprueba ambas representaciones y rechaza alteraciones de contenido.
- El PYTHONPATH del segundo paso usa GITHUB_WORKSPACE convertido por Python para evitar rutas POSIX de Git Bash en el intérprete Windows.

No se omiten pruebas ni se permiten fallos de jobs. Las vulnerabilidades Java y la falta de saldo DeepSeek permanecen pendientes, ajenas a estos fallos de CI.

Evidencia local: ci-fix-spring.xml, ci-fix-quarkus.xml y ci-fix-integration.xml. La nueva ejecución remota se verifica después del push.

La primera corrección dejó dos comprobaciones finales de inputs históricos con hash crudo; se corrigieron también tras leer el nuevo job Linux. Copias aisladas con todos los JSON convertidos a LF reproducen el checkout Linux y aprueban siete pruebas por estudio (ci-lf-spring.xml / ci-lf-quarkus.xml).
