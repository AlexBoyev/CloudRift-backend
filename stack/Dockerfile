FROM gcc:latest

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev

# Files are under ./stack relative to build context "."
COPY stack/stack_server.c /app/stack_server.c
COPY stack/db_client.c /app/db_client.c
COPY stack/db_client.h /app/db_client.h

RUN gcc -O2 -Wall -Wextra -o stack_service stack_server.c db_client.c -I/usr/include/postgresql -lpq

EXPOSE 80
CMD ["./stack_service"]
