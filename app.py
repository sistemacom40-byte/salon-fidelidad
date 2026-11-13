from flask import Flask, render_template, request, session, redirect, url_for, flash
from database import get_conexion, USANDO_POSTGRES, crear_tablas
import datetime
from zoneinfo import ZoneInfo
import urllib.parse
import calendar

app = Flask(__name__)
app.secret_key = "cambiar-esto-luego"
app.permanent_session_lifetime = datetime.timedelta(hours=12)


@app.after_request
def evitar_cache_tarjetas(response):
    if request.path.startswith("/tarjetas"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


def ahora_gt():
    return datetime.datetime.now(ZoneInfo("America/Guatemala")).replace(tzinfo=None)
crear_tablas()


def marcador():
    return "%s" if USANDO_POSTGRES else "?"


def link_whatsapp_clienta(celular, mensaje):
    numero = "".join(ch for ch in str(celular) if ch.isdigit())
    if len(numero) == 8:
        numero = "502" + numero
    texto = urllib.parse.quote(mensaje)
    return f"https://wa.me/{numero}?text={texto}"


def mensaje_promo_para_whatsapp(promo_actual):
    if not promo_actual:
        return ""
    largo = (promo_actual["mensaje_largo"] or "").strip()
    if largo:
        return largo
    return promo_actual["mensaje"] or ""


def obtener_pin(cur):
    cur.execute("SELECT * FROM seguridad ORDER BY id DESC LIMIT 1")
    fila = cur.fetchone()
    return fila["pin"] if fila else "1234"


def obtener_pin_duena(cur):
    cur.execute("SELECT * FROM seguridad ORDER BY id DESC LIMIT 1")
    fila = cur.fetchone()
    if fila and fila["pin_duena"]:
        return fila["pin_duena"]
    return "0000"


def actualizar_pin(cur, nuevo_pin):
    m = marcador()
    cur.execute(f"UPDATE seguridad SET pin = {m}", (nuevo_pin,))


def actualizar_pin_duena(cur, nuevo_pin):
    m = marcador()
    cur.execute(f"UPDATE seguridad SET pin_duena = {m}", (nuevo_pin,))


def formatear_fecha(fecha_iso):
    if not fecha_iso:
        return "Sin visitas registradas"
    try:
        dt = datetime.datetime.fromisoformat(fecha_iso)
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        return f"{dt.day} {meses[dt.month - 1]}, {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return "Sin visitas registradas"


def formatear_fecha_corta(fecha_iso):
    if not fecha_iso:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(fecha_iso)
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        return f"{dt.day} {meses[dt.month - 1]}"
    except Exception:
        return ""


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


def obtener_promo_vigente(cur):
    cur.execute("SELECT * FROM promo ORDER BY id DESC LIMIT 1")
    promo_actual = cur.fetchone()
    if not promo_actual or not promo_actual["fecha_inicio"] or not promo_actual["fecha_fin"]:
        return None
    ahora = ahora_gt()
    inicio = datetime.datetime.fromisoformat(promo_actual["fecha_inicio"])
    fin = datetime.datetime.fromisoformat(promo_actual["fecha_fin"])
    if inicio <= ahora <= fin:
        return promo_actual
    return None


def obtener_configuracion(cur):
    cur.execute("SELECT * FROM configuracion ORDER BY id DESC LIMIT 1")
    config = cur.fetchone()
    if config:
        return config["whatsapp_numero"] or "", config["whatsapp_mensaje"] or ""
    return "", ""


@app.route("/", methods=["GET", "POST"])
def pin():
    celular_nfc = request.args.get("c")
    if celular_nfc:
        return redirect(url_for("tap", celular=celular_nfc))
    error = None
    if request.method == "POST":
        pin_ingresado = request.form.get("pin", "")
        conn = get_conexion()
        cur = conn.cursor()
        pin_correcto = obtener_pin(cur)
        conn.close()
        if pin_ingresado == pin_correcto:
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
                (celular, nombre, 0, ahora_gt().isoformat())
            )
        else:
            nuevas_visitas = clienta["visitas"] + 1
            ciclo_completado = nuevas_visitas > 8
            if ciclo_completado:
                nuevas_visitas = 1
                cur.execute(
                    f"UPDATE clientas SET visitas = {m}, ultima_visita = {m}, tarjetas_completadas = tarjetas_completadas + 1 WHERE celular = {m}",
                    (nuevas_visitas, ahora_gt().isoformat(), celular)
                )
            else:
                cur.execute(
                    f"UPDATE clientas SET visitas = {m}, ultima_visita = {m} WHERE celular = {m}",
                    (nuevas_visitas, ahora_gt().isoformat(), celular)
                )

        conn.commit()
        conn.close()
        flash("Visita registrada correctamente ✅")
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

    if clienta is None:
        conn.close()
        return "Clienta no encontrada"

    promo_actual = obtener_promo_vigente(cur)
    wa_numero, wa_mensaje = obtener_configuracion(cur)
    conn.close()

    return render_template(
        "tarjeta.html",
        nombre=clienta["nombre"],
        visitas=clienta["visitas"],
        celular=clienta["celular"],
        ultima_visita=formatear_fecha(clienta["ultima_visita"]),
        tamano_nombre=tamano_nombre(clienta["nombre"]),
        solo_lectura=not session.get("staff_activo"),
        tarjetas_completadas=clienta["tarjetas_completadas"],
        promo=promo_actual["mensaje"] if promo_actual else None,
        promo_fecha_fin=formatear_fecha_corta(promo_actual["fecha_fin"]) if promo_actual else None,
        wa_numero=wa_numero,
        wa_mensaje=wa_mensaje,
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

    if not clienta["activo"]:
        conn.close()
        return "Esta tarjeta fue desactivada. Pide ayuda al personal del salón."

    salon_activo = request.cookies.get("celular_autorizado") == "si"

    if not salon_activo:
        promo_actual = obtener_promo_vigente(cur)
        wa_numero, wa_mensaje = obtener_configuracion(cur)
        conn.close()
        return render_template(
            "tarjeta.html",
            nombre=clienta["nombre"],
            visitas=clienta["visitas"],
            celular=clienta["celular"],
            ultima_visita=formatear_fecha(clienta["ultima_visita"]),
            tamano_nombre=tamano_nombre(clienta["nombre"]),
            solo_lectura=True,
            tarjetas_completadas=clienta["tarjetas_completadas"],
            promo=promo_actual["mensaje"] if promo_actual else None,
            promo_fecha_fin=formatear_fecha_corta(promo_actual["fecha_fin"]) if promo_actual else None,
            wa_numero=wa_numero,
            wa_mensaje=wa_mensaje,
        )
    else:
        nuevas_visitas = clienta["visitas"] + 1
        ciclo_completado = nuevas_visitas > 8
        if ciclo_completado:
            nuevas_visitas = 1
            cur.execute(
                f"UPDATE clientas SET visitas = {m}, ultima_visita = {m}, tarjetas_completadas = tarjetas_completadas + 1 WHERE celular = {m}",
                (nuevas_visitas, ahora_gt().isoformat(), celular)
            )
        else:
            cur.execute(
                f"UPDATE clientas SET visitas = {m}, ultima_visita = {m} WHERE celular = {m}",
                (nuevas_visitas, ahora_gt().isoformat(), celular)
            )
        conn.commit()
        conn.close()
        flash("Visita registrada correctamente ✅")
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
        mensaje_largo = request.form.get("mensaje_largo", "").strip()
        fecha_inicio = request.form.get("fecha_inicio", "")
        fecha_fin = request.form.get("fecha_fin", "")
        cur.execute("DELETE FROM promo")
        if mensaje:
            cur.execute(
                f"INSERT INTO promo (mensaje, mensaje_largo, fecha_inicio, fecha_fin) VALUES ({m}, {m}, {m}, {m})",
                (mensaje, mensaje_largo, fecha_inicio, fecha_fin)
            )
            flash("Promoción guardada correctamente ✅")
        else:
            flash("Promoción eliminada ✅")
        conn.commit()

    cur.execute("SELECT * FROM promo ORDER BY id DESC LIMIT 1")
    promo_actual = cur.fetchone()

    wa_numero, wa_mensaje = obtener_configuracion(cur)
    conn.close()
    return render_template(
        "promo.html",
        promo=promo_actual,
        wa_numero=wa_numero,
        wa_mensaje=wa_mensaje,
    )


@app.route("/configuracion", methods=["GET", "POST"])
def configuracion():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    conn = get_conexion()
    cur = conn.cursor()
    m = marcador()

    if request.method == "POST":
        wa_numero = request.form.get("wa_numero", "").strip()
        wa_mensaje = request.form.get("wa_mensaje", "").strip()
        cur.execute("DELETE FROM configuracion")
        cur.execute(
            f"INSERT INTO configuracion (whatsapp_numero, whatsapp_mensaje) VALUES ({m}, {m})",
            (wa_numero, wa_mensaje)
        )
        conn.commit()
        conn.close()
        flash("WhatsApp del salón actualizado correctamente ✅")
        return redirect(url_for("promo"))

    conn.close()
    return redirect(url_for("promo"))


@app.route("/panel-ajuste-pin", methods=["GET", "POST"])
def panel_ajuste_pin():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    error = None
    exito = None

    if request.method == "POST":
        pin_actual = request.form.get("pin_actual", "").strip()
        pin_nuevo = request.form.get("pin_nuevo", "").strip()
        pin_nuevo_confirmar = request.form.get("pin_nuevo_confirmar", "").strip()

        conn = get_conexion()
        cur = conn.cursor()
        pin_real = obtener_pin(cur)

        if pin_actual != pin_real:
            error = "El PIN actual no es correcto."
        elif not pin_nuevo.isdigit() or len(pin_nuevo) != 4:
            error = "El nuevo PIN debe tener exactamente 4 dígitos."
        elif pin_nuevo != pin_nuevo_confirmar:
            error = "Los PIN nuevos no coinciden."
        else:
            actualizar_pin(cur, pin_nuevo)
            conn.commit()
            exito = "PIN actualizado correctamente."

        conn.close()

    return render_template("cambiar_pin.html", error=error, exito=exito)


@app.route("/panel-ajuste-pin-especial", methods=["POST"])
def panel_ajuste_pin_especial():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    pin_actual = request.form.get("pin_duena_actual", "").strip()
    pin_nuevo = request.form.get("pin_duena_nuevo", "").strip()
    pin_nuevo_confirmar = request.form.get("pin_duena_nuevo_confirmar", "").strip()

    conn = get_conexion()
    cur = conn.cursor()
    pin_real = obtener_pin_duena(cur)

    error = None
    exito = None

    if pin_actual != pin_real:
        error = "El PIN especial actual no es correcto."
    elif not pin_nuevo.isdigit() or len(pin_nuevo) != 4:
        error = "El nuevo PIN especial debe tener exactamente 4 dígitos."
    elif pin_nuevo != pin_nuevo_confirmar:
        error = "Los PIN especiales nuevos no coinciden."
    else:
        actualizar_pin_duena(cur, pin_nuevo)
        conn.commit()
        exito = "PIN especial actualizado correctamente."

    conn.close()

    return render_template("cambiar_pin.html", error=error, exito=exito)


@app.route("/tarjetas", methods=["GET"])
def tarjetas():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    celular_buscado = request.args.get("celular", "").strip()
    clienta = None

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()

    if celular_buscado:
        cur.execute(f"SELECT * FROM clientas WHERE celular = {m}", (celular_buscado,))
        clienta = cur.fetchone()

    promo_actual = obtener_promo_vigente(cur)

    cur.execute("SELECT * FROM clientas ORDER BY nombre")
    filas = cur.fetchall()
    conn.close()

    todas_las_clientas = []
    for fila in filas:
        item = dict(fila)
        if promo_actual and item.get("activo"):
            item["wa_link"] = link_whatsapp_clienta(item["celular"], mensaje_promo_para_whatsapp(promo_actual))
        else:
            item["wa_link"] = None
        todas_las_clientas.append(item)

    avisadas_count = 0
    total_con_promo = 0
    todas_avisadas = False

    if promo_actual:
        if session.get("campana_promo_id") != promo_actual["id"]:
            session["campana_promo_id"] = promo_actual["id"]
            session["avisadas"] = []
        avisadas = session.get("avisadas", [])
        activas_con_promo = [c for c in todas_las_clientas if c["wa_link"]]
        total_con_promo = len(activas_con_promo)
        avisadas_count = len([c for c in activas_con_promo if c["celular"] in avisadas])
        todas_avisadas = total_con_promo > 0 and avisadas_count >= total_con_promo

    return render_template(
        "tarjetas.html",
        clienta=clienta,
        celular_buscado=celular_buscado,
        todas_las_clientas=todas_las_clientas,
        promo_activa=bool(promo_actual),
        avisadas_count=avisadas_count,
        total_con_promo=total_con_promo,
        todas_avisadas=todas_avisadas,
    )


@app.route("/tarjetas/avisar-siguiente")
def avisar_siguiente():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    promo_actual = obtener_promo_vigente(cur)

    if not promo_actual:
        conn.close()
        flash("No hay ninguna promoción activa en este momento.")
        return redirect(url_for("tarjetas"))

    if session.get("campana_promo_id") != promo_actual["id"]:
        session["campana_promo_id"] = promo_actual["id"]
        session["avisadas"] = []

    avisadas = session.get("avisadas", [])

    cur.execute(f"SELECT * FROM clientas WHERE activo = {m} ORDER BY nombre", (1,))
    clientas_activas = cur.fetchall()
    conn.close()

    siguiente = None
    for c in clientas_activas:
        if c["celular"] not in avisadas:
            siguiente = c
            break

    if not siguiente:
        flash("Ya avisaste a todas las clientas activas sobre esta promoción ✅")
        return redirect(url_for("tarjetas"))

    avisadas.append(siguiente["celular"])
    session["avisadas"] = avisadas
    session.modified = True

    link = link_whatsapp_clienta(siguiente["celular"], mensaje_promo_para_whatsapp(promo_actual))
    return redirect(link)


@app.route("/tarjetas/avisar-reiniciar", methods=["POST"])
def avisar_reiniciar():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    session["avisadas"] = []
    session.modified = True
    flash("Se reinició el conteo. Puedes volver a avisar a todas.")
    return redirect(url_for("tarjetas"))


@app.route("/tarjetas/toggle/<celular>", methods=["POST"])
def tarjetas_toggle(celular):
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM clientas WHERE celular = {m}", (celular,))
    clienta = cur.fetchone()

    if clienta is not None:
        nuevo_estado = 0 if clienta["activo"] else 1
        cur.execute(f"UPDATE clientas SET activo = {m} WHERE celular = {m}", (nuevo_estado, celular))
        conn.commit()
        if nuevo_estado == 0:
            flash("Tarjeta desactivada ✅")
        else:
            flash("Tarjeta reactivada ✅")

    conn.close()
    return redirect(url_for("tarjetas", celular=celular))


@app.route("/tarjetas/eliminar/<celular>", methods=["POST"])
def tarjetas_eliminar(celular):
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM clientas WHERE celular = {m}", (celular,))
    conn.commit()
    conn.close()
    flash("Tarjeta eliminada permanentemente ✅")
    return redirect(url_for("tarjetas"))


@app.route("/caja/servicios", methods=["GET", "POST"])
def caja_servicios():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        precio = request.form.get("precio", "").strip()
        if nombre and precio:
            try:
                precio_num = float(precio)
                cur.execute(
                    f"INSERT INTO servicios (nombre, precio, activo) VALUES ({m}, {m}, 1)",
                    (nombre, precio_num)
                )
                conn.commit()
                flash("Servicio agregado correctamente ✅")
            except ValueError:
                flash("El precio debe ser un número válido.")

    cur.execute("SELECT * FROM servicios ORDER BY activo DESC, nombre")
    servicios = cur.fetchall()
    conn.close()

    return render_template("caja_servicios.html", servicios=servicios)


@app.route("/caja/servicios/toggle/<int:servicio_id>", methods=["POST"])
def caja_servicios_toggle(servicio_id):
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM servicios WHERE id = {m}", (servicio_id,))
    servicio = cur.fetchone()

    if servicio is not None:
        nuevo_estado = 0 if servicio["activo"] else 1
        cur.execute(f"UPDATE servicios SET activo = {m} WHERE id = {m}", (nuevo_estado, servicio_id))
        conn.commit()

    conn.close()
    return redirect(url_for("caja_servicios"))


@app.route("/caja/servicios/eliminar/<int:servicio_id>", methods=["POST"])
def caja_servicios_eliminar(servicio_id):
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM servicios WHERE id = {m}", (servicio_id,))
    conn.commit()
    conn.close()
    flash("Servicio eliminado ✅")
    return redirect(url_for("caja_servicios"))


@app.route("/caja/encargadas", methods=["GET", "POST"])
def caja_encargadas():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if nombre:
            cur.execute(f"INSERT INTO encargadas (nombre, activo) VALUES ({m}, 1)", (nombre,))
            conn.commit()
            flash(f"Encargada {nombre} agregada ✅")

    cur.execute("SELECT * FROM encargadas ORDER BY activo DESC, nombre")
    encargadas = cur.fetchall()
    conn.close()

    return render_template("caja_encargadas.html", encargadas=encargadas)


@app.route("/caja/encargadas/toggle/<int:encargada_id>", methods=["POST"])
def caja_encargadas_toggle(encargada_id):
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM encargadas WHERE id = {m}", (encargada_id,))
    encargada = cur.fetchone()

    if encargada is not None:
        nuevo_estado = 0 if encargada["activo"] else 1
        cur.execute(f"UPDATE encargadas SET activo = {m} WHERE id = {m}", (nuevo_estado, encargada_id))
        conn.commit()

    conn.close()
    return redirect(url_for("caja_encargadas"))


@app.route("/caja/encargadas/eliminar/<int:encargada_id>", methods=["POST"])
def caja_encargadas_eliminar(encargada_id):
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM encargadas WHERE id = {m}", (encargada_id,))
    conn.commit()
    conn.close()
    flash("Encargada eliminada ✅")
    return redirect(url_for("caja_encargadas"))


@app.route("/caja/comisiones", methods=["GET", "POST"])
def caja_comisiones():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute("SELECT * FROM encargadas ORDER BY nombre")
    encargadas = cur.fetchall()

    resultado = None
    error = None

    if request.method == "POST":
        pin_ingresado = request.form.get("pin_duena", "").strip()
        encargada_id = request.form.get("encargada_id", "").strip()
        fecha_inicio = request.form.get("fecha_inicio", "").strip()
        fecha_fin = request.form.get("fecha_fin", "").strip()
        porcentaje = request.form.get("porcentaje", "").strip()

        pin_real = obtener_pin_duena(cur)

        if pin_ingresado != pin_real:
            error = "PIN especial incorrecto."
        elif not encargada_id or not fecha_inicio or not fecha_fin or not porcentaje:
            error = "Completa encargada, rango de fechas y porcentaje."
        else:
            try:
                porcentaje_num = float(porcentaje)
            except ValueError:
                porcentaje_num = None

            if porcentaje_num is None:
                error = "El porcentaje debe ser un número válido."
            else:
                cur.execute(f"SELECT * FROM encargadas WHERE id = {m}", (encargada_id,))
                encargada_sel = cur.fetchone()

                cur.execute(
                    f"SELECT rs.servicio as servicio, rse.monto_asignado as monto FROM registro_servicio_encargadas rse "
                    f"JOIN registro_servicios rs ON rs.id = rse.registro_id "
                    f"WHERE rse.encargada_id = {m} AND rs.fecha >= {m} AND rs.fecha <= {m} AND rs.estado_pago = 'pagado'",
                    (encargada_id, fecha_inicio, fecha_fin)
                )
                movimientos = cur.fetchall()
                total_produccion = sum(mv["monto"] for mv in movimientos)
                comision = total_produccion * (porcentaje_num / 100)

                resumen_por_servicio = {}
                for mv in movimientos:
                    nombre_s = mv["servicio"]
                    if nombre_s not in resumen_por_servicio:
                        resumen_por_servicio[nombre_s] = {"cantidad": 0, "monto": 0.0}
                    resumen_por_servicio[nombre_s]["cantidad"] += 1
                    resumen_por_servicio[nombre_s]["monto"] += mv["monto"]

                detalle_lista = [
                    {"servicio": nombre_s, "cantidad": datos["cantidad"], "monto": datos["monto"]}
                    for nombre_s, datos in resumen_por_servicio.items()
                ]
                detalle_lista.sort(key=lambda x: x["servicio"])

                resultado = {
                    "encargada": encargada_sel["nombre"] if encargada_sel else "—",
                    "fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_fin,
                    "fecha_inicio_fmt": formatear_fecha_dmy(fecha_inicio),
                    "fecha_fin_fmt": formatear_fecha_dmy(fecha_fin),
                    "porcentaje": porcentaje_num,
                    "cantidad_servicios": len(movimientos),
                    "total_produccion": total_produccion,
                    "comision": comision,
                    "detalle": detalle_lista,
                }

    conn.close()

    return render_template("caja_comisiones.html", encargadas=encargadas, resultado=resultado, error=error)


@app.route("/caja/comisiones/marcar-pagada", methods=["POST"])
def caja_comisiones_marcar_pagada():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    pin_ingresado = request.form.get("pin_duena", "").strip()
    encargada_id = request.form.get("encargada_id", "").strip()
    encargada_nombre = request.form.get("encargada_nombre", "").strip()
    monto_comision = request.form.get("monto", "").strip()
    sueldo_base_texto = request.form.get("sueldo_base", "").strip()
    forma_pago = request.form.get("forma_pago_comision", "").strip()
    de_caja_salon = 1 if request.form.get("de_caja_salon") == "si" else 0
    fecha_inicio_rango = request.form.get("fecha_inicio_rango", "").strip()
    fecha_fin_rango = request.form.get("fecha_fin_rango", "").strip()
    porcentaje = request.form.get("porcentaje_rango", "").strip()

    conn = get_conexion()
    cur = conn.cursor()
    pin_real = obtener_pin_duena(cur)

    if pin_ingresado != pin_real:
        conn.close()
        flash("PIN especial incorrecto. No se registró el pago.")
        return redirect(url_for("caja_comisiones"))

    try:
        monto_comision_num = float(monto_comision)
        sueldo_base_num = float(sueldo_base_texto) if sueldo_base_texto else 0.0
    except ValueError:
        conn.close()
        flash("Monto o sueldo base inválido.")
        return redirect(url_for("caja_comisiones"))

    if forma_pago not in ("efectivo", "transferencia"):
        conn.close()
        flash("Selecciona una forma de pago válida.")
        return redirect(url_for("caja_comisiones"))

    monto_total = monto_comision_num + sueldo_base_num

    m = marcador()
    ahora = ahora_gt()
    cur.execute(
        f"INSERT INTO pagos_comisiones (encargada_id, encargada_nombre, fecha_pago, hora_pago, monto, sueldo_base, forma_pago, de_caja_salon, fecha_inicio_rango, fecha_fin_rango, porcentaje) "
        f"VALUES ({m}, {m}, {m}, {m}, {m}, {m}, {m}, {m}, {m}, {m}, {m})",
        (encargada_id or None, encargada_nombre, ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M"),
         monto_total, sueldo_base_num, forma_pago, de_caja_salon, fecha_inicio_rango, fecha_fin_rango, porcentaje or None)
    )
    conn.commit()
    conn.close()

    nota_origen = "" if (forma_pago != "efectivo" or de_caja_salon) else " — fuera de la caja del salón"
    flash(f"Pago registrado: {encargada_nombre} — comisión Q{monto_comision_num:.2f} + sueldo base Q{sueldo_base_num:.2f} = Q{monto_total:.2f} ({forma_pago}{nota_origen}) ✅")
    return redirect(url_for("caja_comisiones"))


@app.route("/caja/comisiones/imprimir")
def caja_comisiones_imprimir():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    encargada_id = request.args.get("encargada_id", "").strip()
    fecha_inicio = request.args.get("fecha_inicio", "").strip()
    fecha_fin = request.args.get("fecha_fin", "").strip()
    porcentaje = request.args.get("porcentaje", "").strip()

    try:
        porcentaje_num = float(porcentaje)
    except ValueError:
        porcentaje_num = 0.0

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM encargadas WHERE id = {m}", (encargada_id,))
    encargada_sel = cur.fetchone()

    cur.execute(
        f"SELECT rs.servicio as servicio, rse.monto_asignado as monto FROM registro_servicio_encargadas rse "
        f"JOIN registro_servicios rs ON rs.id = rse.registro_id "
        f"WHERE rse.encargada_id = {m} AND rs.fecha >= {m} AND rs.fecha <= {m} AND rs.estado_pago = 'pagado'",
        (encargada_id, fecha_inicio, fecha_fin)
    )
    movimientos = cur.fetchall()
    conn.close()

    total_produccion = sum(mv["monto"] for mv in movimientos)
    comision = total_produccion * (porcentaje_num / 100)

    resumen_por_servicio = {}
    for mv in movimientos:
        nombre_s = mv["servicio"]
        if nombre_s not in resumen_por_servicio:
            resumen_por_servicio[nombre_s] = {"cantidad": 0, "monto": 0.0}
        resumen_por_servicio[nombre_s]["cantidad"] += 1
        resumen_por_servicio[nombre_s]["monto"] += mv["monto"]

    detalle_lista = [
        {"servicio": nombre_s, "cantidad": datos["cantidad"], "monto": datos["monto"]}
        for nombre_s, datos in resumen_por_servicio.items()
    ]
    detalle_lista.sort(key=lambda x: x["servicio"])

    return render_template(
        "caja_comisiones_imprimir.html",
        encargada=encargada_sel["nombre"] if encargada_sel else "—",
        fecha_inicio_fmt=formatear_fecha_dmy(fecha_inicio),
        fecha_fin_fmt=formatear_fecha_dmy(fecha_fin),
        porcentaje=porcentaje_num,
        cantidad_servicios=len(movimientos),
        total_produccion=total_produccion,
        comision=comision,
        detalle=detalle_lista,
    )


DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]


def nombre_dia_completo(fecha_str):
    try:
        d = datetime.datetime.strptime(fecha_str, "%Y-%m-%d")
        dia_semana = DIAS_SEMANA[d.weekday()]
        return f"{dia_semana.capitalize()} {d.day} de {MESES_LARGO[d.month - 1]} de {d.year}"
    except Exception:
        return fecha_str


def formatear_fecha_dmy(fecha_str):
    try:
        d = datetime.datetime.strptime(fecha_str, "%Y-%m-%d")
        return d.strftime("%d/%m/%Y")
    except Exception:
        return fecha_str


@app.route("/caja/reporte-dia")
def caja_reporte_dia():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    fecha_vista = request.args.get("fecha", "").strip() or ahora_gt().strftime("%Y-%m-%d")
    m = marcador()

    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM registro_servicios WHERE fecha = {m} ORDER BY id", (fecha_vista,))
    filas = cur.fetchall()
    cur.execute(f"SELECT * FROM gastos_diarios WHERE fecha = {m} ORDER BY id", (fecha_vista,))
    gastos = cur.fetchall()
    cur.execute(f"SELECT * FROM caja_inicial WHERE fecha = {m}", (fecha_vista,))
    fila_caja_inicial = cur.fetchone()
    cur.execute(f"SELECT * FROM depositos_bancarios WHERE fecha = {m} ORDER BY id", (fecha_vista,))
    depositos = cur.fetchall()
    cur.execute(
        f"SELECT COALESCE(SUM(monto),0) as total FROM pagos_comisiones WHERE forma_pago='efectivo' AND de_caja_salon=1 AND fecha_pago = {m}",
        (fecha_vista,)
    )
    total_comisiones_efectivo_caja = cur.fetchone()["total"]
    conn.close()

    caja_inicial = fila_caja_inicial["monto"] if fila_caja_inicial else None
    total_efectivo = sum((f["precio"] - (f["descuento"] or 0)) for f in filas if f["forma_pago"] == "efectivo")
    total_transferencia = sum((f["precio"] - (f["descuento"] or 0)) for f in filas if f["forma_pago"] == "transferencia")
    total_tarjeta = sum((f["precio"] - (f["descuento"] or 0)) for f in filas if f["forma_pago"] == "tarjeta")
    total_pendiente_dia = sum(f["precio"] for f in filas if f["estado_pago"] == "pendiente")
    total_gastos_efectivo = sum(g["monto"] for g in gastos if g["forma_pago"] == "efectivo")
    total_gastos_transferencia = sum(g["monto"] for g in gastos if g["forma_pago"] == "transferencia")
    total_gastos = total_gastos_efectivo + total_gastos_transferencia
    total_depositado_dia = sum(d["monto"] for d in depositos)
    total_neto = total_efectivo + total_transferencia + total_tarjeta - total_gastos_efectivo
    efectivo_esperado = (caja_inicial or 0) + total_efectivo - total_gastos_efectivo - total_comisiones_efectivo_caja
    total_servicios_cantidad = len(filas)
    total_servicios_bruto = sum(f["precio"] for f in filas)
    total_descuentos_dia = sum((f["descuento"] or 0) for f in filas)

    return render_template(
        "caja_reporte_dia.html",
        fecha_vista=fecha_vista,
        fecha_titulo=nombre_dia_completo(fecha_vista),
        filas=filas,
        gastos=gastos,
        depositos=depositos,
        caja_inicial=caja_inicial,
        total_efectivo=total_efectivo,
        total_transferencia=total_transferencia,
        total_tarjeta=total_tarjeta,
        total_pendiente_dia=total_pendiente_dia,
        total_gastos=total_gastos,
        total_gastos_efectivo=total_gastos_efectivo,
        total_gastos_transferencia=total_gastos_transferencia,
        total_depositado_dia=total_depositado_dia,
        total_neto=total_neto,
        total_comisiones_efectivo_caja=total_comisiones_efectivo_caja,
        total_servicios_cantidad=total_servicios_cantidad,
        total_servicios_bruto=total_servicios_bruto,
        total_descuentos_dia=total_descuentos_dia,
        efectivo_esperado=efectivo_esperado,
        formatear_fecha_dmy=formatear_fecha_dmy,
    )


@app.route("/caja/cuaderno")
def caja_cuaderno():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    fecha_vista = request.args.get("fecha", "").strip() or ahora_gt().strftime("%Y-%m-%d")
    m = marcador()

    conn = get_conexion()
    cur = conn.cursor()

    cur.execute(f"SELECT * FROM registro_servicios WHERE fecha = {m} ORDER BY id", (fecha_vista,))
    filas = cur.fetchall()

    cur.execute(f"SELECT * FROM gastos_diarios WHERE fecha = {m} ORDER BY hora", (fecha_vista,))
    gastos = cur.fetchall()

    cur.execute("SELECT * FROM servicios WHERE activo = 1 ORDER BY nombre")
    servicios_disponibles = cur.fetchall()

    cur.execute("SELECT * FROM encargadas WHERE activo = 1 ORDER BY nombre")
    encargadas_disponibles = cur.fetchall()

    cur.execute(f"SELECT * FROM caja_inicial WHERE fecha = {m}", (fecha_vista,))
    fila_caja_inicial = cur.fetchone()

    cur.execute(f"SELECT * FROM depositos_bancarios WHERE fecha = {m} ORDER BY id", (fecha_vista,))
    depositos = cur.fetchall()

    cur.execute(
        f"SELECT COALESCE(SUM(monto),0) as total FROM pagos_comisiones WHERE forma_pago='efectivo' AND de_caja_salon=1 AND fecha_pago = {m}",
        (fecha_vista,)
    )
    total_comisiones_efectivo_caja = cur.fetchone()["total"]

    conn.close()

    caja_inicial = fila_caja_inicial["monto"] if fila_caja_inicial else None

    total_efectivo = sum((f["precio"] - (f["descuento"] or 0)) for f in filas if f["forma_pago"] == "efectivo")
    total_transferencia = sum((f["precio"] - (f["descuento"] or 0)) for f in filas if f["forma_pago"] == "transferencia")
    total_tarjeta = sum((f["precio"] - (f["descuento"] or 0)) for f in filas if f["forma_pago"] == "tarjeta")
    total_pendiente_dia = sum(f["precio"] for f in filas if f["estado_pago"] == "pendiente")
    total_ingresos = total_efectivo + total_transferencia + total_tarjeta
    total_gastos_efectivo = sum(g["monto"] for g in gastos if g["forma_pago"] == "efectivo")
    total_gastos_transferencia = sum(g["monto"] for g in gastos if g["forma_pago"] == "transferencia")
    total_gastos = total_gastos_efectivo + total_gastos_transferencia
    total_depositado_dia = sum(d["monto"] for d in depositos)
    total_neto = total_ingresos - total_gastos_efectivo
    efectivo_esperado = (caja_inicial or 0) + total_efectivo - total_gastos_efectivo - total_comisiones_efectivo_caja
    total_servicios_cantidad = len(filas)
    total_servicios_bruto = sum(f["precio"] for f in filas)
    total_descuentos_dia = sum((f["descuento"] or 0) for f in filas)

    fecha_dt = datetime.datetime.strptime(fecha_vista, "%Y-%m-%d")
    fecha_anterior = (fecha_dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    fecha_siguiente = (fecha_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    return render_template(
        "caja_cuaderno.html",
        fecha_vista=fecha_vista,
        fecha_titulo=nombre_dia_completo(fecha_vista),
        fecha_anterior=fecha_anterior,
        fecha_siguiente=fecha_siguiente,
        filas=filas,
        gastos=gastos,
        depositos=depositos,
        servicios_disponibles=servicios_disponibles,
        encargadas_disponibles=encargadas_disponibles,
        caja_inicial=caja_inicial,
        efectivo_esperado=efectivo_esperado,
        total_efectivo=total_efectivo,
        total_transferencia=total_transferencia,
        total_tarjeta=total_tarjeta,
        total_pendiente_dia=total_pendiente_dia,
        total_ingresos=total_ingresos,
        total_gastos=total_gastos,
        total_gastos_efectivo=total_gastos_efectivo,
        total_gastos_transferencia=total_gastos_transferencia,
        total_depositado_dia=total_depositado_dia,
        total_neto=total_neto,
        total_comisiones_efectivo_caja=total_comisiones_efectivo_caja,
        total_servicios_cantidad=total_servicios_cantidad,
        total_servicios_bruto=total_servicios_bruto,
        total_descuentos_dia=total_descuentos_dia,
    )


@app.route("/caja/cuaderno/set-caja-inicial", methods=["POST"])
def caja_cuaderno_set_caja_inicial():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    fecha_vista = request.form.get("fecha_vista", "").strip() or ahora_gt().strftime("%Y-%m-%d")
    monto = request.form.get("monto_caja_inicial", "").strip()

    try:
        monto_num = float(monto)
    except ValueError:
        flash("La caja inicial debe ser un número válido.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM caja_inicial WHERE fecha = {m}", (fecha_vista,))
    cur.execute(f"INSERT INTO caja_inicial (fecha, monto) VALUES ({m}, {m})", (fecha_vista, monto_num))
    conn.commit()
    conn.close()

    flash(f"Caja inicial guardada: Q{monto_num:.2f} ✅")
    return redirect(url_for("caja_cuaderno", fecha=fecha_vista))


@app.route("/caja/cuaderno/agregar-servicio", methods=["POST"])
def caja_cuaderno_agregar_servicio():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    fecha_vista = request.form.get("fecha_vista", "").strip() or ahora_gt().strftime("%Y-%m-%d")
    nombre_servicio = request.form.get("nombre_servicio", "").strip()
    precio = request.form.get("precio", "").strip()
    encargada_ids = request.form.getlist("encargada_ids")
    observacion = request.form.get("observacion", "").strip()

    if not nombre_servicio or not precio:
        flash("Escribe o elige un servicio con su precio.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    try:
        precio_num = float(precio)
    except ValueError:
        flash("El precio debe ser un número válido.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    ahora = ahora_gt()
    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()

    nombres_encargadas = []
    if encargada_ids:
        placeholders = ", ".join([m] * len(encargada_ids))
        cur.execute(f"SELECT * FROM encargadas WHERE id IN ({placeholders})", tuple(encargada_ids))
        filas_encargadas = cur.fetchall()
        nombres_encargadas = [f["nombre"] for f in filas_encargadas]

    encargada_texto = " + ".join(nombres_encargadas) if nombres_encargadas else "—"

    if USANDO_POSTGRES:
        cur.execute(
            f"INSERT INTO registro_servicios (fecha, hora_registro, nombre_clienta, servicio, precio, encargada, observacion, estado_pago) "
            f"VALUES ({m}, {m}, {m}, {m}, {m}, {m}, {m}, 'pendiente') RETURNING id",
            (fecha_vista, ahora.strftime("%H:%M"), "", nombre_servicio, precio_num, encargada_texto, observacion)
        )
        registro_id = cur.fetchone()["id"]
    else:
        cur.execute(
            f"INSERT INTO registro_servicios (fecha, hora_registro, nombre_clienta, servicio, precio, encargada, observacion, estado_pago) "
            f"VALUES ({m}, {m}, {m}, {m}, {m}, {m}, {m}, 'pendiente')",
            (fecha_vista, ahora.strftime("%H:%M"), "", nombre_servicio, precio_num, encargada_texto, observacion)
        )
        registro_id = cur.lastrowid

    if encargada_ids:
        monto_por_encargada = precio_num / len(encargada_ids)
        for eid in encargada_ids:
            cur.execute(
                f"INSERT INTO registro_servicio_encargadas (registro_id, encargada_id, monto_asignado) VALUES ({m}, {m}, {m})",
                (registro_id, eid, monto_por_encargada)
            )

    conn.commit()
    conn.close()

    return redirect(url_for("caja_cuaderno", fecha=fecha_vista))


@app.route("/caja/cuaderno/eliminar-servicio/<int:fila_id>", methods=["POST"])
def caja_cuaderno_eliminar_servicio(fila_id):
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    fecha_vista = request.form.get("fecha_vista", "")
    pin_ingresado = request.form.get("pin_duena", "").strip()

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()

    pin_real = obtener_pin_duena(cur)
    if pin_ingresado != pin_real:
        conn.close()
        flash("PIN incorrecto. No se eliminó el servicio.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    cur.execute(f"DELETE FROM registro_servicio_encargadas WHERE registro_id = {m}", (fila_id,))
    cur.execute(f"DELETE FROM registro_servicios WHERE id = {m}", (fila_id,))
    conn.commit()
    conn.close()
    flash("Servicio eliminado ✅")
    return redirect(url_for("caja_cuaderno", fecha=fecha_vista))


@app.route("/caja/cuaderno/editar-servicio/<int:fila_id>", methods=["POST"])
def caja_cuaderno_editar_servicio(fila_id):
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    fecha_vista = request.form.get("fecha_vista", "")
    pin_ingresado = request.form.get("pin_duena", "").strip()
    nuevo_servicio = request.form.get("nuevo_servicio", "").strip()
    nuevo_precio = request.form.get("nuevo_precio", "").strip()

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()

    pin_real = obtener_pin_duena(cur)
    if pin_ingresado != pin_real:
        conn.close()
        flash("PIN incorrecto. No se guardaron los cambios.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    if not nuevo_servicio or not nuevo_precio:
        conn.close()
        flash("Escribe el nombre del servicio y el precio.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    try:
        precio_num = float(nuevo_precio)
    except ValueError:
        conn.close()
        flash("El precio debe ser un número válido.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    cur.execute(
        f"UPDATE registro_servicios SET servicio = {m}, precio = {m} WHERE id = {m}",
        (nuevo_servicio, precio_num, fila_id)
    )
    conn.commit()
    conn.close()
    flash("Servicio actualizado ✅")
    return redirect(url_for("caja_cuaderno", fecha=fecha_vista))


@app.route("/caja/cuaderno/cobrar", methods=["POST"])
def caja_cuaderno_cobrar():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    fecha_vista = request.form.get("fecha_vista", "")
    ids_seleccionados = request.form.getlist("ids")
    forma_pago = request.form.get("forma_pago", "").strip()
    descuento_texto = request.form.get("descuento", "").strip()
    tipo_descuento = request.form.get("tipo_descuento", "monto").strip()

    if not ids_seleccionados or forma_pago not in ("efectivo", "transferencia", "tarjeta"):
        flash("Selecciona al menos un servicio y una forma de pago válida.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    try:
        descuento_valor = float(descuento_texto) if descuento_texto else 0.0
    except ValueError:
        flash("El descuento debe ser un número válido.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    m = marcador()
    ahora = ahora_gt()
    conn = get_conexion()
    cur = conn.cursor()

    filas_seleccionadas = []
    for sid in ids_seleccionados:
        cur.execute(f"SELECT id, precio FROM registro_servicios WHERE id = {m}", (sid,))
        fila = cur.fetchone()
        if fila:
            filas_seleccionadas.append(fila)

    subtotal = sum(f["precio"] for f in filas_seleccionadas)

    if tipo_descuento == "porcentaje":
        if descuento_valor < 0 or descuento_valor > 100:
            conn.close()
            flash("El porcentaje de descuento debe estar entre 0 y 100.")
            return redirect(url_for("caja_cuaderno", fecha=fecha_vista))
        descuento_total = round(subtotal * (descuento_valor / 100), 2)
    else:
        descuento_total = descuento_valor

    if descuento_total < 0 or descuento_total > subtotal:
        conn.close()
        flash("El descuento no puede ser mayor al total seleccionado.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    total_cobrado = subtotal - descuento_total

    for fila in filas_seleccionadas:
        descuento_fila = 0.0
        if descuento_total > 0 and subtotal > 0:
            descuento_fila = round(fila["precio"] / subtotal * descuento_total, 2)
        cur.execute(
            f"UPDATE registro_servicios SET estado_pago = 'pagado', forma_pago = {m}, fecha_pago = {m}, hora_pago = {m}, descuento = {m} WHERE id = {m}",
            (forma_pago, ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M"), descuento_fila, fila["id"])
        )

    conn.commit()
    conn.close()

    if descuento_total > 0:
        if tipo_descuento == "porcentaje":
            flash(f"Cobro registrado: Q{total_cobrado:.2f} (descuento del {descuento_valor:.0f}% = Q{descuento_total:.2f}) ✅")
        else:
            flash(f"Cobro registrado: Q{total_cobrado:.2f} (descuento de Q{descuento_total:.2f} aplicado) ✅")
    else:
        flash(f"Cobro registrado: Q{total_cobrado:.2f} ✅")
    return redirect(url_for("caja_cuaderno", fecha=fecha_vista))


@app.route("/caja/cuaderno/agregar-gasto", methods=["POST"])
def caja_cuaderno_agregar_gasto():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    fecha_vista = request.form.get("fecha_vista", "").strip() or ahora_gt().strftime("%Y-%m-%d")
    concepto = request.form.get("concepto", "").strip()
    monto = request.form.get("monto", "").strip()
    forma_pago_gasto = request.form.get("forma_pago_gasto", "efectivo").strip()
    if forma_pago_gasto not in ("efectivo", "transferencia"):
        forma_pago_gasto = "efectivo"

    if not concepto or not monto:
        flash("Escribe el concepto y el monto del gasto.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    try:
        monto_num = float(monto)
    except ValueError:
        flash("El monto debe ser un número válido.")
        return redirect(url_for("caja_cuaderno", fecha=fecha_vista))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO gastos_diarios (fecha, hora, concepto, monto, forma_pago) VALUES ({m}, {m}, {m}, {m}, {m})",
        (fecha_vista, ahora_gt().strftime("%H:%M"), concepto, monto_num, forma_pago_gasto)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("caja_cuaderno", fecha=fecha_vista))


@app.route("/caja/cuaderno/eliminar-gasto/<int:gasto_id>", methods=["POST"])
def caja_cuaderno_eliminar_gasto(gasto_id):
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    fecha_vista = request.form.get("fecha_vista", "")
    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM gastos_diarios WHERE id = {m}", (gasto_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("caja_cuaderno", fecha=fecha_vista))


@app.route("/caja/banco", methods=["GET"])
def caja_banco():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    if not session.get("banco_autorizado"):
        return render_template("caja_banco_pin.html", error=None)

    mes_param = request.args.get("mes", "").strip() or ahora_gt().strftime("%Y-%m")
    try:
        anio_b, mes_b = map(int, mes_param.split("-"))
    except Exception:
        anio_b, mes_b = ahora_gt().year, ahora_gt().month
        mes_param = f"{anio_b:04d}-{mes_b:02d}"
    ultimo_dia_b = calendar.monthrange(anio_b, mes_b)[1]
    fecha_inicio_mes = f"{anio_b:04d}-{mes_b:02d}-01"
    fecha_fin_mes = f"{anio_b:04d}-{mes_b:02d}-{ultimo_dia_b:02d}"
    nombre_mes_banco = f"{MESES_LARGO[mes_b - 1].capitalize()} {anio_b}"

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()

    # Saldo esperado: SIEMPRE historico/acumulado, no se filtra por mes
    cur.execute("SELECT COALESCE(SUM(precio - COALESCE(descuento, 0)), 0) as total FROM registro_servicios WHERE forma_pago = 'transferencia'")
    total_transferencias = cur.fetchone()["total"]

    cur.execute("SELECT COALESCE(SUM(monto), 0) as total FROM depositos_bancarios")
    total_depositos = cur.fetchone()["total"]

    cur.execute("SELECT COALESCE(SUM(monto), 0) as total FROM gastos_diarios WHERE forma_pago = 'transferencia'")
    total_gastos_banco = cur.fetchone()["total"]

    cur.execute("SELECT COALESCE(SUM(monto), 0) as total FROM pagos_comisiones WHERE forma_pago = 'transferencia'")
    total_comisiones_banco = cur.fetchone()["total"]

    saldo_esperado = total_transferencias + total_depositos - total_gastos_banco - total_comisiones_banco

    # Listados de detalle: SI se filtran por el mes elegido
    cur.execute(
        f"SELECT * FROM depositos_bancarios WHERE fecha_registro >= {m} AND fecha_registro <= {m} ORDER BY fecha_registro DESC, id DESC",
        (fecha_inicio_mes, fecha_fin_mes)
    )
    depositos = cur.fetchall()

    cur.execute(
        f"SELECT * FROM gastos_diarios WHERE forma_pago = 'transferencia' AND fecha >= {m} AND fecha <= {m} ORDER BY fecha DESC, id DESC",
        (fecha_inicio_mes, fecha_fin_mes)
    )
    gastos_banco = cur.fetchall()

    cur.execute(
        f"SELECT * FROM pagos_comisiones WHERE forma_pago = 'transferencia' AND fecha_pago >= {m} AND fecha_pago <= {m} ORDER BY fecha_pago DESC, id DESC",
        (fecha_inicio_mes, fecha_fin_mes)
    )
    comisiones_banco = cur.fetchall()

    cur.execute(
        f"SELECT * FROM pagos_comisiones WHERE forma_pago = 'efectivo' AND fecha_pago >= {m} AND fecha_pago <= {m} ORDER BY fecha_pago DESC, id DESC",
        (fecha_inicio_mes, fecha_fin_mes)
    )
    comisiones_efectivo = cur.fetchall()

    # Efectivo por depositar, agrupado por dia del cuaderno dentro del mes elegido
    cur.execute(
        f"SELECT fecha, SUM(precio - COALESCE(descuento,0)) as total_dia FROM registro_servicios "
        f"WHERE forma_pago = 'efectivo' AND estado_pago = 'pagado' AND fecha >= {m} AND fecha <= {m} "
        f"GROUP BY fecha ORDER BY fecha DESC",
        (fecha_inicio_mes, fecha_fin_mes)
    )
    dias_con_efectivo = cur.fetchall()

    efectivo_por_depositar = []
    for fila_dia in dias_con_efectivo:
        cur.execute(f"SELECT COALESCE(SUM(monto),0) as total FROM depositos_bancarios WHERE fecha = {m}", (fila_dia["fecha"],))
        depositado_ese_dia = cur.fetchone()["total"]
        cobrado = fila_dia["total_dia"]
        pendiente = round(cobrado - depositado_ese_dia, 2)
        efectivo_por_depositar.append({
            "fecha": fila_dia["fecha"],
            "fecha_fmt": formatear_fecha_dmy(fila_dia["fecha"]),
            "cobrado": cobrado,
            "depositado": depositado_ese_dia,
            "pendiente": pendiente,
            "estado": "Depositado" if pendiente <= 0 else "Pendiente de depositar",
        })

    conn.close()

    fecha_dt_b = datetime.datetime.strptime(fecha_inicio_mes, "%Y-%m-%d")
    if mes_b == 1:
        mes_anterior_param = f"{anio_b - 1:04d}-12"
    else:
        mes_anterior_param = f"{anio_b:04d}-{mes_b - 1:02d}"
    if mes_b == 12:
        mes_siguiente_param = f"{anio_b + 1:04d}-01"
    else:
        mes_siguiente_param = f"{anio_b:04d}-{mes_b + 1:02d}"

    return render_template(
        "caja_banco.html",
        mes_param=mes_param,
        nombre_mes_banco=nombre_mes_banco,
        mes_anterior_param=mes_anterior_param,
        mes_siguiente_param=mes_siguiente_param,
        total_transferencias=total_transferencias,
        total_depositos=total_depositos,
        total_gastos_banco=total_gastos_banco,
        total_comisiones_banco=total_comisiones_banco,
        saldo_esperado=saldo_esperado,
        depositos=depositos,
        gastos_banco=gastos_banco,
        comisiones_banco=comisiones_banco,
        comisiones_efectivo=comisiones_efectivo,
        efectivo_por_depositar=efectivo_por_depositar,
        formatear_fecha_dmy=formatear_fecha_dmy,
    )


@app.route("/caja/banco/verificar", methods=["POST"])
def caja_banco_verificar():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    pin_ingresado = request.form.get("pin_duena", "").strip()
    conn = get_conexion()
    cur = conn.cursor()
    pin_real = obtener_pin_duena(cur)
    conn.close()

    if pin_ingresado == pin_real:
        session["banco_autorizado"] = True
        return redirect(url_for("caja_banco"))

    return render_template("caja_banco_pin.html", error="PIN especial incorrecto.")


@app.route("/caja/banco/cerrar", methods=["POST"])
def caja_banco_cerrar():
    session.pop("banco_autorizado", None)
    return redirect(url_for("panel"))


@app.route("/caja/banco/agregar-deposito", methods=["POST"])
def caja_banco_agregar_deposito():
    if not session.get("staff_activo") or not session.get("banco_autorizado"):
        return redirect(url_for("caja_banco"))

    fecha_cuaderno = request.form.get("fecha_cuaderno", "").strip() or ahora_gt().strftime("%Y-%m-%d")
    monto = request.form.get("monto_deposito", "").strip()
    numero_deposito = request.form.get("numero_deposito", "").strip()
    observacion = request.form.get("observacion_deposito", "").strip()

    if not monto:
        flash("Escribe el monto del depósito.")
        return redirect(url_for("caja_banco"))

    try:
        monto_num = float(monto)
    except ValueError:
        flash("El monto del depósito debe ser un número válido.")
        return redirect(url_for("caja_banco"))

    m = marcador()
    ahora = ahora_gt()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO depositos_bancarios (fecha, fecha_registro, hora, monto, numero_deposito, observacion) VALUES ({m}, {m}, {m}, {m}, {m}, {m})",
        (fecha_cuaderno, ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M"), monto_num, numero_deposito, observacion)
    )
    conn.commit()
    conn.close()

    flash(f"Depósito registrado: Q{monto_num:.2f} (corresponde al {formatear_fecha_dmy(fecha_cuaderno)}) ✅")
    return redirect(url_for("caja_banco"))


@app.route("/caja/banco/eliminar-deposito/<int:deposito_id>", methods=["POST"])
def caja_banco_eliminar_deposito(deposito_id):
    if not session.get("staff_activo") or not session.get("banco_autorizado"):
        return redirect(url_for("caja_banco"))

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM depositos_bancarios WHERE id = {m}", (deposito_id,))
    conn.commit()
    conn.close()
    flash("Depósito eliminado ✅")
    return redirect(url_for("caja_banco"))


def generar_observaciones_mes(actual, anterior, cambios, desempeno):
    observaciones = []

    if cambios["ingresos"] is not None:
        if cambios["ingresos"] > 5:
            observaciones.append(f"📈 Los ingresos subieron {cambios['ingresos']:.1f}% respecto al mes anterior. ¡Buen mes!")
        elif cambios["ingresos"] < -5:
            observaciones.append(f"📉 Los ingresos bajaron {abs(cambios['ingresos']):.1f}% respecto al mes anterior. Vale la pena revisar si hubo menos clientas, menos servicios por día, o alguna temporada baja.")
        else:
            observaciones.append("➡️ Los ingresos se mantuvieron estables respecto al mes anterior.")

    if cambios["gastos"] is not None and cambios["gastos"] > 20:
        observaciones.append(f"⚠️ Los gastos subieron {cambios['gastos']:.1f}%. Revisa si hubo compras grandes que se puedan planificar mejor el próximo mes.")

    if cambios["neto"] is not None:
        if cambios["neto"] > 0:
            observaciones.append(f"✅ La ganancia neta mejoró {cambios['neto']:.1f}% respecto al mes anterior.")
        elif cambios["neto"] < 0:
            observaciones.append(f"🔻 La ganancia neta bajó {abs(cambios['neto']):.1f}% respecto al mes anterior.")

    if desempeno:
        cantidad_maxima = max(d["cantidad_actual"] for d in desempeno)
        if cantidad_maxima > 0:
            empatadas = [d["nombre"] for d in desempeno if d["cantidad_actual"] == cantidad_maxima]
            if len(empatadas) == 1:
                observaciones.append(f"🏆 {empatadas[0]} fue quien más servicios realizó este mes ({cantidad_maxima}).")
            else:
                nombres = ", ".join(empatadas[:-1]) + " y " + empatadas[-1]
                observaciones.append(f"🏆 {nombres} empataron como quienes más servicios realizaron este mes ({cantidad_maxima} cada una).")

        for d in desempeno:
            if d["cantidad_anterior"] > 0 and d["cantidad_actual"] < d["cantidad_anterior"] * 0.7:
                observaciones.append(f"👀 {d['nombre']} bajó bastante su cantidad de servicios este mes ({d['cantidad_anterior']} → {d['cantidad_actual']}). Puede valer la pena conversar con ella.")
            elif d["cantidad_anterior"] > 0 and d["cantidad_actual"] > d["cantidad_anterior"] * 1.3:
                observaciones.append(f"🌟 {d['nombre']} aumentó bastante su cantidad de servicios este mes ({d['cantidad_anterior']} → {d['cantidad_actual']}).")

    if not observaciones:
        observaciones.append("Todavía no hay suficientes datos de meses anteriores para comparar a fondo.")

    return observaciones


@app.route("/caja/reporte-mes")
def caja_reporte_mes():
    if not session.get("staff_activo"):
        return redirect(url_for("pin"))

    mes_param = request.args.get("mes", "").strip() or ahora_gt().strftime("%Y-%m")
    try:
        anio, mes = map(int, mes_param.split("-"))
    except Exception:
        anio, mes = ahora_gt().year, ahora_gt().month
        mes_param = f"{anio:04d}-{mes:02d}"

    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fecha_inicio = f"{anio:04d}-{mes:02d}-01"
    fecha_fin = f"{anio:04d}-{mes:02d}-{ultimo_dia:02d}"

    if mes == 1:
        anio_ant, mes_ant = anio - 1, 12
    else:
        anio_ant, mes_ant = anio, mes - 1
    ultimo_dia_ant = calendar.monthrange(anio_ant, mes_ant)[1]
    fecha_inicio_ant = f"{anio_ant:04d}-{mes_ant:02d}-01"
    fecha_fin_ant = f"{anio_ant:04d}-{mes_ant:02d}-{ultimo_dia_ant:02d}"

    m = marcador()
    conn = get_conexion()
    cur = conn.cursor()

    def totales_periodo(f_ini, f_fin):
        cur.execute(
            f"SELECT COALESCE(SUM(precio - COALESCE(descuento,0)),0) as total FROM registro_servicios "
            f"WHERE estado_pago='pagado' AND forma_pago='efectivo' AND fecha >= {m} AND fecha <= {m}",
            (f_ini, f_fin)
        )
        efectivo = cur.fetchone()["total"]
        cur.execute(
            f"SELECT COALESCE(SUM(precio - COALESCE(descuento,0)),0) as total FROM registro_servicios "
            f"WHERE estado_pago='pagado' AND forma_pago='transferencia' AND fecha >= {m} AND fecha <= {m}",
            (f_ini, f_fin)
        )
        transferencia = cur.fetchone()["total"]
        cur.execute(
            f"SELECT COALESCE(SUM(precio - COALESCE(descuento,0)),0) as total FROM registro_servicios "
            f"WHERE estado_pago='pagado' AND forma_pago='tarjeta' AND fecha >= {m} AND fecha <= {m}",
            (f_ini, f_fin)
        )
        tarjeta = cur.fetchone()["total"]
        cur.execute(
            f"SELECT COALESCE(SUM(monto),0) as total FROM gastos_diarios WHERE forma_pago='efectivo' AND fecha >= {m} AND fecha <= {m}",
            (f_ini, f_fin)
        )
        gastos_efectivo = cur.fetchone()["total"]
        cur.execute(
            f"SELECT COALESCE(SUM(monto),0) as total FROM gastos_diarios WHERE forma_pago='transferencia' AND fecha >= {m} AND fecha <= {m}",
            (f_ini, f_fin)
        )
        gastos_transferencia = cur.fetchone()["total"]
        gastos = gastos_efectivo + gastos_transferencia

        cur.execute(
            f"SELECT COUNT(*) as cantidad, COALESCE(SUM(precio),0) as bruto, COALESCE(SUM(descuento),0) as descuentos "
            f"FROM registro_servicios WHERE fecha >= {m} AND fecha <= {m}",
            (f_ini, f_fin)
        )
        fila_servicios = cur.fetchone()
        cantidad_servicios = fila_servicios["cantidad"]
        monto_bruto_servicios = fila_servicios["bruto"]
        monto_descuentos = fila_servicios["descuentos"]

        cur.execute(
            f"SELECT COALESCE(SUM(precio),0) as total FROM registro_servicios "
            f"WHERE estado_pago='pendiente' AND fecha >= {m} AND fecha <= {m}",
            (f_ini, f_fin)
        )
        pendiente_cierre = cur.fetchone()["total"]

        cur.execute(
            f"SELECT COALESCE(SUM(monto),0) as total FROM pagos_comisiones WHERE fecha_pago >= {m} AND fecha_pago <= {m}",
            (f_ini, f_fin)
        )
        comisiones_pagadas = cur.fetchone()["total"]

        cur.execute(
            f"SELECT COALESCE(SUM(monto),0) as total FROM depositos_bancarios WHERE fecha_registro >= {m} AND fecha_registro <= {m}",
            (f_ini, f_fin)
        )
        depositado_mes = cur.fetchone()["total"]

        ingresos = efectivo + transferencia + tarjeta
        neto = ingresos - gastos_efectivo

        return {
            "efectivo": efectivo, "transferencia": transferencia, "tarjeta": tarjeta,
            "ingresos": ingresos, "gastos": gastos, "gastos_efectivo": gastos_efectivo,
            "gastos_transferencia": gastos_transferencia, "neto": neto,
            "cantidad_servicios": cantidad_servicios, "monto_bruto_servicios": monto_bruto_servicios,
            "monto_descuentos": monto_descuentos, "pendiente_cierre": pendiente_cierre,
            "comisiones_pagadas": comisiones_pagadas, "depositado_mes": depositado_mes,
        }

    actual = totales_periodo(fecha_inicio, fecha_fin)
    anterior = totales_periodo(fecha_inicio_ant, fecha_fin_ant)

    def cambio_pct(actual_v, anterior_v):
        if anterior_v == 0:
            return None
        return (actual_v - anterior_v) / anterior_v * 100

    cambios = {
        "ingresos": cambio_pct(actual["ingresos"], anterior["ingresos"]),
        "gastos": cambio_pct(actual["gastos"], anterior["gastos"]),
        "neto": cambio_pct(actual["neto"], anterior["neto"]),
        "cantidad_servicios": cambio_pct(actual["cantidad_servicios"], anterior["cantidad_servicios"]),
        "monto_bruto_servicios": cambio_pct(actual["monto_bruto_servicios"], anterior["monto_bruto_servicios"]),
        "monto_descuentos": cambio_pct(actual["monto_descuentos"], anterior["monto_descuentos"]),
    }

    cur.execute("SELECT * FROM encargadas ORDER BY nombre")
    encargadas = cur.fetchall()

    desempeno = []
    for e in encargadas:
        cur.execute(
            f"SELECT COUNT(*) as cantidad, COALESCE(SUM(rse.monto_asignado),0) as produccion "
            f"FROM registro_servicio_encargadas rse JOIN registro_servicios rs ON rs.id = rse.registro_id "
            f"WHERE rse.encargada_id = {m} AND rs.estado_pago='pagado' AND rs.fecha >= {m} AND rs.fecha <= {m}",
            (e["id"], fecha_inicio, fecha_fin)
        )
        actual_e = cur.fetchone()
        cur.execute(
            f"SELECT COUNT(*) as cantidad, COALESCE(SUM(rse.monto_asignado),0) as produccion "
            f"FROM registro_servicio_encargadas rse JOIN registro_servicios rs ON rs.id = rse.registro_id "
            f"WHERE rse.encargada_id = {m} AND rs.estado_pago='pagado' AND rs.fecha >= {m} AND rs.fecha <= {m}",
            (e["id"], fecha_inicio_ant, fecha_fin_ant)
        )
        anterior_e = cur.fetchone()

        if actual_e["cantidad"] > 0 or anterior_e["cantidad"] > 0:
            desempeno.append({
                "nombre": e["nombre"],
                "cantidad_actual": actual_e["cantidad"],
                "produccion_actual": actual_e["produccion"],
                "cantidad_anterior": anterior_e["cantidad"],
                "produccion_anterior": anterior_e["produccion"],
                "cambio_cantidad": cambio_pct(actual_e["cantidad"], anterior_e["cantidad"]),
            })

    conn.close()

    observaciones = generar_observaciones_mes(actual, anterior, cambios, desempeno)

    return render_template(
        "caja_reporte_mes.html",
        mes_param=mes_param,
        nombre_mes=f"{MESES_LARGO[mes - 1].capitalize()} {anio}",
        nombre_mes_anterior=f"{MESES_LARGO[mes_ant - 1].capitalize()} {anio_ant}",
        actual=actual,
        anterior=anterior,
        cambios=cambios,
        desempeno=desempeno,
        observaciones=observaciones,
    )


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