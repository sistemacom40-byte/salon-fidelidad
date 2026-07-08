import os

USANDO_POSTGRES = "DATABASE_URL" in os.environ

def get_conexion():
    if USANDO_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        import sqlite3
        conn = sqlite3.connect("salon.db")
        conn.row_factory = sqlite3.Row
    return conn

def crear_tablas():
    conn = get_conexion()
    cur = conn.cursor()
    if USANDO_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clientas (
                id SERIAL PRIMARY KEY,
                celular TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                visitas INTEGER DEFAULT 0,
                ultima_visita TEXT
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clientas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                celular TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                visitas INTEGER DEFAULT 0,
                ultima_visita TEXT
            )
        """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    crear_tablas()
    print("Base de datos creada correctamente ✅")