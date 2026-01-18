# ----------------------------------------
# Stage 1: Build (Compiling)
# ----------------------------------------
FROM gcc:12 AS builder

WORKDIR /app

# 1. Install PostgreSQL development libraries (Required for -lpq)
RUN apt-get update && apt-get install -y libpq-dev

# 2. Copy all your source files
COPY . .

# 3. Compile with your specific flags
#    -I/usr/include/postgresql : Where to look for header files
#    -lpq                      : Link against the PostgreSQL library
RUN gcc -O2 -Wall -Wextra -o stack-service stack_server.c db_client.c -I/usr/include/postgresql -lpq

# ----------------------------------------
# Stage 2: Run (Runtime)
# ----------------------------------------
FROM debian:bookworm-slim

WORKDIR /app

# 1. Install PostgreSQL runtime library (Required to run the binary)
#    We don't need the full 'dev' package here, just the runtime lib.
RUN apt-get update && apt-get install -y libpq5 && rm -rf /var/lib/apt/lists/*

# 2. Copy the compiled binary from builder
COPY --from=builder /app/stack-service .

# 3. Permissions and Command
RUN chmod +x stack-service
CMD ["./stack-service"]