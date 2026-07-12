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
            resp = redirect(url_for("panel"))
            resp.set_cookie("celular_autorizado", "si", max_age=60*60*24*365)
            return resp
        else:
            error = "PIN incorrecto, intenta de nuevo"
    return render_template("pin.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    resp = redirect(url_for("pin"))
    resp.delete_cookie("celular_autorizado")
    return resp


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
    cur.execute(f"SELECT * FROM clientas WHERE celular = {m}", (celular,))
    clienta = cur.fetchone()
    conn.close()

    if clienta is None:
        return "Clienta no encontrada"

    return render_template(
        "tarjeta.html",
        nombre=clienta["nombre"],
        visitas=clienta["visitas"],
        celular=clienta["celular"],
        ultima_visita=formatear_fecha(clienta["ultima_visita"]),
        tamano_nombre=tamano_nombre(clienta["nombre"]),
        solo_lectura=not session.get("staff_activo"),
    )


@app.route("/tap/<celular>")
def tap(celular):
    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM clientas WHERE celular = {m}", (celular,))
    clienta = cur.fetchone()

    if clienta is None:
        conn.close()
        return "Tarjeta no reconocida. Pide ayuda al personal del salón."

    salon_activo = request.cookies.get("celular_autorizado") == "si"

    if not salon_activo:
        cur.execute("SELECT * FROM promo")
        promo_actual = cur.fetchone()
        mensaje_promo = None
        if promo_actual and promo_actual["fecha_expira"]:
            if datetime.datetime.now() < datetime.datetime.fromisoformat(promo_actual["fecha_expira"]):
                mensaje_promo = promo_actual["mensaje"]
        conn.close()
        return render_template(
            "tarjeta.html",
            nombre=clienta["nombre"],
            visitas=clienta["visitas"],
            celular=clienta["celular"],
            ultima_visita=formatear_fecha(clienta["ultima_visita"]),
            tamano_nombre=tamano_nombre(clienta["nombre"]),
            solo_lectura=True,
            promo=mensaje_promo
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


@app.route("/restar/<celular>")
def restar(celular):
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM clientas WHERE celular = {m}", (celular,))
    clienta = cur.fetchone()

    if clienta is not None and clienta["visitas"] > 0:
        cur.execute(
            f"UPDATE clientas SET visitas = {m} WHERE celular = {m}",
            (clienta["visitas"] - 1, celular)
        )
        conn.commit()

    conn.close()
    return redirect(url_for("tarjeta", celular=celular))


@app.route("/promo", methods=["GET", "POST"])
def promo():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    conn = get_conexion()
    cur = conn.cursor()
    m = marcador()

    if request.method == "POST":
        mensaje = request.form.get("mensaje", "").strip()
        horas = request.form.get("horas", "24")
        fecha_expira = (datetime.datetime.now() + datetime.timedelta(hours=int(horas))).isoformat()
        cur.execute("DELETE FROM promo")
        cur.execute(
            f"INSERT INTO promo (mensaje, fecha_expira) VALUES ({m}, {m})",
            (mensaje, fecha_expira)
        )
        conn.commit()

    cur.execute("SELECT * FROM promo")
    promo_actual = cur.fetchone()
    conn.close()
    return render_template("promo.html", promo=promo_actual)


@app.route("/resumen")
def resumen():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    conn = get_conexion()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total FROM clientas")
    total = cur.fetchone()["total"]
    conn.close()
    return render_template("resumen.html", total=total)


if __name__ == "__main__":
    app.run(debug=True)