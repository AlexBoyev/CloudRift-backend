FROM eclipse-temurin:17-jdk-jammy

WORKDIR /app

# 1. Install curl
RUN apt-get update && apt-get install -y curl

# 2. Download Dependencies (Postgres + Prometheus)
RUN mkdir -p /app/libs && \
    curl -o /app/libs/postgresql.jar https://jdbc.postgresql.org/download/postgresql-42.6.0.jar && \
    # Prometheus Core
    curl -o /app/libs/simpleclient.jar https://repo1.maven.org/maven2/io/prometheus/simpleclient/0.16.0/simpleclient-0.16.0.jar && \
    # Prometheus Common (Formats the data for Grafana)
    curl -o /app/libs/simpleclient_common.jar https://repo1.maven.org/maven2/io/prometheus/simpleclient_common/0.16.0/simpleclient_common-0.16.0.jar && \
    # Prometheus Hotspot (CPU/Memory metrics)
    curl -o /app/libs/simpleclient_hotspot.jar https://repo1.maven.org/maven2/io/prometheus/simpleclient_hotspot/0.16.0/simpleclient_hotspot-0.16.0.jar && \
    # Prometheus Tracer (Required dependency)
    curl -o /app/libs/simpleclient_tracer_common.jar https://repo1.maven.org/maven2/io/prometheus/simpleclient_tracer_common/0.16.0/simpleclient_tracer_common-0.16.0.jar

# 3. Copy Code
COPY linkedlist/ /app/linkedlist/

# 4. Compile (Notice the * wildcard to include all JARs)
RUN javac -cp ".:/app/libs/*" linkedlist/*.java

# 5. Run
CMD ["java", "-cp", ".:/app/libs/*", "linkedlist.LinkedListService"]