# ----------------------------------------
# Stage 1: Build (Compiling)
# ----------------------------------------
FROM gcc:12 AS builder

WORKDIR /app

# 1. Install PostgreSQL development libraries
RUN apt-get update && apt-get install -y libpq-dev

# 2. FIX: Copy the specific 'stack' directory from the root context
COPY stack/ /app/stack/

# 3. FIX: Compile using full paths
#    - We point gcc to the files inside /app/stack/
#    - We add -I/app/stack so it can find header files in that folder
RUN gcc -O2 -Wall -Wextra -o stack-service \
    /app/stack/stack_server.c \
    /app/stack/db_client.c \
    -I/usr/include/postgresql \
    -I/app/stack \
    -lpq

# ----------------------------------------
# Stage 2: Run (Runtime)
# ----------------------------------------
FROM debian:bookworm-slim

WORKDIR /app

# 1. Install PostgreSQL runtime library
RUN apt-get update && apt-get install -y libpq5 && rm -rf /var/lib/apt/lists/*

# 2. Copy the compiled binary from builder
COPY --from=builder /app/stack-service .

# 3. Permissions and Command
RUN chmod +x stack-service
CMD ["./stack-service"]