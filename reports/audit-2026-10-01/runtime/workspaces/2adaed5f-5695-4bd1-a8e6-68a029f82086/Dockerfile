# ==============================================================================
# Multi-Stage Layered Dockerfile for Spring Boot 3 / Java 21 LTS
# Hermetic & Non-Root Execution (Constitution Principles IV & VI)
# ==============================================================================

# Stage 1: Build fat JAR inside container with Maven (Hermetic build)
FROM maven:3.9-eclipse-temurin-21-alpine AS builder-mvn
WORKDIR /workspace
COPY pom.xml .
COPY src ./src
RUN mvn clean package -Dmaven.test.skip=true

# Stage 2: Spring Boot Layer Extractor
FROM eclipse-temurin:21-jre-alpine AS builder
WORKDIR /workspace

# Copy pre-built fat JAR from Maven build stage
COPY --from=builder-mvn /workspace/target/*.jar application.jar

# Extract Spring Boot layers (dependencies, spring-boot-loader, snapshot-dependencies, application)
RUN java -Djarmode=layertools -jar application.jar extract

# ------------------------------------------------------------------------------
# Stage 3: Minimal Non-Root Runtime Image
# ------------------------------------------------------------------------------
FROM eclipse-temurin:21-jre-alpine AS runner
WORKDIR /app

# Create unprivileged non-root user and group
RUN addgroup -g 10001 -S appgroup && \
    adduser -u 10001 -S appuser -G appgroup

# Copy extracted layers in optimal caching order
COPY --from=builder /workspace/dependencies/ ./
COPY --from=builder /workspace/spring-boot-loader/ ./
COPY --from=builder /workspace/snapshot-dependencies/ ./
COPY --from=builder /workspace/application/ ./

# Change ownership of application files
RUN chown -R appuser:appgroup /app

# Switch to non-root execution
USER appuser:appgroup

# Configure JVM container memory management & network defaults
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0 -XX:+UseG1GC -Djava.security.egd=file:/dev/./urandom"
ENV SERVER_PORT=8080

EXPOSE 8080

# Native container healthcheck polling Spring Boot Actuator
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
  CMD wget -q -O - http://localhost:8080/actuator/health | grep UP || exit 1

# Launch using Spring Boot JarLauncher
ENTRYPOINT ["java", "org.springframework.boot.loader.launch.JarLauncher"]
