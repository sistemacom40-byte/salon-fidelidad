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


def _columna_existe_sqlite(cur, tabla, columna):
    cur.execute(f"PRAGMA table_info({tabla})")
    columnas = [fila[1] for fila in cur.fetchall()]
    return columna in columnas


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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS promo (
                id SERIAL PRIMARY KEY,
                mensaje TEXT,
                fecha_inicio TEXT,
                fecha_fin TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sesion_salon (
                id SERIAL PRIMARY KEY,
                activo_hasta TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS configuracion (
                id SERIAL PRIMARY KEY,
                whatsapp_numero TEXT,
                whatsapp_mensaje TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS seguridad (
                id SERIAL PRIMARY KEY,
                pin TEXT NOT NULL
            )
        """)

        cur.execute("ALTER TABLE promo ADD COLUMN IF NOT EXISTS fecha_inicio TEXT")
        cur.execute("ALTER TABLE promo ADD COLUMN IF NOT EXISTS fecha_fin TEXT")
        cur.execute("ALTER TABLE clientas ADD COLUMN IF NOT EXISTS activo INTEGER DEFAULT 1")

        cur.execute("SELECT COUNT(*) as total FROM seguridad")
        if cur.fetchone()["total"] == 0:
            cur.execute("INSERT INTO seguridad (pin) VALUES (%s)", ("1234",))

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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS promo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mensaje TEXT,
                fecha_inicio TEXT,
                fecha_fin TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sesion_salon (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activo_hasta TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS configuracion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                whatsapp_numero TEXT,
                whatsapp_mensaje TEXT
            )
        """)

        # SQLite no soporta "ADD COLUMN IF NOT EXISTS", hay que checar manualmente
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seguridad (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pin TEXT NOT NULL
            )
        """)

        if not _columna_existe_sqlite(cur, "promo", "fecha_inicio"):
            cur.execute("ALTER TABLE promo ADD COLUMN fecha_inicio TEXT")
        if not _columna_existe_sqlite(cur, "promo", "fecha_fin"):
            cur.execute("ALTER TABLE promo ADD COLUMN fecha_fin TEXT")
        if not _columna_existe_sqlite(cur, "clientas", "activo"):
            cur.execute("ALTER TABLE clientas ADD COLUMN activo INTEGER DEFAULT 1")

        cur.execute("SELECT COUNT(*) as total FROM seguridad")
        if cur.fetchone()["total"] == 0:
            cur.execute("INSERT INTO seguridad (pin) VALUES (?)", ("1234",))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    crear_tablas()
    print("Base de datos creada correctamente ✅")