# OLD (Broken): FROM openjdk:17-slim
# NEW (Working):
FROM eclipse-temurin:17-jdk-jammy

WORKDIR /app

# 1. Install curl (Debian based)
RUN apt-get update && apt-get install -y curl

# 2. Download PostgreSQL JDBC Driver
RUN mkdir -p /app/libs && \
    curl -o /app/libs/postgresql.jar https://jdbc.postgresql.org/download/postgresql-42.6.0.jar

# 3. Copy your Java source code
COPY linkedlist/ /app/linkedlist/

# 4. Compile
RUN javac -cp ".:/app/libs/postgresql.jar" linkedlist/*.java

# 5. Run
CMD ["java", "-cp", ".:/app/libs/postgresql.jar", "linkedlist.LinkedListService"]