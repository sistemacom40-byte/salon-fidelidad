from flask import Flask, render_template, request, session, redirect, url_for
from database import get_conexion, USANDO_POSTGRES, crear_tablas
import datetime

app = Flask(__name__)
app.secret_key = "cambiar-esto-luego"
app.permanent_session_lifetime = datetime.timedelta(hours=12)
crear_tablas()
PIN_CORRECTO = "1234"


def marcador():
    return "%s" if USANDO_POSTGRES else "?"


def formatear_fecha(fecha_iso):
    if not fecha_iso:
        return "Sin visitas registradas"
    try:
        dt = datetime.datetime.fromisoformat(fecha_iso)
        meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
        return f"{dt.day} {meses[dt.month - 1]}, {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return "Sin visitas registradas"


def tamano_nombre(nombre):
    largo = len(nombre)
    if largo <= 14:
        return "26px"
    elif largo <= 20:
        return "20px"
    elif largo <= 28:
        return "16px"
    else:
        return "13px"


@app.route("/", methods=["GET", "POST"])
def pin():
    celular_nfc = request.args.get("c")
    if celular_nfc:
        return redirect(url_for("tap", celular=celular_nfc))
    error = None
    if request.method == "POST":
        pin_ingresado = request.form.get("pin", "")
        if pin_ingresado == PIN_CORRECTO:
            session.permanent = True
            session["staff_activo"] = True
            conn = get_conexion()
            cur = conn.cursor()
            m = marcador()
            activo_hasta = (datetime.datetime.now() + datetime.timedelta(hours=12)).isoformat()
            cur.execute("DELETE FROM sesion_salon")
            cur.execute(f"INSERT INTO sesion_salon (activo_hasta) VALUES ({m})", (activo_hasta,))
            conn.commit()
            conn.close()
            return redirect(url_for("panel"))
        else:
            error = "PIN incorrecto, intenta de nuevo"
    return render_template("pin.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute("DELETE FROM sesion_salon")
    conn.commit()
    conn.close()
    return redirect(url_for("pin"))


@app.route("/panel", methods=["GET", "POST"])
def panel():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    if request.method == "POST":
        celular = request.form.get("celular", "").strip()
        m = marcador()
        conn = get_conexion()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM clientas WHERE celular = {m}", (celular,))
        clienta = cur.fetchone()

        if clienta is None:
            nombre = request.form.get("nombre", "").strip() or "Clienta nueva"
            cur.execute(
                f"INSERT INTO clientas (celular, nombre, visitas, ultima_visita) VALUES ({m}, {m}, {m}, {m})",
                (celular, nombre, 0, datetime.datetime.now().isoformat())
            )
        else:
            nuevas_visitas = clienta["visitas"] + 1
            if nuevas_visitas > 8:
                nuevas_visitas = 1
            cur.execute(
                f"UPDATE clientas SET visitas = {m}, ultima_visita = {m} WHERE celular = {m}",
                (nuevas_visitas, datetime.datetime.now().isoformat(), celular)
            )

        conn.commit()
        conn.close()
        return redirect(url_for("tarjeta", celular=celular))

    return render_template("panel.html")


@app.route("/tarjeta")
def tarjeta():
    celular = request.args.get("celular")
    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()