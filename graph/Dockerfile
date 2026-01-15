# Base Image
FROM python:3.9-slim

WORKDIR /app

# 1. Install System Dependencies
# libpq-dev is required for psycopg2 (the Postgres driver)
RUN apt-get update && apt-get install -y libpq-dev gcc

# 2. Install Python Dependencies
COPY graph/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy Application Code
COPY graph/ .

# 4. COPY SHARED DB CLIENT
# This takes db_client.py from your local database/ folder
# and places it inside the container at /app/db_client.py
COPY database/db_client.py .

# 5. Run the Service
CMD ["python", "graph_service.py"]