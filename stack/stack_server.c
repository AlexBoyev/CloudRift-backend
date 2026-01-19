#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <ctype.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <libpq-fe.h>
#include "db_client.h"

// --- CHANGE 1: Set Default Port to 5050 (Internal) ---
#define DEFAULT_PORT 5050
#define BUFFER_SIZE 65536

static void send_response(int sock, int status, const char *body) {
    const char *status_text =
        (status == 200) ? "200 OK" :
        (status == 400) ? "400 Bad Request" :
        (status == 404) ? "404 Not Found" :
        "500 Internal Server Error";

    char resp[BUFFER_SIZE];
    size_t body_len = strlen(body);

    int len = snprintf(resp, sizeof(resp),
        "HTTP/1.1 %s\r\n"
        "Content-Type: application/json\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
        "Access-Control-Allow-Headers: Content-Type\r\n"
        "Connection: close\r\n"
        "Content-Length: %zu\r\n"
        "\r\n"
        "%s",
        status_text, body_len, body
    );

    if (len > 0) {
        (void)write(sock, resp, (size_t)len);
    }
}

static int parse_request_line(const char *req, char *method, size_t msz, char *path, size_t psz) {
    const char *sp1 = strchr(req, ' ');
    if (!sp1) return 0;
    const char *sp2 = strchr(sp1 + 1, ' ');
    if (!sp2) return 0;

    size_t ml = (size_t)(sp1 - req);
    size_t pl = (size_t)(sp2 - (sp1 + 1));

    if (ml == 0 || ml >= msz) return 0;
    if (pl == 0 || pl >= psz) return 0;

    memcpy(method, req, ml);
    method[ml] = '\0';

    memcpy(path, sp1 + 1, pl);
    path[pl] = '\0';
    return 1;
}

static int header_content_length(const char *headers) {
    const char *p = headers;
    while (*p) {
        if ((p[0] == 'C' || p[0] == 'c') &&
            (p[1] == 'o' || p[1] == 'O') &&
            (p[2] == 'n' || p[2] == 'N') &&
            (p[3] == 't' || p[3] == 'T') &&
            (p[4] == 'e' || p[4] == 'E') &&
            (p[5] == 'n' || p[5] == 'N') &&
            (p[6] == 't' || p[6] == 'T') &&
            p[7] == '-' &&
            (p[8] == 'L' || p[8] == 'l') &&
            (p[9] == 'e' || p[9] == 'E') &&
            (p[10] == 'n' || p[10] == 'N') &&
            (p[11] == 'g' || p[11] == 'G') &&
            (p[12] == 't' || p[12] == 'T') &&
            (p[13] == 'h' || p[13] == 'H') &&
            p[14] == ':')
        {
            const char *q = p + 15;
            while (*q && isspace((unsigned char)*q)) q++;
            return atoi(q);
        }
        const char *nl = strstr(p, "\r\n");
        if (!nl) break;
        p = nl + 2;
    }
    return 0;
}

static int extract_json_int_value(const char *json, const char *key, int *out) {
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);

    const char *p = strstr(json, needle);
    if (!p) return 0;
    p += strlen(needle);

    while (*p && isspace((unsigned char)*p)) p++;
    if (*p != ':') return 0;
    p++;
    while (*p && isspace((unsigned char)*p)) p++;

    int sign = 1;
    if (*p == '-') { sign = -1; p++; }

    if (!isdigit((unsigned char)*p)) return 0;

    long v = 0;
    while (*p && isdigit((unsigned char)*p)) {
        v = v * 10 + (*p - '0');
        p++;
    }
    *out = (int)(v * sign);
    return 1;
}

static int read_full_http_request(int sock, char *out_buf, size_t out_sz) {
    size_t total = 0;
    while (total < out_sz - 1) {
        ssize_t n = read(sock, out_buf + total, out_sz - 1 - total);
        if (n <= 0) break;
        total += (size_t)n;
        out_buf[total] = '\0';

        char *hdr_end = strstr(out_buf, "\r\n\r\n");
        if (hdr_end) {
            size_t header_len = (size_t)(hdr_end - out_buf) + 4;
            int cl = header_content_length(out_buf);
            size_t need = header_len + (cl > 0 ? (size_t)cl : 0);
            if (total >= need) {
                return 1;
            }
        }
    }
    return (total > 0);
}

static void handle_client(int client_sock) {
    char req[BUFFER_SIZE];
    memset(req, 0, sizeof(req));

    if (!read_full_http_request(client_sock, req, sizeof(req))) {
        return;
    }

    char method[16], path[256];
    if (!parse_request_line(req, method, sizeof(method), path, sizeof(path))) {
        send_response(client_sock, 400, "{\"error\":\"Bad Request\"}");
        return;
    }

    if (strcmp(method, "OPTIONS") == 0) {
        send_response(client_sock, 200, "{\"status\":\"ok\"}");
        return;
    }

    char *hdr_end = strstr(req, "\r\n\r\n");
    const char *body = (hdr_end) ? (hdr_end + 4) : "";

    if (strcmp(method, "GET") == 0 && strcmp(path, "/health") == 0) {
        send_response(client_sock, 200, "{\"status\":\"ok\"}");
        return;
    }

    PGconn *conn = get_db_connection();
    if (!conn) {
        send_response(client_sock, 500, "{\"error\":\"DB connection failed\"}");
        return;
    }

    PGresult *r0 = PQexec(conn, "CREATE TABLE IF NOT EXISTS stack (id SERIAL PRIMARY KEY, value INT NOT NULL);");
    PQclear(r0);

    if (strcmp(method, "POST") == 0 && strcmp(path, "/push") == 0) {
        int val = 0;
        if (!extract_json_int_value(body, "value", &val)) {
            PQfinish(conn);
            send_response(client_sock, 400, "{\"error\":\"Invalid JSON: expected {\\\"value\\\": <int>}\"}");
            return;
        }

        char val_str[32];
        snprintf(val_str, sizeof(val_str), "%d", val);
        const char *params[1] = { val_str };

        PGresult *res = PQexecParams(conn,
            "INSERT INTO stack (value) VALUES ($1)",
            1, NULL, params, NULL, NULL, 0
        );

        ExecStatusType st = PQresultStatus(res);
        if (st != PGRES_COMMAND_OK) {
            const char *err = PQerrorMessage(conn);
            PQclear(res);
            PQfinish(conn);
            send_response(client_sock, 500, "{\"error\":\"DB insert failed\"}");
            return;
        }

        PQclear(res);
        PQfinish(conn);
        send_response(client_sock, 200, "{\"status\":\"pushed\"}");
        return;
    }

    if (strcmp(method, "POST") == 0 && strcmp(path, "/pop") == 0) {
        PGresult *res = PQexec(conn,
            "DELETE FROM stack WHERE id = (SELECT id FROM stack ORDER BY id DESC LIMIT 1) RETURNING value"
        );

        if (PQresultStatus(res) == PGRES_TUPLES_OK && PQntuples(res) > 0) {
            const char *v = PQgetvalue(res, 0, 0);
            char msg[128];
            snprintf(msg, sizeof(msg), "{\"status\":\"popped\",\"value\":%s}", v);
            PQclear(res);
            PQfinish(conn);
            send_response(client_sock, 200, msg);
            return;
        }

        PQclear(res);
        PQfinish(conn);
        send_response(client_sock, 200, "{\"status\":\"stack empty\"}");
        return;
    }

    if (strcmp(method, "GET") == 0 && strcmp(path, "/stack") == 0) {
        PGresult *res = PQexec(conn, "SELECT value FROM stack ORDER BY id DESC");

        if (PQresultStatus(res) != PGRES_TUPLES_OK) {
            PQclear(res);
            PQfinish(conn);
            send_response(client_sock, 500, "{\"error\":\"DB select failed\"}");
            return;
        }

        char out[BUFFER_SIZE];
        size_t used = 0;
        used += snprintf(out + used, sizeof(out) - used, "[");

        int rows = PQntuples(res);
        for (int i = 0; i < rows; i++) {
            const char *v = PQgetvalue(res, i, 0);
            if (!v) v = "0";
            if (used + strlen(v) + 4 >= sizeof(out)) break;
            used += snprintf(out + used, sizeof(out) - used, "%s%s", v, (i < rows - 1) ? "," : "");
        }
        used += snprintf(out + used, sizeof(out) - used, "]");

        PQclear(res);
        PQfinish(conn);
        send_response(client_sock, 200, out);
        return;
    }

    PQfinish(conn);
    send_response(client_sock, 404, "{\"error\":\"Route Not Found\"}");
}

int main() {
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("socket");
        return 1;
    }

    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    // --- CHANGE 2: Read Port from Environment Variable ---
    int port = DEFAULT_PORT;
    char *env_port = getenv("PORT");
    if (env_port) {
        port = atoi(env_port);
    }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);

    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(server_fd);
        return 1;
    }

    if (listen(server_fd, 128) < 0) {
        perror("listen");
        close(server_fd);
        return 1;
    }

    printf("C Stack Service: Ready on Port %d\n", port);

    while (1) {
        int client = accept(server_fd, NULL, NULL);
        if (client < 0) continue;
        handle_client(client);
        close(client);
    }

    close(server_fd);
    return 0;
}