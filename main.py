"""
main.py - Interfaz web de MotoExpert (Streamlit) conectada a Prolog con PySwip.

Arquitectura híbrida:
  - Capa imperativa (este archivo y motor.py): interfaz gráfica, captura y
    limpieza de las entradas, y presentación de resultados. Python no
    decide nada del dominio.
  - Capa simbólica (base_conocimiento.pl): inferencia, encadenamiento,
    traza de explicación ("¿Por qué?") y datos sugeridos ("¿Qué falta?").

Prolog nunca lee de la entrada estándar (sin read/1): en cada recarga de la
página se le envía la lista completa [obs(Variable, Valor), ...] y se
recogen sus resultados. El estado de la consulta vive en st.session_state.

Diseño: tema en .streamlit/config.toml y estilos de los componentes propios
en estilos.css. Todo texto que viene de Prolog se escapa antes de insertarlo
como HTML.

Uso:  streamlit run main.py      (en Windows: py -m streamlit run main.py)

Autor: Bredman Estiven Velez Cortez
"""

from __future__ import annotations

import html
import os
import re

import streamlit as st

from motor import ErrorMotor, MotorMotoExpert, limpiar_observaciones, limpiar_valor

CARPETA = os.path.dirname(os.path.abspath(__file__))
RUTA_ESTILOS = os.path.join(CARPETA, "estilos.css")
RUTA_ICONO = os.path.join(CARPETA, "icono.svg")

st.set_page_config(page_title="MotoExpert", page_icon=RUTA_ICONO, layout="wide")

# Tokens de color por tema. Grises acerados con sesgo hacia el acento;
# los colores de severidad solo se usan para la prioridad y el estado.
PALETA = {
    "light": {
        "bg": "#F4F6F7", "panel": "#FFFFFF", "sunk": "#E9EEF0", "fg": "#1A2227",
        "muted": "#56636B", "line": "#D3DBDF", "accent": "#0B7480", "accent-soft": "#DCEEF0",
        "crit": "#B42318", "crit-soft": "#FCEBE8", "alta": "#B05800", "alta-soft": "#FDF1E3",
        "media": "#2C64A0", "baja": "#3F6F45", "sobre": "#FFFFFF",
    },
    "dark": {
        "bg": "#0E1316", "panel": "#151C20", "sunk": "#1C252A", "fg": "#E2E8EB",
        "muted": "#97A4AC", "line": "#2A353B", "accent": "#46B5BE", "accent-soft": "#16313A",
        "crit": "#F06A5E", "crit-soft": "#3A1B18", "alta": "#F0A04B", "alta-soft": "#33261A",
        "media": "#74A9E0", "baja": "#86BC8C", "sobre": "#0E1316",
    },
}

# Textos de presentación (no son conocimiento del dominio).
ESTADO = {
    "con_resultados": ("Con resultados", "ok"),
    "datos_insuficientes": ("Datos insuficientes", "aviso"),
    "sin_diagnostico_concluyente": ("Sin diagnóstico concluyente", "aviso"),
    "fuera_de_alcance": ("Fuera de alcance", "critico"),
    "sin_datos": ("Sin datos", "aviso"),
}
TITULO_SITUACION = {
    "definitivo": "Dictamen definitivo",
    "empate": "Empate entre hipótesis",
    "insuficiente": "Evidencia insuficiente",
    "sin_hipotesis": "Sin hipótesis activas",
    "fuera_de_alcance": "Fuera de alcance",
}
TITULO_ALTERNATIVA = {
    "descartada": "Descartada por verificación",
    "excluida": "Excluida por condición (\\+)",
    "sin_evidencia_critica": "Falta evidencia crítica",
}
TITULO_TIPO = {"basica": "Verificación básica", "diagnostico": "Diagnóstico preliminar"}
NOTA_TIPO = {"revision": "requiere revisarla", "prueba_tecnica": "solo si la hizo un técnico"}
GRUPO_CORTO = {"general": "General", "electrico": "Eléctrico", "motor": "Motor",
               "combustible": "Combustible", "encendido": "Encendido"}
SEGMENTOS_RESPALDO = {"bajo": 1, "medio": 2, "alto": 3}
FASES = ["Admisión", "Seguridad", "Verificación básica", "Arranque", "Diferenciación"]
CASO_EJEMPLO = [
    ("cilindrada", 150), ("alimentacion", "carburador"), ("fuga_combustible", "no"),
    ("olor_gasolina", "no"), ("sobrecalentamiento", "no"), ("interruptor_paro", "marcha"),
    ("nivel_combustible", "medio"), ("giro_arranque", "lento"), ("luces", "debil"),
]


# ---------------------------------------------------------------------------
# Conexión con Prolog (una sola carga por proceso)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Cargando la base de conocimiento...")
def obtener_motor() -> MotorMotoExpert:
    return MotorMotoExpert()


@st.cache_data
def obtener_catalogo() -> list[dict]:
    return obtener_motor().catalogo()


@st.cache_data
def leer_estilos() -> str:
    with open(RUTA_ESTILOS, encoding="utf-8") as archivo:
        return archivo.read()


# ---------------------------------------------------------------------------
# Estado de la sesión: lista de observaciones en el orden en que se dieron
# ---------------------------------------------------------------------------
def observaciones() -> list[tuple[str, object]]:
    return limpiar_observaciones(st.session_state.setdefault("obs", []))


def registrar(variable: str, valor) -> None:
    """Guarda una respuesta; si la variable ya tenía valor, lo reemplaza."""
    obs = [(v, x) for v, x in st.session_state.obs if v != variable]
    obs.append((variable, valor))
    st.session_state.obs = obs


def reiniciar() -> None:
    st.session_state.obs = []


def deshacer() -> None:
    st.session_state.obs = st.session_state.obs[:-1]


def cargar_ejemplo() -> None:
    st.session_state.obs = list(CASO_EJEMPLO)


# ---------------------------------------------------------------------------
# Utilidades de presentación
# ---------------------------------------------------------------------------
def e(texto) -> str:
    """Escapa texto de Prolog para insertarlo en HTML."""
    return html.escape(str(texto))


def mayus_inicial(texto: str) -> str:
    """Primera letra en mayúscula sin tocar el resto ("RUN (encendido)" se conserva)."""
    texto = str(texto)
    return texto[:1].upper() + texto[1:]


def bloque(contenido: str) -> None:
    st.html(contenido)


def titulo_seccion(texto: str, ancla: str = "") -> None:
    id_html = f' id="{ancla}"' if ancla else ""
    bloque(f'<h2 class="mx-h"{id_html}>{e(texto)}</h2>')


def aplicar_estilos() -> None:
    tema = st.context.theme.type if st.context.theme.type in PALETA else "light"
    tokens = ";".join(f"--{k}:{v}" for k, v in PALETA[tema].items())
    st.html(f"<style>:root{{{tokens}}}\n{leer_estilos()}</style>")
    # Streamlit declara la página en inglés y Chrome ofrece "traducirla",
    # lo que cambia términos ("Reglas disparadas" -> "Reglas dispersas").
    # Se declara el idioma español y se pide no traducir.
    st.iframe(
        "<script>const d = window.parent.document;"
        "d.documentElement.lang = 'es';"
        "d.documentElement.setAttribute('translate', 'no');"
        "d.body.classList.add('notranslate');</script>",
        height=1, alt="Idioma de la página")


def texto_valor(catalogo: dict, variable: str, valor) -> tuple[str, str]:
    info = catalogo.get(variable)
    if info is None:
        return variable, str(valor)
    textos = {o["valor"]: o["texto"] for o in info["opciones"]}
    return info["etiqueta"], mayus_inicial(textos.get(valor, valor))


def indicador_respaldo(respaldo: str) -> str:
    n = SEGMENTOS_RESPALDO.get(respaldo, 0)
    segmentos = "".join('<i class="on"></i>' if i < n else "<i></i>" for i in range(3))
    return f'<span class="mx-gauge" aria-hidden="true">{segmentos}</span>'


def resaltar_valores(texto: str) -> str:
    """Pone en negrita el valor «entre comillas» de un efecto sugerido."""
    return re.sub(r"«([^»]*)»", r"<b>\1</b>", e(texto))


def fase_de(motivo: str) -> str:
    prefijo = motivo.split(":", 1)[0]
    return prefijo if prefijo in FASES else "Diferenciación"


# ---------------------------------------------------------------------------
# Captura de respuestas
# ---------------------------------------------------------------------------
def formulario_respuesta(info: dict, clave: str) -> None:
    """Pregunta de una variable con botones Responder y No lo sé."""
    variable = info["variable"]
    with st.form(f"form_{clave}_{variable}", clear_on_submit=True, border=False):
        st.markdown(f"**{info['pregunta']}**")
        if info["entrada"] == "numerico":
            texto = st.text_input(info["etiqueta"], placeholder="Escriba un número, por ejemplo 150 o 12,5",
                                  label_visibility="collapsed")
        else:
            opciones = [o for o in info["opciones"] if o["valor"] != "desconocido"]
            elegida = st.radio(info["etiqueta"], opciones, index=None, horizontal=True,
                               format_func=lambda o: mayus_inicial(o["texto"]),
                               label_visibility="collapsed")
        # Fila horizontal: cada botón toma el ancho de su texto y, si no
        # caben, pasan a la línea siguiente en lugar de recortarse.
        with st.container(horizontal=True, gap="small"):
            responder = st.form_submit_button("Responder", type="primary")
            no_se = st.form_submit_button("No lo sé")

    if no_se:
        registrar(variable, "desconocido")
        st.rerun()
    if responder:
        if info["entrada"] == "numerico":
            valor = limpiar_valor(texto)
            if not isinstance(valor, (int, float)):
                st.warning("Escriba un número o use «No lo sé».")
                return
        else:
            if elegida is None:
                st.warning("Elija una opción o use «No lo sé».")
                return
            valor = elegida["valor"]
        registrar(variable, valor)
        st.rerun()


def fases_html(actual: str | None) -> str:
    """Las cinco fases del triaje; las anteriores a la actual quedan hechas."""
    indice = FASES.index(actual) if actual in FASES else len(FASES)
    items = []
    for i, fase in enumerate(FASES):
        clase = "hecha" if i < indice else "actual" if i == indice else ""
        items.append(f'<li class="{clase}">{e(fase)}</li>')
    return f'<ol class="mx-fases" aria-label="Fases de la entrevista">{"".join(items)}</ol>'


def entrevista_guiada(motor: MotorMotoExpert, catalogo: dict) -> None:
    obs = observaciones()
    variable = motor.siguiente_pregunta(obs)
    if variable is None:
        bloque(fases_html(None))
        st.success("La entrevista terminó: ninguna pregunta pendiente cambiaría el resultado. "
                   "Revise el dictamen y la auditoría.")
        boton_volver(obs)
        return
    motivo = motor.por_que(obs, variable)
    fase = fase_de(motivo)
    bloque(fases_html(fase))
    with st.container(border=True):
        bloque(f'<p class="mx-eyebrow">Pregunta {len(obs) + 1} · {e(fase)}</p>')
        formulario_respuesta(catalogo[variable], "guiada")
        bloque(f'<p class="mx-motivo"><b>Por qué</b>{e(motivo)}</p>')
        boton_volver(obs)


def boton_volver(obs: list) -> None:
    """Quita la última respuesta; Prolog vuelve a elegir esa misma pregunta."""
    st.button("← Volver a la pregunta anterior", on_click=deshacer, disabled=not obs,
              type="tertiary", key="volver_guiada")


def aviso_empate(falta: dict) -> None:
    """Aviso visible cuando la evidencia queda empatada entre hipótesis."""
    if falta["situacion"] != "empate":
        st.session_state.ultima_situacion = falta["situacion"]
        return
    nombres = " y ".join(f"{h['codigo'].upper()} ({h['nombre']})" for h in falta["evaluadas"])
    sugerido = falta["sugerencias"][0]["etiqueta"] if falta["sugerencias"] else None
    if st.session_state.get("ultima_situacion") != "empate":
        st.toast("Empate entre hipótesis: responda el dato sugerido en «¿Qué falta?».", icon="⚖️")
    st.session_state.ultima_situacion = "empate"
    accion = (f'Para desempatar, responda el dato sugerido: <b>{e(sugerido)}</b>.'
              if sugerido else "No quedan datos que desempaten; se recomienda revisión profesional.")
    bloque(f'<div class="mx-aviso" role="status"><p class="mx-aviso-et">Empate entre hipótesis</p>'
           f'<p class="mx-p">{e(nombres)} tienen el mismo respaldo. {accion}</p>'
           f'<a class="mx-aviso-ir" href="#que-falta">Ir a «¿Qué falta?» ↓</a></div>')


def campo_libre(info: dict, actual) -> object:
    """Un campo del ingreso libre: botones de opción o, si es numérico, una caja de texto."""
    nota = NOTA_TIPO.get(info["tipo"])
    etiqueta = f"{info['etiqueta']} :gray[· {nota}]" if nota else info["etiqueta"]
    if info["entrada"] == "numerico":
        return st.text_input(etiqueta, help=info["pregunta"], placeholder="Escriba un número o déjelo vacío",
                             value="" if actual in (None, "desconocido") else str(actual))
    valores = [o["valor"] for o in info["opciones"]]
    textos = {o["valor"]: "No lo sé" if o["valor"] == "desconocido" else mayus_inicial(o["texto"])
              for o in info["opciones"]}
    return st.segmented_control(etiqueta, valores, help=info["pregunta"], format_func=textos.get,
                                default=actual if actual in valores else None)


def ingreso_libre(catalogo: dict) -> None:
    st.caption("Recorra las pestañas y marque lo que sepa. Lo que deje sin marcar o con «No lo sé» "
               "cuenta como desconocido.")
    actuales = dict(st.session_state.obs)
    grupos: dict[str, list[dict]] = {}
    for info in catalogo.values():
        grupos.setdefault(info["grupo"], []).append(info)

    # Una pestaña por grupo: se ve un solo grupo a la vez (8 preguntas como
    # máximo) en lugar de las 31 seguidas. Cada pestaña indica cuántas de sus
    # preguntas ya tienen respuesta guardada.
    etiquetas = []
    for grupo, variables in grupos.items():
        respondidas = sum(1 for info in variables
                          if actuales.get(info["variable"], "desconocido") != "desconocido")
        etiquetas.append(f"{GRUPO_CORTO.get(grupo, grupo)} {respondidas}/{len(variables)}")

    nuevos: dict[str, object] = {}
    with st.form("form_libre", border=False):
        for pestana, variables in zip(st.tabs(etiquetas), grupos.values()):
            with pestana:
                st.caption(variables[0]["nombre_grupo"])
                for info in variables:
                    nuevos[info["variable"]] = campo_libre(info, actuales.get(info["variable"]))
        aplicar = st.form_submit_button("Diagnosticar con estos datos", type="primary", width="stretch")
    if aplicar:
        st.session_state.obs = [(v, x) for v, x in nuevos.items()
                                if limpiar_valor(x) not in (None, "desconocido")]
        st.rerun()


# ---------------------------------------------------------------------------
# Presentación de resultados
# ---------------------------------------------------------------------------
def resumen_estado(respuesta: dict) -> None:
    etiqueta, tono = ESTADO.get(respuesta["estado"], (respuesta["estado"], "aviso"))
    tipos = [r["tipo"] for r in respuesta["resultados"]]
    cuentas = [("alertas", tipos.count("alerta")),
               ("verificaciones básicas", tipos.count("basica")),
               ("diagnósticos", tipos.count("diagnostico")),
               ("hipótesis descartadas", len(respuesta["descartadas"]))]
    cuentas_html = "".join(f"<span><b>{n}</b>{e(t)}</span>" for t, n in cuentas)
    bloque(f'<div class="mx-estado {tono}"><div class="mx-estado-et">{e(etiqueta)}</div>'
           f'<p class="mx-p">{e(respuesta["mensaje"])}</p>'
           f'<p class="mx-cuentas">{cuentas_html}</p></div>')


def tarjeta_conclusion(r: dict) -> None:
    prioridad = f'<span class="mx-prio p{r["prioridad"]}">Prioridad {r["prioridad"]} · {e(r["etiqueta_prioridad"])}</span>'
    if r["tipo"] == "alerta":
        recomendaciones = "".join(f"<li>{e(x)}</li>" for x in r["recomendaciones"])
        bloque(f'<article class="mx-card mx-alerta">'
               f'<div class="mx-fila"><span class="mx-cod">{e(r["codigo"].upper())}</span>'
               f'<span class="mx-meta">Alerta de seguridad · {e(r["subsistema"])}</span>{prioridad}</div>'
               f'<p class="mx-titulo">{e(r["nombre"])}</p>'
               f'<p class="mx-p"><b>{e(r["accion_prioridad"])}</b></p>'
               f'<ul class="mx-lista">{recomendaciones}</ul></article>')
        return

    bloque(f'<article class="mx-card">'
           f'<div class="mx-fila"><span class="mx-cod">{e(r["codigo"].upper())}</span>'
           f'<span class="mx-meta">{e(TITULO_TIPO.get(r["tipo"], r["tipo"]))} · {e(r["subsistema"])}</span>{prioridad}</div>'
           f'<p class="mx-titulo">{e(r["nombre"])}</p>'
           f'<div class="mx-resp">{indicador_respaldo(r["respaldo"])}'
           f'<span>Respaldo <b>{e(r["respaldo"])}</b> · {e(r["coincidencia"])}</span></div>'
           f'<p class="mx-p mx-muted">{e(r["accion_prioridad"])}</p></article>')
    with st.expander(f"Evidencias y recomendaciones de {r['codigo'].upper()}"):
        partes = ['<p class="mx-eyebrow">Evidencias a favor</p>',
                  '<ul class="mx-lista">' + "".join(f"<li>{e(x)}</li>" for x in r["evidencias"]) + "</ul>"]
        if r["evidencias_en_contra"]:
            partes += ['<p class="mx-eyebrow">Evidencias en contra</p>',
                       '<ul class="mx-lista">' + "".join(f"<li>{e(x)}</li>" for x in r["evidencias_en_contra"]) + "</ul>"]
        partes += [f'<p class="mx-p"><b>Respaldo.</b> {e(r["justificacion_respaldo"])}</p>',
                   '<p class="mx-eyebrow">Verificaciones y acciones seguras</p>',
                   '<ul class="mx-lista">' + "".join(f"<li>{e(x)}</li>" for x in r["recomendaciones"]) + "</ul>",
                   "".join(f'<p class="mx-p mx-muted">{e(a)}</p>' for a in r["avisos"])]
        bloque('<div style="display:grid;gap:.5rem">' + "".join(partes) + "</div>")


def efectos_html(efectos: list[str]) -> str:
    return '<ul class="mx-efectos">' + "".join(f"<li>{resaltar_valores(x)}</li>" for x in efectos) + "</ul>"


def panel_que_falta(falta: dict, catalogo: dict) -> None:
    titulo_seccion("¿Qué falta?", ancla="que-falta")
    situacion = falta["situacion"]
    evaluadas = "".join(
        f'<span class="mx-hip"><code>{e(h["codigo"].upper())}</code>{indicador_respaldo(h["respaldo"])}'
        f'{e(h["respaldo"].replace("_", " "))}</span>' for h in falta["evaluadas"])
    bloque(f'<div style="display:grid;gap:.6rem">'
           f'<div class="mx-fila"><span class="mx-sit {e(situacion)}">'
           f'{e(TITULO_SITUACION.get(situacion, situacion))}</span></div>'
           f'<p class="mx-p">{e(falta["mensaje"])}</p>'
           + (f'<div class="mx-fila">{evaluadas}</div>' if evaluadas else "") + "</div>")

    sugerencias = falta["sugerencias"]
    if not sugerencias:
        return
    principal, otras = sugerencias[0], sugerencias[1:]
    with st.container(border=True):
        peso = '<i></i>' * principal["peso"]
        bloque(f'<div style="display:grid;gap:.5rem">'
               f'<p class="mx-eyebrow">Dato sugerido · {e(principal["tipo"].replace("_", " "))}</p>'
               f'<p class="mx-titulo">{e(principal["etiqueta"])}</p>'
               f'<div class="mx-fila mx-muted" style="font-size:.85rem">'
               f'<span class="mx-peso" aria-hidden="true">{peso}</span>'
               f'Peso {principal["peso"]} · prioridad afectada {principal["prioridad"]}</div>'
               f'{efectos_html(principal["efectos"])}</div>')
        if principal["variable"] in catalogo:
            formulario_respuesta(catalogo[principal["variable"]], "falta")
    if otras:
        filas = "".join(
            f'<li><div class="mx-fila"><b>{e(s["etiqueta"])}</b>'
            f'<span class="mx-muted" style="font-size:.8rem">peso {s["peso"]} · {e(s["tipo"].replace("_", " "))}</span></div>'
            f'{efectos_html(s["efectos"])}</li>' for s in otras)
        bloque(f'<p class="mx-eyebrow">También ayudarían</p><ul class="mx-otras">{filas}</ul>')


def traza_html(pasos: list[dict]) -> str:
    filas = []
    for p in pasos:
        coincidencia = re.match(r"^([a-z_]+/\d+)(.*)$", p["texto"], re.S)
        cuerpo = (f"<code>{e(coincidencia.group(1))}</code>{e(coincidencia.group(2))}"
                  if coincidencia else e(p["texto"]))
        filas.append(f'<li class="d{min(p["nivel"], 3)}"><span class="mx-regla">{e(p["regla"])}</span>'
                     f'<span>{cuerpo}</span></li>')
    return f'<ol class="mx-traza">{"".join(filas)}</ol>'


def panel_auditoria(explicacion: dict, respuesta: dict) -> None:
    titulo_seccion("¿Por qué? Auditoría del razonamiento")
    reglas, hechos, alternativas = st.tabs(
        ["Reglas disparadas", "Hechos comprobados", "Hipótesis descartadas"])

    with reglas:
        bloque('<p class="mx-eyebrow">Razonamiento común</p>' + traza_html(explicacion["general"]))
        for c in explicacion["conclusiones"]:
            with st.expander(f"{c['codigo'].upper()} · {c['nombre']}"):
                bloque(traza_html(c["pasos"]))
        if not explicacion["conclusiones"]:
            st.caption("No hay conclusiones que explicar.")

    with hechos:
        if explicacion["hechos"]:
            filas = "".join(
                f'<tr><td>{e(h["hecho"])}</td><td>'
                + ("".join(f'<span class="mx-chip">{e(u)}</span>' for u in h["usos"])
                   or '<span class="mx-muted">Sin reglas asociadas</span>')
                + "</td></tr>" for h in explicacion["hechos"])
            bloque('<div class="mx-tabla-wrap"><table class="mx-tabla"><thead><tr>'
                   '<th>Hecho del caso</th><th>Unificó con</th></tr></thead>'
                   f'<tbody>{filas}</tbody></table></div>')
        else:
            st.caption("Todavía no hay hechos comprobados.")
        if respuesta["invalidas"]:
            st.warning("Datos rechazados por la validación de Prolog: "
                       + ", ".join(respuesta["invalidas"]))

    with alternativas:
        if not explicacion["alternativas"]:
            st.caption("Ninguna hipótesis alternativa fue descartada o excluida.")
        else:
            filas = "".join(
                f'<div class="mx-alt"><div class="mx-fila"><span class="mx-cod">{e(a["codigo"].upper())}</span>'
                f'<span class="mx-alt-nombre">{e(a["nombre"])}</span>'
                f'<span class="mx-tag {e(a["tipo"])}">{e(TITULO_ALTERNATIVA.get(a["tipo"], a["tipo"]))}</span></div>'
                + (f'<p class="mx-p mx-muted" style="font-size:.85rem">Síntomas compartidos: '
                   f'{e("; ".join(a["compartidos"]))}</p>' if a["compartidos"] else "")
                + f'<p class="mx-p">{e(a["motivo"])}</p></div>' for a in explicacion["alternativas"])
            bloque(f'<div class="mx-alts">{filas}</div>')


def estado_vacio() -> None:
    bloque('<div class="mx-vacio"><p class="mx-titulo">El dictamen aparecerá aquí</p>'
           '<p class="mx-p mx-muted">Con la primera respuesta, Prolog calcula y muestra:</p>'
           '<ol><li>alertas de seguridad y diagnósticos con su respaldo y prioridad;</li>'
           '<li>el dato que más ayuda a confirmar o desempatar;</li>'
           '<li>la traza de reglas que explica cada conclusión.</li></ol></div>')
    st.button("Probar con un caso de ejemplo", on_click=cargar_ejemplo,
              help="Carga una moto de 150 cc con giro lento y luces débiles.")


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------
def cabecera() -> None:
    bloque('<header class="mx-cab"><div class="mx-marca">Moto<span>Expert</span></div>'
           '<p class="mx-sub">Responda unas preguntas sobre su moto y encuentre la causa '
           'probable de la falla. Cada resultado le explica cómo se llegó a él.</p>'
           '<ul class="mx-spec" aria-label="Alcance"><li>100–250 cc</li><li>4 tiempos</li>'
           '<li>Carburador</li><li>12 V</li></ul></header>')


def barra_lateral(catalogo: dict) -> None:
    with st.sidebar:
        obs = observaciones()
        bloque(f'<p class="mx-eyebrow">Datos del caso · {len(obs)}</p>')
        if obs:
            filas = "".join(f"<dt>{e(et)}</dt><dd>{e(val)}</dd>"
                            for et, val in (texto_valor(catalogo, v, x) for v, x in obs))
            bloque(f'<dl class="mx-datos">{filas}</dl>')
        else:
            st.caption("Aún no hay respuestas.")
        col1, col2 = st.columns(2)
        col1.button("Deshacer", on_click=deshacer, disabled=not obs)
        col2.button("Nueva consulta", on_click=reiniciar, disabled=not obs)
        st.divider()
        st.caption("Ingrese datos de pruebas técnicas (voltaje, chispa, compresión) solo si ya "
                   "las realizó personal capacitado.")
        st.caption("Diagnóstico preliminar: no sustituye la evaluación de un profesional.")


def main() -> None:
    aplicar_estilos()
    cabecera()

    try:
        motor = obtener_motor()
        catalogo = {info["variable"]: info for info in obtener_catalogo()}
    except ErrorMotor as exc:
        st.error(f"No fue posible iniciar el motor de Prolog: {exc}")
        st.info("Verifique que SWI-Prolog esté instalado y en el PATH, y que PySwip esté "
                "instalado (pip install pyswip).")
        st.stop()

    barra_lateral(catalogo)
    try:
        # Prolog se consulta antes de dibujar, para que el aviso de empate
        # pueda aparecer junto a la pregunta que el usuario está mirando.
        obs = observaciones()
        if obs:
            respuesta = motor.consultar(obs)
            explicacion = motor.explicar(obs)
            falta = motor.que_falta(obs)

        captura, dictamen = st.columns([5, 7], gap="large")
        with captura:
            titulo_seccion("Captura")
            if obs:
                aviso_empate(falta)
            guiada, libre = st.tabs(["Entrevista guiada", "Ingreso libre"])
            with guiada:
                entrevista_guiada(motor, catalogo)
            with libre:
                ingreso_libre(catalogo)

        with dictamen:
            titulo_seccion("Dictamen")
            if not obs:
                estado_vacio()
                return
            resumen_estado(respuesta)
            for r in respuesta["resultados"]:
                tarjeta_conclusion(r)
            panel_que_falta(falta, catalogo)

        panel_auditoria(explicacion, respuesta)
    except ErrorMotor as exc:
        st.error(f"Error al consultar Prolog: {exc}")


main()
