#include <stdio.h>
#include <stdlib.h>
#include <libpq-fe.h>

PGconn *get_db_connection() {
    char conninfo[512];

    const char *host = getenv("DB_HOST");
    const char *name = getenv("DB_NAME");
    const char *user = getenv("DB_USER");
    const char *pass = getenv("DB_PASSWORD");

    if (!host || !name || !user || !pass) {
        fprintf(stderr, "FATAL: Missing DB Env Vars! DB_HOST=%s DB_NAME=%s DB_USER=%s\n",
                host ? host : "NULL",
                name ? name : "NULL",
                user ? user : "NULL");
        return NULL;
    }

    snprintf(conninfo, sizeof(conninfo),
             "host=%s dbname=%s user=%s password=%s",
             host, name, user, pass);

    PGconn *conn = PQconnectdb(conninfo);
    if (PQstatus(conn) != CONNECTION_OK) {
        fprintf(stderr, "DB Connection failed: %s\n", PQerrorMessage(conn));
        PQfinish(conn);
        return NULL;
    }
    return conn;
}
