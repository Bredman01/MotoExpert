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

from clasificador import convertir_mediciones
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
    "ambiguo": "Causas sin distinguir",
}
TITULO_ALTERNATIVA = {
    "descartada": "Descartada por verificación",
    "excluida": "Excluida por condición (\\+)",
    "sin_evidencia_critica": "Falta evidencia crítica",
}
TITULO_TIPO = {"basica": "Verificación básica", "diagnostico": "Diagnóstico preliminar"}
NOTA_TIPO = {"revision": "requiere revisarla", "prueba_tecnica": "solo si la hizo un técnico"}
TITULO_RAMA = {"electrica": "Eléctrica", "motor": "Motor"}
TITULO_TIPO_PREGUNTA = {"sintoma": "Síntoma", "dato": "Dato", "revision": "Revisión",
                        "prueba_tecnica": "Prueba técnica"}
TITULO_TIPO_REGLA = {"evidencia": "Lo apoya", "verificacion": "Lo confirma",
                     "contraevidencia": "Lo debilita", "descarte": "Lo descarta"}
NIVEL_PRIORIDAD = {1: "Baja", 2: "Media", 3: "Alta", 4: "Crítica"}
EJEMPLO_DESCRIPCION = ("Mi moto de 150 cc no arranca: el motor gira lento y las luces están "
                       "débiles. No huele a gasolina.")
# Clave del rol Experto. Puede cambiarse con la variable de entorno MOTOEXPERT_CLAVE.
CLAVE_EXPERTO = os.environ.get("MOTOEXPERT_CLAVE", "experto")
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
    """Nueva consulta: borra los datos, la descripción y las mediciones."""
    st.session_state.obs = []
    st.session_state.pop("interpretacion", None)
    st.session_state.pop("conversion", None)
    # Los formularios de descripción e ingreso libre usan esta versión en su
    # clave: al cambiarla, Streamlit los dibuja de nuevo vacíos.
    st.session_state.version_consulta = st.session_state.get("version_consulta", 0) + 1


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
    """
    Aviso visible cuando la evidencia no alcanza para elegir: empate (mismo
    respaldo Medio o Bajo) o causas sin distinguir (Alto por la misma prueba).
    """
    situacion = falta["situacion"]
    if situacion not in ("empate", "ambiguo"):
        st.session_state.ultima_situacion = situacion
        return
    nombres = " y ".join(f"{h['codigo'].upper()} ({h['nombre']})" for h in falta["evaluadas"])
    sugerido = falta["sugerencias"][0]["etiqueta"] if falta["sugerencias"] else None
    titulo = TITULO_SITUACION[situacion]
    if st.session_state.get("ultima_situacion") != situacion:
        st.toast(f"{titulo}: responda el dato sugerido en «¿Qué falta?».", icon="⚖️")
    st.session_state.ultima_situacion = situacion
    motivo = ("tienen el mismo respaldo." if situacion == "empate" else
              "quedaron con respaldo Alto por la misma prueba, así que todavía no se sabe cuál es.")
    accion = (f'Para distinguirlos, responda el dato sugerido: <b>{e(sugerido)}</b>.'
              if sugerido else "No quedan datos que los distingan; se recomienda revisión profesional.")
    bloque(f'<div class="mx-aviso" role="status"><p class="mx-aviso-et">{e(titulo)}</p>'
           f'<p class="mx-p">{e(nombres)} {motivo} {accion}</p>'
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
    with st.form(f"form_libre_{st.session_state.get('version_consulta', 0)}", border=False):
        *pestanas, mediciones = st.tabs(etiquetas + ["Mediciones"])
        for pestana, variables in zip(pestanas, grupos.values()):
            with pestana:
                st.caption(variables[0]["nombre_grupo"])
                for info in variables:
                    nuevos[info["variable"]] = campo_libre(info, actuales.get(info["variable"]))
        with mediciones:
            st.caption("Si tiene la medición exacta, escríbala: un clasificador la convierte en el "
                       "dato que usa el sistema y reemplaza lo marcado en la pregunta equivalente.")
            temperatura = st.text_input("Temperatura del aceite del motor (°C)",
                                        placeholder="Ej.: 135 · reemplaza «Sobrecalentamiento»")
            dias = st.text_input("Días sin usar la moto", placeholder="Ej.: 45 · reemplaza «Tiempo sin uso»")
        aplicar = st.form_submit_button("Diagnosticar con estos datos", type="primary", width="stretch")
    if aplicar:
        obs = {v: x for v, x in nuevos.items() if limpiar_valor(x) not in (None, "desconocido")}
        medidas = {clave: valor if isinstance(valor, (int, float)) else None
                   for clave, valor in (("temperatura", limpiar_valor(temperatura)),
                                        ("dias_sin_uso", limpiar_valor(dias)))}
        convertidas, detalle = convertir_mediciones(medidas)
        obs.update(convertidas)
        st.session_state.obs = list(obs.items())
        st.session_state.conversion = detalle
        st.rerun()
    if st.session_state.get("conversion"):
        mostrar_conversion(st.session_state.conversion)


def mostrar_conversion(detalle: list[dict]) -> None:
    """Cómo el clasificador convirtió cada medición en un dato discreto."""
    filas = []
    for d in detalle:
        if "error" in d:
            filas.append(f'<li class="mx-entendido invalido"><span class="mx-frase">{e(d["nombre"])}: '
                         f'{d["valor"]:g} {e(d["unidad"])}</span><span class="mx-dato">'
                         f'<em>No se usa: {e(d["error"])}</em></span></li>')
            continue
        umbrales = " y ".join(f"{u:g}" for u in d["umbrales"])
        filas.append(f'<li class="mx-entendido"><span class="mx-frase">{e(d["nombre"])}: '
                     f'{d["valor"]:g} {e(d["unidad"])}</span><span class="mx-dato">'
                     f'{e(d["variable"])} = {e(d["etiqueta"])} <em>({e(d["metodo"])}; umbral '
                     f'{umbrales} {e(d["unidad"])})</em></span></li>')
    bloque('<p class="mx-eyebrow">Mediciones convertidas</p>'
           f'<ul class="mx-entendidos">{"".join(filas)}</ul>')


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
           '<p class="mx-sub">Cuéntele con sus palabras qué le pasa a su moto, o responda unas '
           'preguntas, y encuentre la causa probable de la falla. Cada resultado le explica '
           'cómo se llegó a él.</p>'
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
        st.divider()
        acceso_experto()


# ---------------------------------------------------------------------------
# Entregable 3: descripción en lenguaje natural (DCG en Prolog)
# ---------------------------------------------------------------------------
def descripcion_libre(motor: MotorMotoExpert) -> None:
    st.caption("Escriba con sus palabras qué le pasa a la moto. Prolog analiza el texto con una "
               "gramática (DCG) y extrae los datos para el diagnóstico.")
    with st.form(f"form_descripcion_{st.session_state.get('version_consulta', 0)}", border=False):
        texto = st.text_area("Descripción de la falla", height=130, label_visibility="collapsed",
                             placeholder=f"Por ejemplo: {EJEMPLO_DESCRIPCION}")
        enviar = st.form_submit_button("Interpretar descripción", type="primary", width="stretch")
    if enviar:
        if not texto.strip():
            st.warning("Escriba una descripción de la falla.")
            return
        resultado = motor.interpretar(texto)
        # Cada dato entendido reemplaza el valor anterior de la misma pregunta.
        for variable, valor in resultado["observaciones"]:
            registrar(variable, valor)
        st.session_state.interpretacion = resultado
        st.rerun()
    if st.session_state.get("interpretacion"):
        mostrar_interpretacion(st.session_state.interpretacion)


def mostrar_interpretacion(resultado: dict) -> None:
    """Qué parte del texto se entendió y qué dato salió de cada una."""
    filas = []
    for r in resultado["reconocidos"]:
        nota = {"repetido": "ya mencionado antes en el texto; vale el primero",
                "invalido": "valor fuera de rango; no se usa"}.get(r["estado"], "")
        filas.append(f'<li class="mx-entendido {e(r["estado"])}"><span class="mx-frase">'
                     f'«{e(r["frase"])}»</span><span class="mx-dato">{e(mayus_inicial(r["texto"]))}'
                     + (f' <em>({e(nota)})</em>' if nota else "") + "</span></li>")
    if filas:
        bloque('<p class="mx-eyebrow">Lo que entendí</p>'
               f'<ul class="mx-entendidos">{"".join(filas)}</ul>')
    else:
        st.warning("No encontré síntomas en la descripción. Pruebe con frases como «el motor gira "
                   "lento», «las luces están débiles» o «huele a gasolina».")
    if resultado["no_reconocidas"]:
        st.caption("Palabras que no reconocí: " + ", ".join(resultado["no_reconocidas"]))


# ---------------------------------------------------------------------------
# Entregable 3: modo experto (assertz/1 y persistencia en Prolog)
# ---------------------------------------------------------------------------
def acceso_experto() -> None:
    """Acceso al rol Experto. La clave es un control de la interfaz, no del dominio."""
    bloque('<p class="mx-eyebrow">Modo experto</p>')
    if st.session_state.get("experto"):
        st.toggle("Ver panel del experto", key="vista_experto")
        st.button("Salir del modo experto", on_click=salir_experto)
        return
    with st.form("form_clave", border=False):
        clave = st.text_input("Clave de experto", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        if clave == CLAVE_EXPERTO:
            st.session_state.experto = True
            st.session_state.vista_experto = True
            st.rerun()
        st.error("Clave incorrecta.")


def salir_experto() -> None:
    st.session_state.experto = False
    st.session_state.vista_experto = False


def panel_experto(motor: MotorMotoExpert) -> None:
    titulo_seccion("Panel del experto")
    st.caption("Enseñe al sistema un diagnóstico, una pregunta o una regla nueva. Prolog los valida, "
               "los carga en memoria con assertz/1 y los guarda en conocimiento_aprendido.pl, así que "
               "el aprendizaje se conserva al reiniciar. Desde ese momento participan en el "
               "diagnóstico, las preguntas y las explicaciones como cualquier otro conocimiento.")
    mensaje = st.session_state.pop("mensaje_experto", None)
    if mensaje:
        tipo, texto_mensaje = mensaje if isinstance(mensaje, tuple) else ("ok", mensaje)
        (st.success if tipo == "ok" else st.error)(texto_mensaje)
    formularios, aprendidos = st.columns([7, 5], gap="large")
    with formularios:
        editando = st.session_state.get("editando")
        if editando and editando[0] == "diagnostico":
            formulario_diagnostico(motor, codigo=editando[1])
        elif editando and editando[0] == "pregunta":
            formulario_pregunta(motor, variable=editando[1])
        else:
            diagnostico, pregunta, regla = st.tabs(["Nuevo diagnóstico", "Nueva pregunta", "Nueva regla"])
            with diagnostico:
                formulario_diagnostico(motor)
            with pregunta:
                formulario_pregunta(motor)
            with regla:
                formulario_regla(motor)
    with aprendidos:
        lista_aprendidos(motor)


def empezar_edicion(tipo: str, clave: str) -> None:
    st.session_state.editando = (tipo, clave)


def terminar_edicion() -> None:
    st.session_state.pop("editando", None)


def mostrar_errores(titulo: str, errores: list[str]) -> None:
    """
    Errores de validación de Prolog. El título dice expresamente que no se
    guardó nada, para que el usuario no crea que sus cambios quedaron hechos.
    """
    st.error(f"**{titulo}** Corrija lo siguiente y vuelva a guardar:\n\n" +
             "\n".join(f"- {err}" for err in errores))


def botones_formulario(editando: bool, texto_crear: str) -> tuple[bool, bool]:
    """Guardar (y Cancelar al editar). Devuelve (guardar, cancelar)."""
    if not editando:
        return st.form_submit_button(texto_crear, type="primary", width="stretch"), False
    with st.container(horizontal=True, gap="small"):
        guardar = st.form_submit_button("Guardar cambios", type="primary")
        cancelar = st.form_submit_button("Cancelar")
    return guardar, cancelar


def formulario_pregunta(motor: MotorMotoExpert, variable: str | None = None) -> None:
    """Pregunta nueva, o edición de una aprendida (conserva su identificador)."""
    datos = motor.datos_pregunta(variable) if variable else None
    if variable and datos is None:
        terminar_edicion()
        st.rerun()
    datos = datos or {}
    grupos = {g["grupo"]: g["nombre"] for g in motor.grupos()}
    # Al crear, la clave cambia tras guardar (el formulario se vacía). Al
    # editar es fija: si hay errores, el formulario conserva lo escrito.
    version = st.session_state.setdefault("version_formulario_pregunta", 0)
    clave = f"form_editar_p_{variable}" if variable else f"form_pregunta_{version}"
    with st.form(clave):
        if variable:
            bloque(f'<p class="mx-eyebrow">Editar pregunta · {e(datos["etiqueta"])}</p>')
        st.caption("Sirve para agregar la prueba o el síntoma que distingue un diagnóstico de otro.")
        etiqueta = st.text_input("Nombre corto", value=datos.get("etiqueta", ""),
                                 placeholder="Ej.: Voltaje al acelerar")
        texto = st.text_input("Pregunta para el usuario", value=datos.get("texto", ""),
                              placeholder="Ej.: Con el motor encendido, ¿sube el voltaje de la batería al acelerar?")
        lista_grupos = list(grupos)
        grupo = st.selectbox("Grupo", lista_grupos, format_func=grupos.get,
                             index=lista_grupos.index(datos["grupo"]) if datos.get("grupo") in grupos else 0)
        tipo = st.segmented_control("Tipo", list(TITULO_TIPO_PREGUNTA), default=datos.get("tipo", "sintoma"),
                                    format_func=TITULO_TIPO_PREGUNTA.get,
                                    help="Define el orden en que se pregunta: primero lo que el usuario "
                                         "observa, al final las pruebas técnicas.")
        opciones = st.text_input("Respuestas posibles (separadas por comas)",
                                 value=", ".join(mayus_inicial(o) for o in datos.get("opciones", ["Sí", "No"])),
                                 help="«No lo sé» se agrega solo.")
        frases = st.text_area("Frases que la describen (una por línea: respuesta: frase)",
                              value="\n".join(f"{mayus_inicial(o)}: {f}" for o, f in datos.get("frases", [])),
                              placeholder="No: el voltaje no sube al acelerar\nSí: el voltaje sube al acelerar",
                              help="Con estas frases la pestaña «Descripción» reconoce la respuesta en "
                                   "el texto del usuario.")
        guardar, cancelar = botones_formulario(bool(variable), "Agregar la pregunta")
    if cancelar:
        terminar_edicion()
        st.rerun()
    if guardar:
        pares = []
        for linea in frases.splitlines():
            respuesta, _, frase = linea.partition(":")
            if linea.strip():
                pares.append((respuesta.strip(), frase.strip()))
        pregunta = {"etiqueta": etiqueta, "texto": texto, "grupo": grupo or "", "tipo": tipo or "",
                    "opciones": [o.strip() for o in opciones.split(",") if o.strip()], "frases": pares}
        if variable:
            resultado = motor.editar_pregunta(variable, pregunta)
            if resultado["estado"] == "ok":
                obtener_catalogo.clear()
                terminar_edicion()
                st.session_state.mensaje_experto = f"Se guardaron los cambios de la pregunta «{etiqueta.strip()}»."
                st.rerun()
            mostrar_errores("No se guardaron los cambios: la pregunta sigue como estaba.", resultado["errores"])
            return
        resultado = motor.aprender_pregunta(pregunta)
        if resultado["estado"] == "ok":
            obtener_catalogo.clear()      # el formulario de ingreso libre la debe mostrar
            st.session_state.version_formulario_pregunta = version + 1
            st.session_state.mensaje_experto = (
                f"Se agregó la pregunta «{etiqueta.strip()}». Ya aparece en el ingreso libre y puede "
                "usarse en diagnósticos y reglas.")
            st.rerun()
        mostrar_errores("No se guardó la pregunta.", resultado["errores"])


def formulario_regla(motor: MotorMotoExpert) -> None:
    """Regla nueva sobre un diagnóstico existente, de la base o aprendido."""
    condiciones = motor.condiciones_posibles()
    pares = [(c["variable"], c["valor"]) for c in condiciones]
    textos = {(c["variable"], c["valor"]): mayus_inicial(c["texto"]) for c in condiciones}
    diagnosticos = {d["codigo"]: d["nombre"] for d in motor.catalogo_diagnosticos()}
    version = st.session_state.setdefault("version_formulario_regla", 0)
    with st.form(f"form_regla_{version}"):
        st.caption("Si el usuario responde… → qué le pasa al diagnóstico. Sirve también para los "
                   "diagnósticos de la base original.")
        condicion = st.selectbox("Si la respuesta es", pares, index=None, format_func=textos.get,
                                 placeholder="Elija una pregunta y su respuesta")
        tipo = st.segmented_control("Entonces", list(TITULO_TIPO_REGLA), default="verificacion",
                                    format_func=TITULO_TIPO_REGLA.get)
        codigo = st.selectbox("al diagnóstico", list(diagnosticos), index=None,
                              format_func=lambda c: f"{c.upper()} · {diagnosticos[c]}",
                              placeholder="Elija el diagnóstico")
        guardar = st.form_submit_button("Agregar la regla", type="primary", width="stretch")
    if guardar:
        variable, valor = condicion if condicion else ("", "")
        resultado = motor.aprender_regla(codigo or "", tipo or "", variable, valor)
        if resultado["estado"] == "ok":
            st.session_state.version_formulario_regla = version + 1
            st.session_state.mensaje_experto = (
                f"Se agregó la regla: si «{textos.get(condicion)}», "
                f"{TITULO_TIPO_REGLA[tipo].lower()} {codigo.upper()}.")
            st.rerun()
        mostrar_errores("No se guardó la regla.", resultado["errores"])


def formulario_diagnostico(motor: MotorMotoExpert, codigo: str | None = None) -> None:
    """Diagnóstico nuevo, o edición de uno aprendido (conserva su código)."""
    datos = motor.datos_diagnostico(codigo) if codigo else None
    if codigo and datos is None:
        terminar_edicion()
        st.rerun()
    datos = datos or {}
    condiciones = motor.condiciones_posibles()
    pares = [(c["variable"], c["valor"]) for c in condiciones]
    textos = {(c["variable"], c["valor"]): mayus_inicial(c["texto"]) for c in condiciones}
    diagnosticos = {d["codigo"]: d["nombre"] for d in motor.catalogo_diagnosticos() if d["codigo"] != codigo}

    def actuales(campo: str) -> list:
        return [c for c in datos.get(campo, []) if c in pares]

    # Al crear, la clave cambia tras guardar (el formulario se vacía). Al
    # editar es fija: si hay errores, el formulario conserva lo escrito.
    version = st.session_state.setdefault("version_formulario_experto", 0)
    clave = f"form_editar_d_{codigo}" if codigo else f"form_experto_{version}"
    with st.form(clave):
        titulo = f"Editar {codigo.upper()} · {datos['nombre']}" if codigo else "Nuevo diagnóstico"
        bloque(f'<p class="mx-eyebrow">{e(titulo)}</p>')
        nombre = st.text_input("Nombre del diagnóstico", value=datos.get("nombre", ""),
                               placeholder="Ej.: Regulador de voltaje dañado")
        subsistema = st.text_input("Subsistema afectado", value=datos.get("subsistema", ""),
                                   placeholder="Ej.: Sistema de carga")
        rama = st.segmented_control("Rama", ["electrica", "motor"], default=datos.get("rama", "electrica"),
                                    format_func=TITULO_RAMA.get,
                                    help="Eléctrica: el problema impide o debilita el giro del motor. "
                                         "Motor: el motor gira, pero no enciende o funciona mal.")
        prioridad = st.segmented_control("Prioridad base", [1, 2, 3, 4], default=datos.get("prioridad", 2),
                                         format_func=lambda p: f"{p} · {NIVEL_PRIORIDAD[p]}")
        evidencias = st.multiselect("Síntomas a favor (evidencias)", pares, format_func=textos.get,
                                    default=actuales("evidencias"), placeholder="Elija uno o más síntomas")
        verificaciones = st.multiselect("Pruebas que lo confirman (opcional)", pares, format_func=textos.get,
                                        default=actuales("verificaciones"),
                                        placeholder="Por ejemplo, una revisión o una prueba técnica")
        descartes = st.multiselect("Pruebas que lo descartan (opcional)", pares, format_func=textos.get,
                                   default=actuales("descartes"),
                                   placeholder="Resultados que demuestran que no es esta falla")
        competidoras = st.multiselect("Se confunde con (opcional)", list(diagnosticos),
                                      default=[c for c in datos.get("competidoras", []) if c in diagnosticos],
                                      format_func=lambda c: f"{c.upper()} · {diagnosticos[c]}",
                                      placeholder="Diagnósticos con síntomas parecidos")
        recomendaciones = st.text_area("Recomendaciones (una por línea)",
                                       value="\n".join(datos.get("recomendaciones", [])),
                                       placeholder="Ej.: Revisar el regulador de voltaje en un taller.")
        if codigo:
            st.caption("Las reglas agregadas aparte en «Nueva regla» se conservan y no aparecen aquí.")
        guardar, cancelar = botones_formulario(bool(codigo), "Agregar a la base de conocimiento")

    if cancelar:
        terminar_edicion()
        st.rerun()
    if guardar:
        ficha = {
            "nombre": nombre, "subsistema": subsistema, "rama": rama or "",
            "prioridad": prioridad or 0, "evidencias": evidencias,
            "verificaciones": verificaciones, "descartes": descartes,
            "competidoras": competidoras, "recomendaciones": recomendaciones.splitlines(),
        }
        if codigo:
            resultado = motor.editar_diagnostico(codigo, ficha)
            if resultado["estado"] == "ok":
                terminar_edicion()
                st.session_state.mensaje_experto = f"Se guardaron los cambios de {codigo.upper()} · {nombre.strip()}."
                st.rerun()
            mostrar_errores(f"No se guardaron los cambios: {codigo.upper()} sigue como estaba.",
                            resultado["errores"])
            return
        resultado = motor.aprender(ficha)
        if resultado["estado"] == "ok":
            st.session_state.version_formulario_experto = version + 1
            st.session_state.mensaje_experto = (
                f"Se agregó {resultado['codigo'].upper()} · {nombre.strip()} a la base de conocimiento "
                "y se guardó en conocimiento_aprendido.pl.")
            st.rerun()
        mostrar_errores("No se guardó el diagnóstico.", resultado["errores"])


def olvidar(motor: MotorMotoExpert, codigo: str) -> None:
    resultado = motor.olvidar(codigo)
    if resultado["estado"] == "ok":
        st.session_state.mensaje_experto = (f"Se eliminó {codigo.upper()} de la memoria y de "
                                            "conocimiento_aprendido.pl.")


def olvidar_pregunta(motor: MotorMotoExpert, variable: str, etiqueta: str) -> None:
    resultado = motor.olvidar_pregunta(variable)
    if resultado["estado"] == "ok":
        obtener_catalogo.clear()
        st.session_state.mensaje_experto = f"Se eliminó la pregunta «{etiqueta}»."
    else:
        st.session_state.mensaje_experto = ("error", " ".join(resultado["errores"]))


def olvidar_regla(motor: MotorMotoExpert, identificador: str) -> None:
    if motor.olvidar_regla(identificador)["estado"] == "ok":
        st.session_state.mensaje_experto = f"Se eliminó la regla {identificador.upper()}."


def lista_aprendidos(motor: MotorMotoExpert) -> None:
    """Conocimiento aprendido en pestañas por categoría, en el orden de los formularios."""
    diagnosticos = motor.aprendidos()
    preguntas = motor.preguntas_aprendidas()
    reglas = motor.reglas_aprendidas()
    bloque('<p class="mx-eyebrow">Conocimiento aprendido</p>')
    pestana_d, pestana_p, pestana_r = st.tabs([
        f"Diagnósticos {len(diagnosticos)}", f"Preguntas {len(preguntas)}", f"Reglas {len(reglas)}"])
    with pestana_d:
        lista_diagnosticos(motor, diagnosticos)
    with pestana_p:
        lista_preguntas(motor, preguntas)
    with pestana_r:
        lista_reglas(motor, reglas)
    with st.expander("Ver conocimiento_aprendido.pl"):
        st.caption("Todo lo aprendido, tal como Prolog lo carga al iniciar.")
        try:
            with open(motor.ruta_aprendido(), encoding="utf-8") as archivo:
                st.code(archivo.read(), language="prolog")
        except OSError:
            st.caption("El archivo todavía no existe.")


def lista_diagnosticos(motor: MotorMotoExpert, aprendidos: list[dict]) -> None:
    if not aprendidos:
        st.caption("Todavía no se ha agregado ningún diagnóstico.")
    for a in aprendidos:
        evidencias = "".join(f'<span class="mx-chip">{e(t)}</span>' for t in a["evidencias"])
        bloque(f'<article class="mx-card"><div class="mx-fila"><span class="mx-cod">{e(a["codigo"].upper())}</span>'
               f'<span class="mx-meta">{e(TITULO_RAMA.get(a["rama"], a["rama"]))} · {e(a["subsistema"])}</span>'
               f'<span class="mx-prio p{a["prioridad"]}">Prioridad {a["prioridad"]} · '
               f'{e(NIVEL_PRIORIDAD.get(a["prioridad"], ""))}</span></div>'
               f'<p class="mx-titulo">{e(a["nombre"])}</p><div>{evidencias}</div>'
               f'<p class="mx-p mx-muted" style="font-size:.85rem">Aprendido el {e(a["fecha"])}</p></article>')
        with st.container(horizontal=True, gap="small"):
            st.button(f"Editar {a['codigo'].upper()}", key=f"editar_{a['codigo']}",
                      on_click=empezar_edicion, args=("diagnostico", a["codigo"]))
            with st.popover(f"Eliminar {a['codigo'].upper()}"):
                st.write(f"¿Eliminar {a['codigo'].upper()} · {a['nombre']}? Se retira de la memoria y del archivo.")
                st.button("Sí, eliminar", key=f"olvidar_{a['codigo']}", type="primary",
                          on_click=olvidar, args=(motor, a["codigo"]))


def lista_preguntas(motor: MotorMotoExpert, preguntas: list[dict]) -> None:
    if not preguntas:
        st.caption("Todavía no se ha agregado ninguna pregunta.")
    for p in preguntas:
        frases = "".join(f'<span class="mx-chip">{e(f)}</span>' for f in p["frases"])
        bloque(f'<article class="mx-card"><div class="mx-fila"><span class="mx-meta">'
               f'{e(p["grupo"])} · {e(TITULO_TIPO_PREGUNTA.get(p["tipo"], p["tipo"]))}</span></div>'
               f'<p class="mx-titulo">{e(p["etiqueta"])}</p><p class="mx-p">{e(p["pregunta"])}</p>'
               f'<p class="mx-p mx-muted" style="font-size:.85rem">Respuestas: '
               f'{e(", ".join(p["opciones"]))}</p><div>{frases}</div></article>')
        with st.container(horizontal=True, gap="small"):
            st.button(f"Editar «{p['etiqueta']}»", key=f"editar_p_{p['variable']}",
                      on_click=empezar_edicion, args=("pregunta", p["variable"]))
            with st.popover(f"Eliminar «{p['etiqueta']}»"):
                if p["en_uso"]:
                    st.write("Esta pregunta se usa en un diagnóstico o una regla. Elimínelos primero.")
                else:
                    st.write(f"¿Eliminar la pregunta «{p['etiqueta']}»?")
                    st.button("Sí, eliminar", key=f"olvidar_p_{p['variable']}", type="primary",
                              on_click=olvidar_pregunta, args=(motor, p["variable"], p["etiqueta"]))


def lista_reglas(motor: MotorMotoExpert, reglas: list[dict]) -> None:
    if not reglas:
        st.caption("Todavía no se ha agregado ninguna regla.")
        return
    filas ="".join(f'<li class="mx-entendido"><span class="mx-frase">{e(r["texto"])}</span>'
                    f'<span class="mx-dato">{e(r["codigo"].upper())} · {e(r["nombre"])}</span></li>'
                    for r in reglas)
    bloque(f'<ul class="mx-entendidos">{filas}</ul>')
    with st.popover("Eliminar una regla"):
        for r in reglas:
            st.button(f"{r['id'].upper()} · {r['texto']} → {r['codigo'].upper()}", key=f"olvidar_r_{r['id']}",
                      on_click=olvidar_regla, args=(motor, r["id"]))


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
        if st.session_state.get("experto") and st.session_state.get("vista_experto"):
            panel_experto(motor)
            return

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
            descripcion, guiada, libre = st.tabs(["Descripción", "Entrevista guiada", "Ingreso libre"])
            with descripcion:
                descripcion_libre(motor)
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
