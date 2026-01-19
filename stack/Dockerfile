# ----------------------------------------
# Stage 1: Build (Compiling)
# ----------------------------------------
# We keep this EXACTLY as you had it
FROM gcc:12 AS builder

WORKDIR /app

# 1. Install PostgreSQL development libraries
RUN apt-get update && apt-get install -y libpq-dev

# 2. Copy the specific 'stack' directory
COPY stack/ /app/stack/

# 3. Compile the C code
RUN gcc -O2 -Wall -Wextra -o stack-service \
    /app/stack/stack_server.c \
    /app/stack/db_client.c \
    -I/usr/include/postgresql \
    -I/app/stack \
    -lpq

# ----------------------------------------
# Stage 2: Run (Hybrid Runtime: C + Python)
# ----------------------------------------
# CHANGE: Use a Python base image (which is built on Debian)
FROM python:3.9-slim

WORKDIR /app

# 1. Install PostgreSQL runtime library (Required for your C binary)
#    We also perform clean up to keep image small
RUN apt-get update && apt-get install -y libpq5 && rm -rf /var/lib/apt/lists/*

# 2. Install Python Dependencies (For Monitoring)
COPY stack/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy the compiled C binary from Stage 1
COPY --from=builder /app/stack-service .
RUN chmod +x stack-service

# 4. Copy the Python Wrapper (The bridge to Prometheus)
COPY stack/app.py .

# 5. Expose the port (Python Wrapper usually runs on 5001)
EXPOSE 5001

# 6. CHANGE CMD: Run the Python Wrapper, not the C binary directly
#    (The Python script will call the C binary when needed)
CMD ["python", "app.py"]