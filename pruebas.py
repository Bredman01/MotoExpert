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
Casos del entregable 3 (lenguaje natural y modo experto):
 16. DCG - Descripción completa en español
 17. DCG - Negaciones, sujeto omitido y expresiones
 18. DCG - Textos vacíos, ajenos, repetidos y fuera de rango
 19. Modo experto - assertz/1, persistencia y reinicio
 20. Pre-procesamiento numérico con scikit-learn (opcional)
 21. Causas sin distinguir: Alto confirmado por la misma prueba
 22. Modo experto: pregunta y reglas nuevas que distinguen diagnósticos
 23. Modo experto: editar lo aprendido (sin cambios si hay errores)

Las pruebas usan una copia temporal de la base con el conocimiento aprendido
vacío: no dependen de lo que el experto haya enseñado ni lo modifican.

Uso:  python pruebas.py

Autor: Bredman Estiven Velez Cortez
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
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


# ---------------------------------------------------------------------------
# Casos del entregable 3: lenguaje natural (DCG) y modo experto
# ---------------------------------------------------------------------------
TEXTO_DCG_1 = ("Mi moto de 150 cc no arranca, el motor gira lento y las luces están débiles.\n"
               "No huele a gasolina y la batería marca 11,5 voltios")
TEXTO_DCG_2 = ("No hay fugas. A veces no arranca por las mañanas, da tirones y bota humo negro; "
               "el filtro de aire está muy sucio. Lleva 3 meses guardada con gasolina vieja.")


def caso_dcg(motor: MotorMotoExpert, texto: str, esperado: dict, diagnostico=None):
    i = motor.interpretar(texto)
    obtenidos = dict(i["observaciones"])
    obtenido = [f"Consulta : {i['consulta']}",
                "Obtenido : " + "; ".join(f"{r['variable']}={r['valor']} ← «{r['frase']}»"
                                          for r in i["reconocidos"]),
                f"           no reconocidas={i['no_reconocidas']}"]
    comprobaciones = [("hechos extraídos = esperados", obtenidos == esperado),
                      ("ninguna palabra con contenido quedó sin reconocer", i["no_reconocidas"] == [])]
    if diagnostico:
        r = motor.consultar(i["observaciones"])
        obtenido.append(f"           dictamen={resumen(r)}")
        comprobaciones.append((f"{diagnostico[0]} con respaldo {diagnostico[1]} a partir del texto",
                               respaldo_de(r, diagnostico[0]) == diagnostico[1]))
    return obtenido, comprobaciones


def caso_dcg_bordes(motor: MotorMotoExpert):
    vacio = motor.interpretar("")
    ajeno = motor.interpretar("quisiera saber el precio de una llanta")
    mixto = motor.interpretar("el motor no gira, el motor gira lento y la moto tiene 5000 cc")
    estados = [(r["variable"], r["valor"], r["estado"]) for r in mixto["reconocidos"]]
    obtenido = [f"Obtenido : (1) {vacio['observaciones']} {vacio['no_reconocidas']}",
                f"           (2) {ajeno['observaciones']} no reconocidas={ajeno['no_reconocidas']}",
                f"           (3) {estados}"]
    return obtenido, [
        ("(1) texto vacío: sin observaciones ni errores", vacio["observaciones"] == []),
        ("(2) texto ajeno: sin observaciones", ajeno["observaciones"] == []),
        ("(2) informa 'precio' y 'llanta' como no reconocidas",
         {"precio", "llanta"} <= set(ajeno["no_reconocidas"])),
        ("(3) el primer giro vale y el segundo queda como repetido",
         ("giro_arranque", "no_gira", "aceptado") in estados
         and ("giro_arranque", "lento", "repetido") in estados),
        ("(3) 5000 cc se marca inválido y no se usa",
         ("cilindrada", 5000, "invalido") in estados and "cilindrada" not in dict(mixto["observaciones"])),
    ]


def caso_experto(motor: MotorMotoExpert):
    ruta = motor.ruta_aprendido()
    with open(ruta, encoding="utf-8") as archivo:
        antes = archivo.read()
    mala = motor.aprender({"nombre": " ", "subsistema": "", "rama": "otra", "prioridad": 9,
                           "evidencias": [], "verificaciones": [], "descartes": [("luces", "morado")],
                           "competidoras": ["d99"], "recomendaciones": []})
    ficha = {"nombre": "Regulador de voltaje (prueba)", "subsistema": "Sistema de carga",
             "rama": "electrica", "prioridad": 3,
             "evidencias": [("luces", "debil"), ("falla_intermitente", "si")],
             "verificaciones": [("voltaje", "bajo")], "descartes": [],
             "competidoras": ["d01", "d02"],
             "recomendaciones": ["Revisar el regulador de voltaje en un taller."]}
    ok = motor.aprender(ficha)
    codigo = ok["codigo"]
    r = motor.consultar([("luces", "debil"), ("falla_intermitente", "si"), ("voltaje", 11.4)])
    with open(ruta, encoding="utf-8") as archivo:
        escrito = archivo.read()
    # Un proceso de Prolog nuevo, sin PySwip: simula reiniciar el programa.
    base = base_de(motor)
    reinicio = subprocess.run(
        ["swipl", "-q", "-g", f"(diagnostico({codigo}, N, _, _) -> write(N) ; write(no_existe)), halt",
         base], capture_output=True, text=True, encoding="utf-8", timeout=60)
    olvido = motor.olvidar(codigo)
    base_original = motor.olvidar("d01")
    with open(ruta, encoding="utf-8") as archivo:
        despues = archivo.read()
    obtenido = [f"Obtenido : ficha inválida -> {mala['estado']}, {len(mala['errores'])} errores",
                f"           ficha válida -> {ok}",
                f"           dictamen con {codigo}: {resumen(r)}",
                f"           proceso nuevo de Prolog -> {reinicio.stdout.strip()!r}",
                f"           olvidar {codigo} -> {olvido['estado']}; olvidar d01 -> {base_original['estado']}"]
    return obtenido, [
        ("(1) la ficha inválida se rechaza con sus errores", mala["estado"] == "error" and len(mala["errores"]) >= 6),
        ("(2) la ficha válida se aprende con un código nuevo", ok["estado"] == "ok" and codigo.startswith("d")),
        ("(3) el diagnóstico aprendido participa en consultar/6 con respaldo alto",
         respaldo_de(r, codigo) == "alto"),
        ("(4) queda escrito en conocimiento_aprendido.pl",
         f"diagnostico({codigo}, 'Regulador de voltaje (prueba)'" in escrito),
        ("(5) un proceso de Prolog nuevo lo carga desde el archivo",
         reinicio.stdout.strip() == "Regulador de voltaje (prueba)"),
        ("(6) olvidar lo retira de la memoria y deja el archivo como estaba",
         olvido["estado"] == "ok" and despues == antes
         and codigo not in [d["codigo"] for d in motor.catalogo_diagnosticos()]),
        ("(7) un diagnóstico de la base original no se puede borrar", base_original["estado"] == "error"),
    ]


def caso_clasificador(motor: MotorMotoExpert):
    from clasificador import CLASIFICADORES, convertir_mediciones
    temp = CLASIFICADORES["temperatura"]
    dias = CLASIFICADORES["dias_sin_uso"]
    casos_t = {t: convertir_mediciones({"temperatura": t})[0] for t in (85, 117, 118, 135)}
    casos_d = {d: convertir_mediciones({"dias_sin_uso": d})[0] for d in (3, 7, 29, 45)}
    _, fuera = convertir_mediciones({"temperatura": 900})
    obs, _ = convertir_mediciones({"temperatura": 135, "dias_sin_uso": 45})
    r = motor.consultar(obs)
    obtenido = [f"Obtenido : método={temp.metodo}; umbral temperatura={temp.umbrales()}; "
                f"umbrales días={dias.umbrales()}",
                f"           temperatura -> {casos_t}",
                f"           días -> {casos_d}",
                f"           900 °C -> {fuera}",
                f"           consultar({obs}) -> {resumen(r)}"]
    return obtenido, [
        ("el árbol aprende el umbral 117,5 °C de la tabla de referencia", temp.umbrales() == [117.5]),
        ("y los umbrales 6,5 y 29,5 días", dias.umbrales() == [6.5, 29.5]),
        ("117 °C -> no; 118 °C -> si",
         casos_t[117] == [("sobrecalentamiento", "no")] and casos_t[118] == [("sobrecalentamiento", "si")]),
        ("3 -> dias, 7 -> semanas, 45 -> meses",
         [casos_d[k][0][1] for k in (3, 7, 45)] == ["dias", "semanas", "meses"]),
        ("una medición fuera de rango no produce hechos", fuera and "error" in fuera[0]),
        ("los hechos discretos alimentan al motor (alerta A02)", "a02" in codigos(r)),
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
    {"nombre": "Lenguaje natural - Descripción completa con la DCG",
     "objetivo": "Comprobar que interpretar_texto/4 analiza una oración en español (con tildes, "
                 "comas y un salto de línea) y extrae los hechos que alimentan al motor.",
     "entrada": TEXTO_DCG_1,
     "esperado": "cilindrada 150, dificultad persistente, giro lento, luces débiles, sin olor a "
                 "gasolina y voltaje 11,5; ninguna palabra sin reconocer; D01 con respaldo alto.",
     "ejecutar": lambda motor: caso_dcg(motor, TEXTO_DCG_1, {
         "cilindrada": 150, "dificultad_arranque": "persistente", "giro_arranque": "lento",
         "luces": "debil", "olor_gasolina": "no", "voltaje": 11.5}, diagnostico=("d01", "alto"))},
    {"nombre": "Lenguaje natural - Negaciones, sujeto omitido y expresiones",
     "objetivo": "Comprobar negaciones ('no hay fugas'), sujeto implícito ('a veces no arranca'), "
                 "cópula con intensificador ('está muy sucio') y medidas sin unidad explícita.",
     "entrada": TEXTO_DCG_2,
     "esperado": "fuga no, dificultad ocasional, condición en frío, tirones, humo negro, filtro "
                 "sucio, tiempo sin uso en meses y gasolina vieja.",
     "ejecutar": lambda motor: caso_dcg(motor, TEXTO_DCG_2, {
         "fuga_combustible": "no", "dificultad_arranque": "ocasional", "condicion_motor": "frio",
         "tirones": "si", "humo": "negro", "filtro_aire": "sucio", "tiempo_sin_uso": "meses",
         "combustible_viejo": "si"})},
    {"nombre": "Lenguaje natural - Textos vacíos, ajenos, repetidos y fuera de rango",
     "objetivo": "Comprobar que la DCG no falla ni inventa hechos: un texto vacío o ajeno no "
                 "produce observaciones; un dato repetido vale la primera vez; un número fuera de "
                 "rango se marca inválido y no se usa.",
     "entrada": "(1) ''. (2) 'quisiera saber el precio de una llanta'. (3) 'el motor no gira, el "
                "motor gira lento y la moto tiene 5000 cc'.",
     "esperado": "(1) y (2) sin observaciones; (2) informa 'precio' y 'llanta' como no "
                 "reconocidas. (3) giro no_gira; el segundo giro repetido; 5000 cc inválido.",
     "ejecutar": caso_dcg_bordes},
    {"nombre": "Modo experto - assertz/1 y persistencia en conocimiento_aprendido.pl",
     "objetivo": "Comprobar que aprender_diagnostico/4 valida la ficha, inyecta el diagnóstico "
                 "con assertz/1, lo escribe en el archivo .pl, que un proceso de Prolog NUEVO lo "
                 "carga al iniciar y que olvidar_diagnostico/3 lo retira de la memoria y del archivo.",
     "entrada": "Ficha inválida; luego ficha 'Regulador de voltaje (prueba)' con evidencias "
                "luces débiles y falla intermitente, verificación voltaje bajo.",
     "esperado": "(1) errores sin cambios. (2) estado ok y nuevo código. (3) participa en "
                 "consultar/6. (4) escrito en el archivo. (5) visible tras reiniciar Prolog. "
                 "(6) olvidado de memoria y archivo; la base original no se puede borrar.",
     "ejecutar": caso_experto},
    {"nombre": "Pre-procesamiento numérico (opcional) - clasificador scikit-learn",
     "objetivo": "Comprobar que el clasificador convierte mediciones continuas en hechos "
                 "discretos antes de enviarlos a Prolog, con umbrales aprendidos de una tabla de "
                 "referencia.",
     "entrada": "Temperaturas 85, 117, 118, 135 y 900 °C; días 3, 7, 29 y 45.",
     "esperado": "Umbrales 117,5 °C y 6,5/29,5 días; 135 °C y 45 días producen "
                 "sobrecalentamiento = si y tiempo_sin_uso = meses, que activan la alerta A02.",
     "ejecutar": caso_clasificador},
    {"nombre": "Causas sin distinguir - Alto confirmado por la misma prueba",
     "objetivo": "Comprobar que si dos diagnósticos que compiten quedan en Alto confirmados por "
                 "exactamente la misma prueba, «¿Qué falta?» informa 'ambiguo' en lugar de "
                 "'definitivo', y que no lo hace cuando cada uno tiene su propia prueba.",
     "entrada": "(1) Control: giro lento, luces débiles, voltaje 11,6 y bornes sulfatados. "
                "(2) Diagnóstico aprendido 'Regulador de voltaje dañado' confirmado por voltaje "
                "bajo, con luces débiles, falla intermitente, bornes normales y voltaje 12,3.",
     "esperado": "(1) definitivo. (2) el regulador y D01 en Alto; situación ambiguo.",
     "ejecutar": lambda motor: caso_ambiguo(motor)},
    {"nombre": "Modo experto - Pregunta y reglas nuevas que distinguen diagnósticos",
     "objetivo": "Comprobar que el experto puede crear una pregunta nueva (con sus frases para la "
                 "DCG) y reglas sobre diagnósticos existentes, que el sistema las usa para "
                 "distinguir causas, que persisten tras reiniciar y que se pueden retirar.",
     "entrada": "Pregunta 'Voltaje al acelerar' (sí/no). Reglas: 'no' confirma el regulador, "
                "'sí' lo descarta y 'no' descarta D01. Descripción con 'el voltaje no sube al acelerar'.",
     "esperado": "La pregunta se sugiere para distinguir; la DCG la reconoce; queda solo el "
                 "regulador en Alto; un proceso nuevo carga todo; al final el archivo queda igual.",
     "ejecutar": lambda motor: caso_pregunta_y_reglas(motor)},
    {"nombre": "Modo experto - Editar lo aprendido (y no cambiar nada si hay errores)",
     "objetivo": "Comprobar que un diagnóstico y una pregunta aprendidos se pueden corregir "
                 "conservando su código, y que una edición inválida se rechaza con sus errores "
                 "sin modificar nada.",
     "entrada": "Edición inválida del diagnóstico (nombre de otro, sin subsistema, prioridad 9, "
                "compite consigo mismo) y de la pregunta (quita «No», que usa una regla). Luego "
                "ediciones válidas.",
     "esperado": "Los errores se informan y el archivo queda idéntico; las ediciones válidas se "
                 "aplican y la regla agregada aparte se conserva.",
     "ejecutar": lambda motor: caso_edicion(motor)},
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


FICHA_REGULADOR = {
    "nombre": "Regulador de voltaje dañado", "subsistema": "Sistema de carga", "rama": "electrica",
    "prioridad": 3, "evidencias": [("luces", "debil"), ("falla_intermitente", "si")],
    "verificaciones": [("voltaje", "bajo")], "descartes": [], "competidoras": ["d01", "d02"],
    "recomendaciones": ["Revisar el regulador de voltaje en un taller."]}
CASO_REGULADOR = [("luces", "debil"), ("falla_intermitente", "si"), ("bornes", "normal"), ("voltaje", 12.3)]


def caso_ambiguo(motor: MotorMotoExpert):
    control = [("giro_arranque", "lento"), ("luces", "debil"), ("voltaje", 11.6), ("bornes", "sulfatados")]
    antes = motor.que_falta(control)
    codigo = motor.aprender(FICHA_REGULADOR)["codigo"]
    r = motor.consultar(CASO_REGULADOR)
    f = motor.que_falta(CASO_REGULADOR)
    motor.olvidar(codigo)
    obtenido = [f"Obtenido : control D01+D02 -> {antes['situacion']}",
                f"           con {codigo}: dictamen={resumen(r)}",
                f"           ¿Qué falta? -> {f['situacion']}; evaluadas="
                f"{[e['codigo'] for e in f['evaluadas']]}"]
    return obtenido, [
        ("control: D01 y D02 confirmadas cada una por su propia prueba -> definitivo",
         antes["situacion"] == "definitivo"),
        (f"{codigo} y D01 quedan en Alto", respaldo_de(r, codigo) == "alto" and respaldo_de(r, "d01") == "alto"),
        ("como las confirma la misma prueba (voltaje bajo), la situación es «ambiguo», no definitivo",
         f["situacion"] == "ambiguo"),
        ("el panel evalúa justo esas dos hipótesis", {e["codigo"] for e in f["evaluadas"]} == {codigo, "d01"}),
    ]


def caso_pregunta_y_reglas(motor: MotorMotoExpert):
    ruta = motor.ruta_aprendido()
    with open(ruta, encoding="utf-8") as archivo:
        antes = archivo.read()
    mala = motor.aprender_pregunta({"etiqueta": "", "texto": "", "grupo": "x", "tipo": "x",
                                    "opciones": ["Sí"], "frases": [("Tal vez", "algo")]})
    codigo = motor.aprender(FICHA_REGULADOR)["codigo"]
    p = motor.aprender_pregunta({
        "etiqueta": "Voltaje al acelerar",
        "texto": "Con el motor encendido, ¿sube el voltaje de la batería al acelerar?",
        "grupo": "electrico", "tipo": "prueba_tecnica", "opciones": ["Sí", "No"],
        "frases": [("No", "el voltaje no sube al acelerar"), ("Sí", "el voltaje sube al acelerar")]})
    var = p["variable"]
    r1 = motor.aprender_regla(codigo, "verificacion", var, "no")
    r2 = motor.aprender_regla(codigo, "descarte", var, "si")
    r3 = motor.aprender_regla("d01", "descarte", var, "no")
    repetida = motor.aprender_regla("d01", "descarte", var, "no")
    sugerida = motor.que_falta(CASO_REGULADOR)["sugerencias"][0]["variable"]
    entrevista = motor.siguiente_pregunta(
        [("cilindrada", 150), ("alimentacion", "carburador"), ("fuga_combustible", "no"),
         ("olor_gasolina", "no"), ("sobrecalentamiento", "no"), ("interruptor_paro", "marcha"),
         ("nivel_combustible", "medio"), ("giro_arranque", "normal")] + CASO_REGULADOR)
    texto = motor.interpretar("las luces están débiles, la falla es intermitente, los bornes están "
                              "bien, la batería marca 12,3 V y el voltaje no sube al acelerar")
    r = motor.consultar(texto["observaciones"])
    f = motor.que_falta(texto["observaciones"])
    en_catalogo = var in [c["variable"] for c in motor.catalogo()]
    reinicio = subprocess.run(
        ["swipl", "-q", "-g", "reglas_aprendidas(R), length(R, N), write(N), "
         f"(variable({var}, _, _, _, _) -> write(' pregunta') ; true), halt", base_de(motor)],
        capture_output=True, text=True, encoding="utf-8", timeout=60)
    en_uso = motor.olvidar_pregunta(var)
    for regla in (r1, r2, r3):
        motor.olvidar_regla(regla["id"])
    motor.olvidar(codigo)
    limpia = motor.olvidar_pregunta(var)
    with open(ruta, encoding="utf-8") as archivo:
        despues = archivo.read()
    obtenido = [f"Obtenido : pregunta inválida -> {len(mala['errores'])} errores",
                f"           pregunta -> {p}; reglas -> {[x['id'] for x in (r1, r2, r3)]}; repetida -> {repetida['estado']}",
                f"           sugerida por ¿Qué falta? -> {sugerida}; entrevista pregunta -> {entrevista}",
                f"           DCG -> {texto['observaciones']}",
                f"           dictamen -> {resumen(r)}; situación -> {f['situacion']}",
                f"           proceso nuevo de Prolog -> {reinicio.stdout.strip()!r}",
                f"           olvidar pregunta en uso -> {en_uso['estado']}; tras limpiar -> {limpia['estado']}"]
    return obtenido, [
        ("(1) la pregunta inválida se rechaza con sus errores", mala["estado"] == "error" and len(mala["errores"]) >= 5),
        ("(2) la pregunta se crea y entra al catálogo del formulario", p["estado"] == "ok" and en_catalogo),
        ("(3) las tres reglas se crean y una repetida se rechaza",
         all(x["estado"] == "ok" for x in (r1, r2, r3)) and repetida["estado"] == "error"),
        ("(4) ¿Qué falta? y la entrevista sugieren la pregunta nueva para distinguir",
         sugerida == var and entrevista == var),
        ("(5) la DCG reconoce la frase de la pregunta nueva", dict(texto["observaciones"]).get(var) == "no"),
        (f"(6) con esa respuesta queda solo {codigo}: D01 descartada por la regla nueva",
         codigos(r) == [codigo] and respaldo_de(r, codigo) == "alto" and f["situacion"] == "definitivo"),
        ("(7) un proceso de Prolog nuevo carga las 3 reglas y la pregunta", reinicio.stdout.strip() == "3 pregunta"),
        ("(8) una pregunta en uso no se puede borrar; limpia el archivo al final",
         en_uso["estado"] == "error" and limpia["estado"] == "ok" and despues == antes),
    ]


def caso_edicion(motor: MotorMotoExpert):
    ruta = motor.ruta_aprendido()
    codigo = motor.aprender(FICHA_REGULADOR)["codigo"]
    var = motor.aprender_pregunta({"etiqueta": "Voltaje al acelerar", "texto": "¿Sube el voltaje al acelerar?",
                                   "grupo": "electrico", "tipo": "prueba_tecnica", "opciones": ["Sí", "No"],
                                   "frases": [("No", "el voltaje no sube al acelerar")]})["variable"]
    regla = motor.aprender_regla(codigo, "verificacion", var, "no")
    with open(ruta, encoding="utf-8") as archivo:
        antes = archivo.read()

    ficha_mala = dict(FICHA_REGULADOR, nombre="Batería descargada o debilitada", subsistema="",
                      prioridad=9, competidoras=[codigo])
    mala_d = motor.editar_diagnostico(codigo, ficha_mala)
    mala_p = motor.editar_pregunta(var, {"etiqueta": "Voltaje al acelerar", "texto": "x", "grupo": "electrico",
                                         "tipo": "prueba_tecnica", "opciones": ["Sí", "Tal vez"], "frases": []})
    with open(ruta, encoding="utf-8") as archivo:
        tras_errores = archivo.read()

    datos = motor.datos_diagnostico(codigo)
    ok_d = motor.editar_diagnostico(codigo, dict(datos, prioridad=2,
                                                 recomendaciones=datos["recomendaciones"] + ["Medir la carga."]))
    ok_p = motor.editar_pregunta(var, {"etiqueta": "Voltaje al acelerar", "texto": "¿Sube el voltaje al acelerar?",
                                       "grupo": "electrico", "tipo": "prueba_tecnica",
                                       "opciones": ["Sí", "No", "No sé medirlo"],
                                       "frases": [("No", "el voltaje no sube")]})
    nuevo = motor.datos_diagnostico(codigo)
    entiende = dict(motor.interpretar("el voltaje no sube")["observaciones"]).get(var)
    reglas = len(motor.reglas_aprendidas())
    motor.olvidar_regla(regla["id"])
    motor.olvidar(codigo)
    motor.olvidar_pregunta(var)
    obtenido = [f"Obtenido : edición inválida del diagnóstico -> {mala_d['estado']}: {mala_d['errores']}",
                f"           edición inválida de la pregunta -> {mala_p['estado']}: {mala_p['errores']}",
                f"           ediciones válidas -> {ok_d['estado']}, {ok_p['estado']}; prioridad={nuevo['prioridad']}; "
                f"recomendaciones={nuevo['recomendaciones']}; reglas={reglas}; frase editada -> {entiende}"]
    return obtenido, [
        ("(1) la edición inválida del diagnóstico se rechaza explicando cada error",
         mala_d["estado"] == "error" and len(mala_d["errores"]) == 4),
        ("(2) quitar una respuesta que usa una regla se rechaza",
         mala_p["estado"] == "error" and any("se usa" in x for x in mala_p["errores"])),
        ("(3) tras los errores, lo aprendido y el archivo quedan EXACTAMENTE igual", tras_errores == antes),
        ("(4) la edición válida cambia la prioridad y las recomendaciones, con el mismo código",
         ok_d["estado"] == "ok" and nuevo["prioridad"] == 2 and "Medir la carga." in nuevo["recomendaciones"]),
        ("(5) la regla agregada aparte se conserva al editar", reglas == 1),
        ("(6) la pregunta editada usa sus frases nuevas", ok_p["estado"] == "ok" and entiende == "no"),
    ]


def base_de(motor: MotorMotoExpert) -> str:
    """Ruta de la base que cargó el motor (la copia de prueba)."""
    return os.path.join(os.path.dirname(motor.ruta_aprendido()), "base_conocimiento.pl")


def copia_de_prueba() -> str:
    """
    Copia base_conocimiento.pl a una carpeta temporal con el conocimiento
    aprendido vacío. Así las pruebas no dependen de lo que el experto haya
    enseñado al sistema y nunca modifican el conocimiento_aprendido.pl real.
    """
    carpeta = tempfile.mkdtemp(prefix="motoexpert_pruebas_")
    origen = os.path.dirname(os.path.abspath(__file__))
    shutil.copy(os.path.join(origen, "base_conocimiento.pl"), carpeta)
    with open(os.path.join(carpeta, "conocimiento_aprendido.pl"), "w", encoding="utf-8", newline="\n") as f:
        f.write(":- encoding(utf8).\n")
    return os.path.join(carpeta, "base_conocimiento.pl")


def main() -> int:
    escribir(f"MotoExpert - Evidencia de pruebas ({datetime.now():%Y-%m-%d %H:%M})")
    escribir("Base: copia de base_conocimiento.pl con el conocimiento aprendido vacío.")
    escribir()
    try:
        motor = MotorMotoExpert(copia_de_prueba())
        motor.consulta_libre("guardar_aprendido")   # el archivo vacío, con el encabezado de Prolog
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
