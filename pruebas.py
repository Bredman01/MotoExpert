"""
pruebas.py - Casos de prueba por consola de MotoExpert.

Ejecuta casos de prueba contra el motor de Prolog. Para cada caso muestra:
objetivo, entrada, consulta enviada a Prolog, resultado esperado, resultado
obtenido y veredicto. La salida completa se guarda también en
evidencia_pruebas.txt como evidencia de ejecución.

Casos exigidos por la actividad:
  1. Caso Normal 1   - Diagnóstico único claro
  2. Caso Normal 2   - Múltiples diagnósticos / recolección (setof)
  3. Caso Exclusión  - Negación por fallo (\\+) y corte (!)
  4. Caso Borde 1    - Datos insuficientes / lista parcial
  5. Caso Borde 2    - Lista vacía / caso por defecto sin errores en Python
Casos adicionales:
  6. Caso Borde 2b   - Elementos inválidos y entrada que no es lista
  7. Respaldo Alto por descarte de las hipótesis competidoras
  8. Motocicleta fuera de alcance con alerta de seguridad
  9. Entrevista simulada guiada por siguiente_pregunta/2
Casos del entregable 2 (módulos de explicabilidad y recomendación):
 10. ¿Por qué? - Traza de reglas, hechos comprobados y competidoras descartadas
 11. ¿Por qué? - Alternativas excluidas (\\+) y sin evidencia crítica
 12. ¿Qué falta? - Empate entre hipótesis y dato de desempate
 13. ¿Qué falta? - Dictamen definitivo y caso fuera de alcance
 14. Validación en Prolog con ground/1 y átomos en minúscula
 15. Coherencia entre la entrevista guiada y el módulo «¿Qué falta?»

Uso:  python pruebas.py

Autor: Bredman Estiven Velez Cortez
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

from motor import ErrorMotor, MotorMotoExpert

RUTA_EVIDENCIA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "evidencia_pruebas.txt")
SALIDA: list[str] = []


def escribir(texto: str = "") -> None:
    print(texto)
    SALIDA.append(texto)


def resumen(respuesta: dict) -> str:
    """Resumen corto de los resultados: CODIGO(respaldo, prioridad)."""
    partes = [f"{r['codigo']}(respaldo={r['respaldo']}, prioridad={r['prioridad']})"
              for r in respuesta["resultados"]]
    return ", ".join(partes) if partes else "[] (sin conclusiones)"


def codigos(respuesta: dict) -> list[str]:
    return [r["codigo"] for r in respuesta["resultados"]]


def respaldo_de(respuesta: dict, codigo: str) -> str | None:
    for r in respuesta["resultados"]:
        if r["codigo"] == codigo:
            return r["respaldo"]
    return None


# ---------------------------------------------------------------------------
# Definición de los casos
# Cada caso tiene: nombre, objetivo, entrada, esperado (texto) y verificar(),
# que recibe la respuesta de consultar/6 y devuelve una lista de
# comprobaciones (descripción, se_cumple).
# ---------------------------------------------------------------------------
CASOS = [
    {
        "nombre": "Caso Normal 1 - Diagnóstico único claro",
        "objetivo": "Comprobar que una combinación coherente de síntomas y una "
                    "verificación específica produce un único diagnóstico con "
                    "respaldo Alto.",
        "entrada": [("cilindrada", 150), ("alimentacion", "carburador"),
                    ("tablero", "no"), ("luces", "apagadas"),
                    ("giro_arranque", "no_gira"), ("clic_arranque", "no"),
                    ("fusible", "fundido"), ("voltaje", 12.6)],
        "esperado": "Estado con_resultados. Una sola conclusión: d03 con respaldo "
                    "alto y prioridad 3. d01 descartada por voltaje normal.",
        "verificar": lambda r: [
            ("estado = con_resultados", r["estado"] == "con_resultados"),
            ("conclusiones = [d03]", codigos(r) == ["d03"]),
            ("respaldo d03 = alto", respaldo_de(r, "d03") == "alto"),
            ("d01 en descartadas", "d01" in [d["codigo"] for d in r["descartadas"]]),
        ],
    },
    {
        "nombre": "Caso Normal 2 - Múltiples diagnósticos / recolección",
        "objetivo": "Comprobar que diagnosticar_todos/2 reúne con setof/3 varias "
                    "conclusiones compatibles, sin duplicados (la entrada repite "
                    "una observación) y con las alertas primero.",
        "entrada": [("giro_arranque", "lento"), ("luces", "debil"),
                    ("luces", "debil"), ("voltaje", 11.6),
                    ("bornes", "sulfatados"), ("falla_intermitente", "si"),
                    ("olor_gasolina", "si")],
        "esperado": "Estado con_resultados. Conclusiones en orden: a01 (alerta, "
                    "prioridad 4), luego d01 y d02, ambas con respaldo alto. Sin "
                    "códigos repetidos.",
        "verificar": lambda r: [
            ("estado = con_resultados", r["estado"] == "con_resultados"),
            ("primera conclusión = a01", codigos(r)[:1] == ["a01"]),
            ("contiene d01 y d02", {"d01", "d02"} <= set(codigos(r))),
            ("sin duplicados", len(codigos(r)) == len(set(codigos(r)))),
            ("respaldo d01 = alto", respaldo_de(r, "d01") == "alto"),
            ("respaldo d02 = alto", respaldo_de(r, "d02") == "alto"),
        ],
    },
    {
        "nombre": "Caso de Exclusión - negación por fallo (\\+) y corte (!)",
        "objetivo": "Comprobar que d04 (relé o motor de arranque) NO se diagnostica "
                    "aunque haya clic y el motor no gire, porque la alimentación "
                    "eléctrica es débil. estado_alimentacion/2 usa cortes para "
                    "clasificar y hipotesis_activa/2 usa \\+ excluida(...).",
        "entrada": [("clic_arranque", "si"), ("giro_arranque", "no_gira"),
                    ("tablero", "si"), ("luces", "debil")],
        "esperado": "d04 ausente de los resultados y presente en descartadas con el "
                    "motivo de alimentación débil. d01 presente. "
                    "estado_alimentacion = debil (una sola solución por el corte). "
                    "Los diagnósticos de la rama motor quedan excluidos.",
        "consulta_extra": "estado_alimentacion([obs(clic_arranque,si), "
                          "obs(giro_arranque,no_gira), obs(tablero,si), "
                          "obs(luces,debil)], E)",
        "verificar": lambda r: [
            ("d04 no está en resultados", "d04" not in codigos(r)),
            ("d04 en descartadas", "d04" in [d["codigo"] for d in r["descartadas"]]),
            ("motivo menciona alimentación", any(
                d["codigo"] == "d04" and "alimentación" in d["motivo"]
                for d in r["descartadas"])),
            ("d01 está en resultados", "d01" in codigos(r)),
            ("sin diagnósticos de la rama motor",
             not set(codigos(r)) & {"d05", "d06", "d07", "d08", "d09", "d10"}),
        ],
    },
    {
        "nombre": "Caso Borde 1 - Datos insuficientes (lista parcial)",
        "objetivo": "Comprobar que con un solo síntoma el sistema no presenta una "
                    "conclusión definitiva: propone hipótesis con respaldo bajo e "
                    "informa que los datos son insuficientes.",
        "entrada": [("dificultad_arranque", "persistente")],
        "esperado": "Estado datos_insuficientes. Varias hipótesis (d05, d06, d07, "
                    "d10), todas con respaldo bajo y con aviso de evidencia "
                    "insuficiente.",
        "verificar": lambda r: [
            ("estado = datos_insuficientes", r["estado"] == "datos_insuficientes"),
            ("hay hipótesis", len(r["resultados"]) > 0),
            ("todas con respaldo bajo",
             all(x["respaldo"] == "bajo" for x in r["resultados"])),
            ("todas con aviso de evidencia insuficiente",
             all(any("insuficiente" in a for a in x["avisos"]) for x in r["resultados"])),
        ],
    },
    {
        "nombre": "Caso Borde 2 - Lista vacía (caso por defecto)",
        "objetivo": "Comprobar que una lista vacía no produce errores en Python ni "
                    "en Prolog: setof/3 falla sin soluciones y la rama por defecto "
                    "devuelve []; estado_consulta/3 usa su cláusula de sin datos.",
        "entrada": [],
        "esperado": "Estado sin_datos. Resultados = []. Ninguna excepción.",
        "verificar": lambda r: [
            ("estado = sin_datos", r["estado"] == "sin_datos"),
            ("resultados = []", r["resultados"] == []),
            ("mensaje no vacío", bool(r["mensaje"])),
        ],
    },
    {
        "nombre": "Caso Borde 2b - Elementos inválidos y entrada que no es lista",
        "objetivo": "Comprobar que Prolog filtra variables inexistentes, valores no "
                    "admitidos y números fuera de rango, y que una entrada que no "
                    "es lista cae en la cláusula por defecto de normalizar_caso/2.",
        "entrada": [("color", "rojo"), ("luces", "morado"), ("voltaje", 85)],
        "esperado": "Estado sin_datos, resultados [] y 3 observaciones inválidas. "
                    "Con la entrada 'no_lista': estado sin_datos, sin excepción.",
        "verificar": None,   # se define abajo (necesita una segunda consulta)
    },
    {
        "nombre": "Respaldo Alto por descarte de competidoras (d04)",
        "objetivo": "Comprobar la regla de respaldo Alto para diagnósticos sin "
                    "verificación propia: d04 alcanza Alto cuando d01, d02 y d03 "
                    "quedan descartadas por verificación.",
        "entrada": [("clic_arranque", "si"), ("giro_arranque", "no_gira"),
                    ("tablero", "si"), ("luces", "normal"), ("voltaje", 12.7),
                    ("bornes", "normal"), ("fusible", "bueno")],
        "esperado": "Una sola conclusión: d04 con respaldo alto. d01, d02 y d03 en "
                    "descartadas.",
        "verificar": lambda r: [
            ("conclusiones = [d04]", codigos(r) == ["d04"]),
            ("respaldo d04 = alto", respaldo_de(r, "d04") == "alto"),
            ("d01, d02 y d03 descartadas",
             {"d01", "d02", "d03"} <= {d["codigo"] for d in r["descartadas"]}),
        ],
    },
    {
        "nombre": "Fuera de alcance con alerta de seguridad",
        "objetivo": "Comprobar que una moto de 600 cc no recibe diagnósticos, pero "
                    "sí la alerta de seguridad por fuga de combustible.",
        "entrada": [("cilindrada", 600), ("fuga_combustible", "si"),
                    ("giro_arranque", "lento"), ("luces", "debil")],
        "esperado": "Estado fuera_de_alcance. Solo la alerta a01 con prioridad 4.",
        "verificar": lambda r: [
            ("estado = fuera_de_alcance", r["estado"] == "fuera_de_alcance"),
            ("conclusiones = [a01]", codigos(r) == ["a01"]),
            ("prioridad a01 = 4", r["resultados"][0]["prioridad"] == 4
             if r["resultados"] else False),
        ],
    },
]

# Respuestas que daría un usuario con la batería descargada (caso 9).
RESPUESTAS_SIMULADAS = {
    "cilindrada": 150, "alimentacion": "carburador",
    "fuga_combustible": "no", "olor_gasolina": "no", "sobrecalentamiento": "no",
    "interruptor_paro": "marcha", "nivel_combustible": "medio",
    "giro_arranque": "lento", "luces": "debil", "voltaje": 11.5,
    "bornes": "normal", "falla_intermitente": "no", "tablero": "si",
}


def ejecutar_caso(motor: MotorMotoExpert, numero: int, caso: dict) -> bool:
    escribir("=" * 78)
    escribir(f"CASO {numero}: {caso['nombre']}")
    escribir("=" * 78)
    escribir(f"Objetivo : {caso['objetivo']}")
    escribir(f"Entrada  : {caso['entrada']}")

    respuesta = motor.consultar(caso["entrada"])
    escribir(f"Consulta : {respuesta['consulta']}")
    escribir(f"Esperado : {caso['esperado']}")
    escribir(f"Obtenido : estado={respuesta['estado']}; resultados={resumen(respuesta)}")
    if respuesta["descartadas"]:
        escribir("           descartadas=" + ", ".join(
            d["codigo"] for d in respuesta["descartadas"]))
    if respuesta["invalidas"]:
        escribir(f"           inválidas={respuesta['invalidas']}")

    comprobaciones = caso["verificar"](respuesta)

    if "consulta_extra" in caso:
        soluciones = motor.consulta_libre(caso["consulta_extra"])
        escribir(f"Consulta adicional: {caso['consulta_extra']}")
        escribir(f"           soluciones={soluciones}")
        comprobaciones.append(("estado_alimentacion = debil, una sola solución",
                               soluciones == [{"E": "debil"}]))

    return informar(comprobaciones)


def ejecutar_caso_invalidos(motor: MotorMotoExpert, numero: int, caso: dict) -> bool:
    escribir("=" * 78)
    escribir(f"CASO {numero}: {caso['nombre']}")
    escribir("=" * 78)
    escribir(f"Objetivo : {caso['objetivo']}")
    escribir(f"Entrada  : {caso['entrada']}  y luego el término no_lista")
    r1 = motor.consultar(caso["entrada"])
    escribir(f"Consulta : {r1['consulta']}")
    r2 = motor.consultar("no_lista")
    escribir(f"Consulta : {r2['consulta']}")
    escribir(f"Esperado : {caso['esperado']}")
    escribir(f"Obtenido : (1) estado={r1['estado']}; resultados={resumen(r1)}; "
             f"inválidas={r1['invalidas']}")
    escribir(f"           (2) estado={r2['estado']}; resultados={resumen(r2)}; "
             f"inválidas={r2['invalidas']}")
    return informar([
        ("(1) estado = sin_datos", r1["estado"] == "sin_datos"),
        ("(1) resultados = []", r1["resultados"] == []),
        ("(1) 3 inválidas", len(r1["invalidas"]) == 3),
        ("(2) estado = sin_datos", r2["estado"] == "sin_datos"),
        ("(2) resultados = []", r2["resultados"] == []),
    ])


def ejecutar_entrevista(motor: MotorMotoExpert, numero: int) -> bool:
    escribir("=" * 78)
    escribir(f"CASO {numero}: Entrevista simulada guiada por siguiente_pregunta/2")
    escribir("=" * 78)
    escribir("Objetivo : Comprobar que Prolog elige las preguntas (primero admisión, "
             "seguridad y verificaciones básicas; luego solo las que diferencian "
             "hipótesis) y que la entrevista termina sola.")
    escribir("Entrada  : respuestas de un usuario con batería descargada; las "
             "preguntas no previstas se responden 'desconocido'.")
    escribir("Consulta : siguiente_pregunta(Lista, V) en cada paso; al final "
             "consultar/6.")
    escribir("Esperado : primera pregunta = cilindrada; no se pregunta por "
             "carburación; termina con 'fin' en menos de 25 preguntas; "
             "conclusión d01 con respaldo alto. Después del triaje, cada "
             "pregunta es la sugerencia principal de que_falta/5.")
    observaciones: list = []
    preguntas: list[str] = []
    while True:
        variable = motor.siguiente_pregunta(observaciones)
        if variable is None or len(preguntas) > 40:
            break
        preguntas.append(variable)
        observaciones.append((variable, RESPUESTAS_SIMULADAS.get(variable, "desconocido")))
    respuesta = motor.consultar(observaciones)
    escribir(f"Obtenido : {len(preguntas)} preguntas -> {', '.join(preguntas)}")
    escribir(f"           estado={respuesta['estado']}; resultados={resumen(respuesta)}")
    rama_motor = {"ralenti_inestable", "tirones", "vacios_aceleracion",
                  "filtro_aire", "bujia", "chispa", "compresion"}
    return informar([
        ("primera pregunta = cilindrada", preguntas[:1] == ["cilindrada"]),
        ("no pregunta por carburación ni encendido", not set(preguntas) & rama_motor),
        ("termina en menos de 25 preguntas", len(preguntas) < 25),
        ("conclusión d01 con respaldo alto", respaldo_de(respuesta, "d01") == "alto"),
    ])


# ---------------------------------------------------------------------------
# Casos del entregable 2: explicar_consulta/5 y que_falta/5
# Cada función recibe el motor y devuelve (líneas obtenidas, comprobaciones).
# ---------------------------------------------------------------------------
def reglas_de(explicacion: dict, codigo: str) -> list[str]:
    for c in explicacion["conclusiones"]:
        if c["codigo"] == codigo:
            return [p["regla"] for p in c["pasos"]]
    return []


def alternativa(explicacion: dict, codigo: str) -> dict | None:
    for a in explicacion["alternativas"]:
        if a["codigo"] == codigo:
            return a
    return None


def caso_traza(motor: MotorMotoExpert):
    entrada = CASOS[6]["entrada"]          # mismo caso que el 7: d04 Alto por descarte
    e = motor.explicar(entrada)
    pasos_d04 = next(c["pasos"] for c in e["conclusiones"] if c["codigo"] == "d04")
    hecho_clic = next((h for h in e["hechos"] if h["hecho"].startswith("Clic")), None)
    obtenido = [f"Consulta : {e['consulta']}",
                f"Obtenido : reglas d04 = {reglas_de(e, 'd04')}",
                f"           hecho clic = {hecho_clic}",
                "           alternativas = " + ", ".join(
                    f"{a['codigo']}({a['tipo']})" for a in e["alternativas"])]
    return obtenido, [
        ("traza general incluye normalizar_caso (R1.5) y estado_alimentacion (R2.1)",
         {"R1.5", "R2.1"} <= {p["regla"] for p in e["general"]}),
        ("la raíz de la traza de d04 es conclusion/2 (R3.6) en nivel 0",
         pasos_d04[0]["regla"] == "R3.6" and pasos_d04[0]["nivel"] == 0),
        ("d04 dispara hipotesis_activa, compatible, clasificar_respaldo y prioridad",
         {"R2.11", "R2.10", "R2.15", "R3.4"} <= set(reglas_de(e, "d04"))),
        ("el respaldo Alto de d04 se explica por competidoras descartadas (R2.9)",
         "R2.9" in reglas_de(e, "d04")),
        ("el hecho 'clic' unificó con requisito(d04, ...)",
         hecho_clic is not None and any(u.startswith("requisito(d04") for u in hecho_clic["usos"])),
        ("d01, d02 y d03 aparecen como alternativas descartadas",
         all((alternativa(e, c) or {}).get("tipo") == "descartada" for c in ("d01", "d02", "d03"))),
    ]


def caso_alternativas(motor: MotorMotoExpert):
    e1 = motor.explicar(CASOS[2]["entrada"])                 # caso 3: exclusión de d04
    e2 = motor.explicar([("clic_arranque", "si"), ("giro_arranque", "normal"),
                         ("tablero", "si")])
    a1, a2 = alternativa(e1, "d04"), alternativa(e2, "d04")
    obtenido = [f"Consulta : {e1['consulta']}",
                f"Obtenido : d04 -> {a1}",
                f"Consulta : {e2['consulta']}",
                f"Obtenido : d04 -> {a2}"]
    return obtenido, [
        ("(1) d04 es alternativa excluida", a1 is not None and a1["tipo"] == "excluida"),
        ("(1) el motivo cita la negación \\+ excluida/3", a1 is not None and "\\+" in a1["motivo"]),
        ("(1) informa los síntomas compartidos", a1 is not None and len(a1["compartidos"]) >= 2),
        ("(2) d04 queda sin evidencia crítica (no cumple su requisito)",
         a2 is not None and a2["tipo"] == "sin_evidencia_critica"),
    ]


def caso_empate(motor: MotorMotoExpert):
    f = motor.que_falta([("giro_arranque", "lento"), ("luces", "debil")])
    primera = f["sugerencias"][0] if f["sugerencias"] else {}
    obtenido = [f"Consulta : {f['consulta']}",
                f"Obtenido : situación={f['situacion']}; evaluadas="
                + ", ".join(f"{x['codigo']}({x['respaldo']})" for x in f["evaluadas"]),
                "           sugerencias=" + ", ".join(
                    f"{s['variable']}(peso={s['peso']})" for s in f["sugerencias"]),
                f"           efectos de la primera: {primera.get('efectos')}"]
    return obtenido, [
        ("situación = empate", f["situacion"] == "empate"),
        ("evalúa d01 y d02 con respaldo medio",
         {(x["codigo"], x["respaldo"]) for x in f["evaluadas"]} == {("d01", "medio"), ("d02", "medio")}),
        ("primera sugerencia = bornes (peso 3, menor costo que el voltaje)",
         primera.get("variable") == "bornes" and primera.get("peso") == 3),
        ("el voltaje también se sugiere", "voltaje" in [s["variable"] for s in f["sugerencias"]]),
        ("no sugiere datos ya ingresados",
         not {"giro_arranque", "luces"} & {s["variable"] for s in f["sugerencias"]}),
    ]


def caso_definitivo(motor: MotorMotoExpert):
    f1 = motor.que_falta(CASOS[0]["entrada"])                # caso 1: d03 Alto
    f2 = motor.que_falta(CASOS[7]["entrada"])                # caso 8: 600 cc
    obtenido = [f"Consulta : {f1['consulta']}",
                f"Obtenido : situación={f1['situacion']}; sugerencias={len(f1['sugerencias'])}",
                f"Consulta : {f2['consulta']}",
                f"Obtenido : situación={f2['situacion']}; sugerencias={len(f2['sugerencias'])}"]
    return obtenido, [
        ("(1) situación = definitivo", f1["situacion"] == "definitivo"),
        ("(1) mensaje no genérico", "Alto" in f1["mensaje"]),
        ("(2) situación = fuera_de_alcance", f2["situacion"] == "fuera_de_alcance"),
        ("(2) sin sugerencias", f2["sugerencias"] == []),
    ]


def caso_ground(motor: MotorMotoExpert):
    entrada = "[obs(voltaje, _), obs('Luces', 'Debil'), obs(_, si), obs(giro_arranque, lento)]"
    r = motor.consultar(entrada)
    e = motor.explicar(entrada)
    obtenido = [f"Consulta : {r['consulta']}",
                f"Obtenido : inválidas={r['invalidas']}; resultados={resumen(r)}",
                f"           hechos={[h['hecho'] for h in e['hechos']]}"]
    return obtenido, [
        ("2 observaciones con variables libres rechazadas por ground/1", len(r["invalidas"]) == 2),
        ("'Luces'/'Debil' se aceptan como luces = debil",
         any(h["hecho"].startswith("Intensidad de las luces") for h in e["hechos"])),
        ("d01 se infiere con los datos limpios", "d01" in codigos(r)),
    ]


def caso_coherencia(motor: MotorMotoExpert):
    base = [("cilindrada", 150), ("alimentacion", "carburador"), ("fuga_combustible", "no"),
            ("olor_gasolina", "no"), ("sobrecalentamiento", "no"), ("interruptor_paro", "marcha"),
            ("nivel_combustible", "medio"), ("giro_arranque", "lento"), ("luces", "debil")]
    f1 = motor.que_falta(base + [("bornes", "desconocido")])
    cerrado = base + [("bornes", "normal"), ("voltaje", 11.5)]
    f2 = motor.que_falta(cerrado)
    siguiente = motor.siguiente_pregunta(cerrado)
    sin_triaje = motor.siguiente_pregunta([("giro_arranque", "lento"), ("luces", "debil"),
                                           ("bornes", "normal"), ("voltaje", 11.5)])
    medio = base + [("bornes", "normal"), ("voltaje", "desconocido"), ("clic_arranque", "no"),
                    ("tiempo_sin_uso", "desconocido")]
    f3 = motor.que_falta(medio)
    siguiente_medio = motor.siguiente_pregunta(medio)

    # Entrevista completa: después del triaje, cada pregunta debe ser la
    # sugerencia principal de que_falta/5, y 'fin' solo cuando no hay ninguna.
    respuestas = dict(base + [("bornes", "normal"), ("voltaje", 11.5)])
    obs, incoherencias = [], 0
    while True:
        variable = motor.siguiente_pregunta(obs)
        if len(obs) >= 8:
            sugeridas = motor.que_falta(obs)["sugerencias"]
            incoherencias += variable != (sugeridas[0]["variable"] if sugeridas else None)
        if variable is None or len(obs) > 30:
            break
        obs.append((variable, respuestas.get(variable, "desconocido")))

    obtenido = [f"Obtenido : tras 'No lo sé' en bornes, sugerencias="
                f"{[s['variable'] for s in f1['sugerencias']]}",
                f"           dictamen cerrado: situación={f2['situacion']}, "
                f"sugerencias={f2['sugerencias']}, siguiente_pregunta={siguiente}",
                f"           dictamen Alto sin triaje: siguiente_pregunta={sin_triaje}",
                f"           D01 medio sin más datos útiles: situación={f3['situacion']}, "
                f"sugerencias={f3['sugerencias']}, siguiente_pregunta={siguiente_medio}",
                f"           entrevista completa: {[v for v, _ in obs]}; incoherencias={incoherencias}"]
    return obtenido, [
        ("(1) un dato respondido 'No lo sé' no se vuelve a sugerir",
         "bornes" not in [s["variable"] for s in f1["sugerencias"]]),
        ("(2) con dictamen definitivo y sin sugerencias, la entrevista termina",
         f2["situacion"] == "definitivo" and f2["sugerencias"] == [] and siguiente is None),
        ("(3) aunque el dictamen esté cerrado, primero se completa el triaje de seguridad",
         sin_triaje == "cilindrada"),
        ("(4) con respaldo Medio y sin datos útiles, la entrevista también termina",
         f3["sugerencias"] == [] and siguiente_medio is None),
        ("(5) en toda la entrevista, cada pregunta es la sugerencia principal del panel",
         incoherencias == 0 and len(obs) > 8),
    ]


CASOS_MODULOS = [
    {"nombre": "¿Por qué? - Traza de reglas, hechos comprobados y descartes",
     "objetivo": "Comprobar que explicar_consulta/5 devuelve el árbol de reglas disparadas "
                 "(intermedias y finales), los hechos que unificaron con la base y las "
                 "hipótesis competidoras descartadas.",
     "entrada": "La misma del caso 7 (d04 con respaldo Alto por descarte).",
     "esperado": "Traza de d04 con R3.6 en la raíz, R2.11, R2.10, R2.15, R2.9 y R3.4; el hecho "
                 "'clic' unificado con requisito(d04, ...); d01, d02 y d03 descartadas.",
     "ejecutar": caso_traza},
    {"nombre": "¿Por qué? - Alternativas excluidas (\\+) y sin evidencia crítica",
     "objetivo": "Comprobar que las hipótesis que compartían síntomas se informan con su "
                 "causa: exclusión por negación por fallo o requisito mínimo no cumplido.",
     "entrada": "(1) La del caso 3. (2) Clic sí, giro normal, tablero sí.",
     "esperado": "(1) d04 excluida, motivo con \\+. (2) d04 sin evidencia crítica.",
     "ejecutar": caso_alternativas},
    {"nombre": "¿Qué falta? - Empate y dato de desempate",
     "objetivo": "Comprobar que que_falta/5 detecta el empate entre d01 y d02 y sugiere el "
                 "dato no ingresado de mayor peso, con su efecto sobre cada hipótesis.",
     "entrada": "[giro_arranque = lento, luces = debil]",
     "esperado": "Situación empate; primera sugerencia bornes (confirma o descarta d02).",
     "ejecutar": caso_empate},
    {"nombre": "¿Qué falta? - Dictamen definitivo y fuera de alcance",
     "objetivo": "Comprobar que el módulo distingue un dictamen ya definitivo y que no "
                 "pide datos cuando la motocicleta está fuera de alcance.",
     "entrada": "(1) La del caso 1. (2) La del caso 8.",
     "esperado": "(1) definitivo. (2) fuera_de_alcance sin sugerencias.",
     "ejecutar": caso_definitivo},
    {"nombre": "Validación en Prolog con ground/1 y minúsculas",
     "objetivo": "Comprobar que Prolog rechaza observaciones con variables libres llegadas "
                 "desde Python y acepta átomos en mayúscula convirtiéndolos a minúscula.",
     "entrada": "[obs(voltaje, _), obs('Luces', 'Debil'), obs(_, si), obs(giro_arranque, lento)]",
     "esperado": "2 inválidas; luces = debil aceptada; d01 entre los resultados.",
     "ejecutar": caso_ground},
    {"nombre": "Coherencia entre la entrevista y «¿Qué falta?»",
     "objetivo": "Comprobar que la entrevista y el panel usan un único criterio: un dato "
                 "respondido 'No lo sé' no se vuelve a sugerir, cada pregunta es la sugerencia "
                 "principal y la entrevista termina cuando ningún dato cambiaría el resultado.",
     "entrada": "Caso de batería: (1) bornes = desconocido; (2) bornes normales y voltaje 11,5; "
                "(3) el mismo dictamen sin triaje; (4) voltaje desconocido; (5) entrevista completa.",
     "esperado": "(1) bornes no sugerido. (2) definitivo, sin sugerencias y fin. (3) pregunta la "
                 "cilindrada. (4) fin con respaldo medio. (5) cero incoherencias.",
     "ejecutar": caso_coherencia},
]


def ejecutar_caso_modulo(motor: MotorMotoExpert, numero: int, caso: dict) -> bool:
    escribir("=" * 78)
    escribir(f"CASO {numero}: {caso['nombre']}")
    escribir("=" * 78)
    escribir(f"Objetivo : {caso['objetivo']}")
    escribir(f"Entrada  : {caso['entrada']}")
    escribir(f"Esperado : {caso['esperado']}")
    obtenido, comprobaciones = caso["ejecutar"](motor)
    for linea in obtenido:
        escribir(linea)
    return informar(comprobaciones)


def informar(comprobaciones: list[tuple[str, bool]]) -> bool:
    escribir("Comprobaciones:")
    for descripcion, ok in comprobaciones:
        escribir(f"   [{'OK' if ok else 'FALLA'}] {descripcion}")
    aprobado = all(ok for _, ok in comprobaciones)
    escribir(f"Veredicto: {'APROBADO' if aprobado else 'NO APROBADO'}")
    escribir()
    return aprobado


def main() -> int:
    escribir(f"MotoExpert - Evidencia de pruebas ({datetime.now():%Y-%m-%d %H:%M})")
    escribir()
    try:
        motor = MotorMotoExpert()
    except ErrorMotor as exc:
        escribir(f"No fue posible iniciar el motor: {exc}")
        return 1

    resultados = []
    for numero, caso in enumerate(CASOS, start=1):
        try:
            if caso["verificar"] is None:
                resultados.append(ejecutar_caso_invalidos(motor, numero, caso))
            else:
                resultados.append(ejecutar_caso(motor, numero, caso))
        except ErrorMotor as exc:     # un error no detiene el resto de pruebas
            escribir(f"ERROR en el caso {numero}: {exc}")
            resultados.append(False)
    try:
        resultados.append(ejecutar_entrevista(motor, len(CASOS) + 1))
    except ErrorMotor as exc:
        escribir(f"ERROR en la entrevista simulada: {exc}")
        resultados.append(False)
    for numero, caso in enumerate(CASOS_MODULOS, start=len(CASOS) + 2):
        try:
            resultados.append(ejecutar_caso_modulo(motor, numero, caso))
        except (ErrorMotor, StopIteration) as exc:
            escribir(f"ERROR en el caso {numero}: {exc!r}")
            resultados.append(False)

    escribir("=" * 78)
    escribir(f"RESUMEN: {sum(resultados)} de {len(resultados)} casos aprobados.")
    escribir("=" * 78)

    with open(RUTA_EVIDENCIA, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(SALIDA) + "\n")
    print(f"\nEvidencia guardada en {RUTA_EVIDENCIA}")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
