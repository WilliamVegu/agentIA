FROM agentia-builder:d88bfa15cfd91d25b40dd518 AS build
WORKDIR /workspace
COPY . .
WORKDIR /workspace
RUN --network=none mkdir -p /tmp/m2 && cp -R /opt/agentia-cache/. /tmp/m2/ && mvn -B -o -Dmaven.repo.local=/tmp/m2 verify
RUN --network=none find . -type f -path '*/target/*.jar' ! -name '*-plain.jar' ! -name 'original-*' ! -name '*sources.jar' ! -name '*javadoc.jar' | while IFS= read -r jar; do \
      if unzip -tqq "$jar" >/dev/null 2>&1 && unzip -l "$jar" | grep -q 'BOOT-INF/' && unzip -p "$jar" META-INF/MANIFEST.MF | tr -d '\r' | grep -Eq '^Main-Class: org\.springframework\.boot\.loader\.(launch\.)?(JarLauncher|PropertiesLauncher)$'; then \
        printf '%s\n' "$jar"; \
      fi; \
    done > /tmp/agentia-executable-jars; \
    count=$(wc -l < /tmp/agentia-executable-jars); \
    if [ "$count" -ne 1 ]; then echo "Expected exactly one executable Spring Boot JAR; found $count" >&2; exit 1; fi; \
    IFS= read -r jar < /tmp/agentia-executable-jars; \
    cp "$jar" /application.jar

FROM agentia-runtime:21-v1
WORKDIR /app
COPY --from=build --chown=10001:10001 /application.jar /app/application.jar
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0" SERVER_PORT=8080
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=5 CMD wget -q -O - http://127.0.0.1:8080/actuator/health | grep -q '"status":"UP"' || exit 1
ENTRYPOINT ["java", "-jar", "/app/application.jar"]
