#ifndef DB_CLIENT_H
#define DB_CLIENT_H

#include <libpq-fe.h>

PGconn *get_db_connection();

#endif
