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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS servicios (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                precio REAL NOT NULL,
                activo INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS registro_servicios (
                id SERIAL PRIMARY KEY,
                fecha TEXT NOT NULL,
                hora_registro TEXT NOT NULL,
                nombre_clienta TEXT,
                servicio TEXT NOT NULL,
                precio REAL NOT NULL,
                encargada TEXT,
                observacion TEXT,
                estado_pago TEXT NOT NULL DEFAULT 'pendiente',
                forma_pago TEXT,
                fecha_pago TEXT,
                hora_pago TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS gastos_diarios (
                id SERIAL PRIMARY KEY,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                concepto TEXT NOT NULL,
                monto REAL NOT NULL,
                forma_pago TEXT NOT NULL DEFAULT 'efectivo'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS depositos_bancarios (
                id SERIAL PRIMARY KEY,
                fecha TEXT NOT NULL,
                fecha_registro TEXT,
                hora TEXT NOT NULL,
                monto REAL NOT NULL,
                numero_deposito TEXT,
                observacion TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS pagos_comisiones (
                id SERIAL PRIMARY KEY,
                encargada_id INTEGER,
                encargada_nombre TEXT NOT NULL,
                fecha_pago TEXT NOT NULL,
                hora_pago TEXT NOT NULL,
                monto REAL NOT NULL,
                sueldo_base REAL DEFAULT 0,
                forma_pago TEXT NOT NULL,
                de_caja_salon INTEGER DEFAULT 1,
                fecha_inicio_rango TEXT,
                fecha_fin_rango TEXT,
                porcentaje REAL,
                observacion TEXT
            )
        """)

        cur.execute("ALTER TABLE gastos_diarios ADD COLUMN IF NOT EXISTS forma_pago TEXT NOT NULL DEFAULT 'efectivo'")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS encargadas (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                activo INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS registro_servicio_encargadas (
                id SERIAL PRIMARY KEY,
                registro_id INTEGER NOT NULL,
                encargada_id INTEGER NOT NULL,
                monto_asignado REAL NOT NULL
            )
        """)

        cur.execute("ALTER TABLE promo ADD COLUMN IF NOT EXISTS fecha_inicio TEXT")
        cur.execute("ALTER TABLE promo ADD COLUMN IF NOT EXISTS fecha_fin TEXT")
        cur.execute("ALTER TABLE promo ADD COLUMN IF NOT EXISTS mensaje_largo TEXT")
        cur.execute("ALTER TABLE clientas ADD COLUMN IF NOT EXISTS activo INTEGER DEFAULT 1")
        cur.execute("ALTER TABLE clientas ADD COLUMN IF NOT EXISTS tarjetas_completadas INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE registro_servicios ADD COLUMN IF NOT EXISTS descuento REAL DEFAULT 0")
        cur.execute("ALTER TABLE seguridad ADD COLUMN IF NOT EXISTS pin_duena TEXT")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS caja_inicial (
                id SERIAL PRIMARY KEY,
                fecha TEXT UNIQUE NOT NULL,
                monto REAL NOT NULL
            )
        """)

        cur.execute("SELECT COUNT(*) as total FROM seguridad")
        if cur.fetchone()["total"] == 0:
            cur.execute("INSERT INTO seguridad (pin, pin_duena) VALUES (%s, %s)", ("1234", "0000"))
        else:
            cur.execute("UPDATE seguridad SET pin_duena = %s WHERE pin_duena IS NULL", ("0000",))

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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS servicios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                precio REAL NOT NULL,
                activo INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS servicios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                precio REAL NOT NULL,
                activo INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS registro_servicios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                hora_registro TEXT NOT NULL,
                nombre_clienta TEXT,
                servicio TEXT NOT NULL,
                precio REAL NOT NULL,
                encargada TEXT,
                observacion TEXT,
                estado_pago TEXT NOT NULL DEFAULT 'pendiente',
                forma_pago TEXT,
                fecha_pago TEXT,
                hora_pago TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS gastos_diarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                concepto TEXT NOT NULL,
                monto REAL NOT NULL,
                forma_pago TEXT NOT NULL DEFAULT 'efectivo'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS depositos_bancarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                fecha_registro TEXT,
                hora TEXT NOT NULL,
                monto REAL NOT NULL,
                numero_deposito TEXT,
                observacion TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS pagos_comisiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                encargada_id INTEGER,
                encargada_nombre TEXT NOT NULL,
                fecha_pago TEXT NOT NULL,
                hora_pago TEXT NOT NULL,
                monto REAL NOT NULL,
                sueldo_base REAL DEFAULT 0,
                forma_pago TEXT NOT NULL,
                de_caja_salon INTEGER DEFAULT 1,
                fecha_inicio_rango TEXT,
                fecha_fin_rango TEXT,
                porcentaje REAL,
                observacion TEXT
            )
        """)

        if not _columna_existe_sqlite(cur, "gastos_diarios", "forma_pago"):
            cur.execute("ALTER TABLE gastos_diarios ADD COLUMN forma_pago TEXT NOT NULL DEFAULT 'efectivo'")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS encargadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                activo INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS registro_servicio_encargadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registro_id INTEGER NOT NULL,
                encargada_id INTEGER NOT NULL,
                monto_asignado REAL NOT NULL
            )
        """)

        if not _columna_existe_sqlite(cur, "promo", "fecha_inicio"):
            cur.execute("ALTER TABLE promo ADD COLUMN fecha_inicio TEXT")
        if not _columna_existe_sqlite(cur, "promo", "fecha_fin"):
            cur.execute("ALTER TABLE promo ADD COLUMN fecha_fin TEXT")
        if not _columna_existe_sqlite(cur, "promo", "mensaje_largo"):
            cur.execute("ALTER TABLE promo ADD COLUMN mensaje_largo TEXT")
        if not _columna_existe_sqlite(cur, "clientas", "activo"):
            cur.execute("ALTER TABLE clientas ADD COLUMN activo INTEGER DEFAULT 1")
        if not _columna_existe_sqlite(cur, "clientas", "tarjetas_completadas"):
            cur.execute("ALTER TABLE clientas ADD COLUMN tarjetas_completadas INTEGER DEFAULT 0")
        if not _columna_existe_sqlite(cur, "registro_servicios", "descuento"):
            cur.execute("ALTER TABLE registro_servicios ADD COLUMN descuento REAL DEFAULT 0")
        if not _columna_existe_sqlite(cur, "seguridad", "pin_duena"):
            cur.execute("ALTER TABLE seguridad ADD COLUMN pin_duena TEXT")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS caja_inicial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT UNIQUE NOT NULL,
                monto REAL NOT NULL
            )
        """)

        cur.execute("SELECT COUNT(*) as total FROM seguridad")
        if cur.fetchone()["total"] == 0:
            cur.execute("INSERT INTO seguridad (pin, pin_duena) VALUES (?, ?)", ("1234", "0000"))
        else:
            cur.execute("UPDATE seguridad SET pin_duena = ? WHERE pin_duena IS NULL", ("0000",))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    crear_tablas()
    print("Base de datos creada correctamente ✅")