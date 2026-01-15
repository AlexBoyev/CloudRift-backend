import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    """
    Creates and returns a connection to the PostgreSQL database.
    Reads credentials from Environment Variables.
    """
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'postgres-service'),
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD')
        )
        return conn
    except Exception as e:
        print(f"Database Connection Failed: {e}")
        return None


def execute_query(query, params=None, fetch=False):
    """
    Helper to execute a query safely.
    - query: SQL string
    - params: Tuple of values (e.g. (label,))
    - fetch: True if you expect data back (SELECT), False for INSERT/UPDATE
    """
    conn = get_db_connection()
    if conn is None:
        return None

    result = None
    try:
        # RealDictCursor allows accessing columns by name: row['label']
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)

        if fetch:
            result = cur.fetchall()
        else:
            conn.commit()
            result = True

        cur.close()
    except Exception as e:
        print(f"Query Failed: {query} | Error: {e}")
        if conn: conn.rollback()
        result = False  # explicit failure
    finally:
        if conn: conn.close()

    return result