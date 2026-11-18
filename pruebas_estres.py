"""
pruebas_estres.py - Pruebas de estrés del manejo de contradicciones (entregable 4).

Somete las reglas de consistencia de MotoExpert a miles de entradas y
comprueba, contra un ORÁCULO escrito en Python a partir de los mismos hechos
incompatibles/3, que el sistema:

  E1. Detecta TODAS las incompatibilidades entre pares de respuestas
      (barrido exhaustivo de todos los pares variable-valor del catálogo).
  E2. Nunca emite un diagnóstico con datos incompatibles y nunca bloquea
      datos coherentes (casos aleatorios con contradicciones inyectadas).
  E3. Mantiene las alertas de seguridad aunque los datos se contradigan.
  E4. Resiste entradas hostiles: estructuras mal formadas, variables libres,
      listas enormes y textos muy largos o con contradicciones.
  E5. Detecta contradicciones dentro de una descripción en lenguaje natural.
  E6. Responde en tiempos aceptables (latencia media y máxima).

Usa una copia temporal de la base con el conocimiento aprendido vacío.
Guarda el reporte en evidencia_estres.txt y un resumen en resumen_estres.json.

Uso:  python pruebas_estres.py

Autor: Bredman Estiven Velez Cortez
"""

from __future__ import annotations

import json
import os
import random
import statistics
import sys
import time
from datetime import datetime

from motor import ErrorMotor, MotorMotoExpert
from pruebas import copia_de_prueba

CARPETA = os.path.dirname(os.path.abspath(__file__))
RUTA_EVIDENCIA = os.path.join(CARPETA, "evidencia_estres.txt")
RUTA_RESUMEN = os.path.join(CARPETA, "resumen_estres.json")
SEMILLA = 2026
CASOS_ALEATORIOS = 1500
SALIDA: list[str] = []
TIEMPOS: dict[str, list[float]] = {}


def escribir(texto: str = "") -> None:
    print(texto)
    SALIDA.append(texto)


def medir(nombre: str, funcion, *args):
    """Ejecuta una consulta y guarda su duración (ms) para el reporte de latencia."""
    inicio = time.perf_counter()
    resultado = funcion(*args)
    TIEMPOS.setdefault(nombre, []).append((time.perf_counter() - inicio) * 1000)
    return resultado


# ---------------------------------------------------------------------------
# Oráculo: reimplementa en Python la semántica de las reglas de consistencia
# a partir de los hechos de Prolog. Si Prolog y el oráculo difieren, es un error.
# ---------------------------------------------------------------------------
class Oraculo:
    def __init__(self, motor: MotorMotoExpert) -> None:
        self.reglas = []
        for s in motor.consulta_libre(
                "incompatibles(I, Cs, _), "
                "findall([V, X], member(V-X, Cs), P), "
                "findall([V, Mn, Mx], member(rango(V, Mn, Mx), Cs), R)"):
            pares = [(str(v), str(x)) for v, x in s["P"]]
            rangos = [(str(v), float(mn), float(mx)) for v, mn, mx in s["R"]]
            self.reglas.append((str(s["I"]), pares, rangos))
        self.disparadores = {(str(s["V"]), str(s["X"])) for s in
                             motor.consulta_libre("disparador_alerta(A, V, X)")}
        self.alerta_de = {(str(s["V"]), str(s["X"])): str(s["A"]) for s in
                          motor.consulta_libre("disparador_alerta(A, V, X)")}

    @staticmethod
    def primeros(obs):
        """Primer valor de cada variable (lo que conserva normalizar_caso/2)."""
        vistos = {}
        for v, x in obs:
            vistos.setdefault(v, x)
        return vistos

    def esperadas(self, obs) -> set[str]:
        caso = self.primeros(obs)
        ids = set()
        valores = {}
        for v, x in obs:
            if x != "desconocido":
                valores.setdefault(v, set()).add(x)
        if any(len(xs) >= 2 for xs in valores.values()):
            ids.add("c00")
        for regla, pares, rangos in self.reglas:
            ok = all(caso.get(v) == x for v, x in pares)
            ok = ok and all(isinstance(caso.get(v), (int, float)) and mn <= caso[v] < mx
                            for v, mn, mx in rangos)
            if ok:
                ids.add(regla)
        return ids

    def alertas(self, obs) -> set[str]:
        return {self.alerta_de[(v, x)] for v, x in obs if (v, x) in self.disparadores}


# ---------------------------------------------------------------------------
# Generadores de casos
# ---------------------------------------------------------------------------
def valores_categoricos(catalogo):
    return {i["variable"]: [o["valor"] for o in i["opciones"] if o["valor"] != "desconocido"]
            for i in catalogo if i["entrada"] == "opciones"}


def caso_aleatorio(rnd: random.Random, valores: dict, forzar_conflicto: bool):
    variables = rnd.sample(sorted(valores), rnd.randint(3, 12))
    obs = [(v, rnd.choice(valores[v])) for v in variables]
    if rnd.random() < 0.5:
        obs.append(("voltaje", round(rnd.uniform(0, 20), 1)))
    if rnd.random() < 0.3:
        obs.append(("cilindrada", rnd.choice([110, 125, 150, 200, 250])))
    if forzar_conflicto:
        v, x = rnd.choice(obs)
        if v in valores and len(valores[v]) > 1:
            obs.append((v, rnd.choice([y for y in valores[v] if y != x])))
    rnd.shuffle(obs)
    return obs


# ---------------------------------------------------------------------------
# Escenarios
# ---------------------------------------------------------------------------
def e1_barrido_exhaustivo(motor, oraculo, valores):
    """Todos los pares de respuestas (variable distinta) del catálogo."""
    pares = [(v, x) for v in sorted(valores) for x in valores[v]]
    combinaciones, detectadas, errores = 0, 0, []
    for i, a in enumerate(pares):
        for b in pares[i + 1:]:
            if a[0] == b[0]:
                continue
            obs = [a, b]
            obtenidas = {x["id"] for x in medir("inconsistencias/2", motor.inconsistencias, obs)}
            esperadas = oraculo.esperadas(obs)
            combinaciones += 1
            detectadas += bool(obtenidas)
            if obtenidas != esperadas:
                errores.append((obs, sorted(obtenidas), sorted(esperadas)))
    # Las reglas de tres condiciones (C06) y las numéricas se cubren aparte.
    triples = 0
    for regla, condiciones, rangos in oraculo.reglas:
        if len(condiciones) == 3:
            for quitar in range(4):
                obs = [c for k, c in enumerate(condiciones) if k != quitar]
                obtenidas = {x["id"] for x in motor.inconsistencias(obs)}
                triples += 1
                if obtenidas != oraculo.esperadas(obs):
                    errores.append((obs, sorted(obtenidas), sorted(oraculo.esperadas(obs))))
    numericos = 0
    for voltaje in [x / 10 for x in range(0, 201, 5)]:
        for extra in ([], [("tablero", "si")], [("luces", "normal")], [("tablero", "no")]):
            obs = [("voltaje", voltaje)] + extra
            obtenidas = {x["id"] for x in motor.inconsistencias(obs)}
            numericos += 1
            if obtenidas != oraculo.esperadas(obs):
                errores.append((obs, sorted(obtenidas), sorted(oraculo.esperadas(obs))))
    return {"pares": combinaciones, "pares_incompatibles": detectadas, "subconjuntos_C06": triples,
            "barrido_voltaje": numericos, "discrepancias": len(errores), "ejemplos_error": errores[:5]}


def e2_e3_aleatorios(motor, oraculo, valores, rnd):
    """Casos aleatorios: la mitad con una contradicción C00 inyectada."""
    resumen = {"casos": 0, "inconsistentes": 0, "coherentes": 0, "falsos_negativos": 0,
               "falsos_positivos": 0, "diagnosticos_con_datos_incompatibles": 0,
               "alertas_perdidas": 0, "que_falta_incorrecto": 0, "entrevista_incorrecta": 0,
               "excepciones": 0}
    ejemplos = []
    for n in range(CASOS_ALEATORIOS):
        obs = caso_aleatorio(rnd, valores, forzar_conflicto=n % 2 == 0)
        try:
            ins = {x["id"] for x in medir("inconsistencias/2", motor.inconsistencias, obs)}
            r = medir("consultar/6", motor.consultar, obs)
            f = medir("que_falta/5", motor.que_falta, obs)
            p = medir("siguiente_pregunta/2", motor.siguiente_pregunta, obs)
        except ErrorMotor as exc:
            resumen["excepciones"] += 1
            ejemplos.append(("excepción", obs, str(exc)[:120]))
            continue
        esperadas = oraculo.esperadas(obs)
        resumen["casos"] += 1
        bloqueado = r["estado"] == "inconsistente"
        if esperadas:
            resumen["inconsistentes"] += 1
            if not bloqueado or ins != esperadas:
                resumen["falsos_negativos"] += 1
                ejemplos.append(("falso negativo", obs, sorted(ins)))
            if any(x["tipo"] != "alerta" for x in r["resultados"]):
                resumen["diagnosticos_con_datos_incompatibles"] += 1
                ejemplos.append(("diagnóstico emitido", obs, [x["codigo"] for x in r["resultados"]]))
            if {x["codigo"] for x in r["resultados"]} != oraculo.alertas(obs):
                resumen["alertas_perdidas"] += 1
                ejemplos.append(("alertas", obs, [x["codigo"] for x in r["resultados"]]))
            involucradas = {v for x in motor.inconsistencias(obs) for v in x["variables"]}
            if f["situacion"] != "inconsistente" or not f["sugerencias"] \
                    or {s["variable"] for s in f["sugerencias"]} != involucradas:
                resumen["que_falta_incorrecto"] += 1
            if p not in involucradas:
                resumen["entrevista_incorrecta"] += 1
        else:
            resumen["coherentes"] += 1
            if bloqueado or ins:
                resumen["falsos_positivos"] += 1
                ejemplos.append(("falso positivo", obs, sorted(ins)))
    resumen["ejemplos_error"] = ejemplos[:5]
    return resumen


def e4_entradas_hostiles(motor):
    """Entradas mal formadas o enormes: el sistema no debe fallar ni diagnosticar a ciegas."""
    resultados = []

    def probar(nombre, entrada, esperado):
        inicio = time.perf_counter()
        try:
            r = motor.consultar(entrada)
            ins = motor.inconsistencias(entrada)
            obtenido = f"estado={r['estado']}; inconsistencias={[x['id'] for x in ins]}"
            ok = esperado(r, ins)
        except ErrorMotor as exc:
            obtenido, ok = f"ErrorMotor: {str(exc)[:80]}", False
        resultados.append({"prueba": nombre, "obtenido": obtenido, "ok": ok,
                           "ms": round((time.perf_counter() - inicio) * 1000, 1)})

    probar("Lista vacía", [], lambda r, i: r["estado"] == "sin_datos" and i == [])
    probar("Entrada que no es lista", "hola", lambda r, i: r["estado"] == "sin_datos" and i == [])
    probar("Variables libres (ground/1)", "[obs(luces, _), obs(_, si), obs(tablero, X)]",
           lambda r, i: len(r["invalidas"]) == 3 and i == [])
    probar("Valores inválidos que 'contradicen'", [("luces", "morado"), ("luces", "debil")],
           lambda r, i: i == [] and r["estado"] != "inconsistente")
    probar("Mayúsculas en el conflicto", [("Luces", "Debil"), ("luces", "normal")],
           lambda r, i: [x["id"] for x in i] == ["c00"])
    probar("Términos extraños", "[foo, obs(a,b,c), 42, obs(luces), obs(luces, debil)]",
           lambda r, i: len(r["invalidas"]) == 4 and i == [])
    probar("Voltaje fuera de rango (99 V)", [("voltaje", 99), ("tablero", "si")],
           lambda r, i: i == [] and len(r["invalidas"]) == 1)
    probar("La misma respuesta 200 veces", [("luces", "debil")] * 200, lambda r, i: i == [])
    enorme = [("luces", "debil"), ("giro_arranque", "lento")] * 250 + [("luces", "normal")]
    probar("500 observaciones + 1 contradicción al final", enorme,
           lambda r, i: [x["id"] for x in i] == ["c00"] and r["estado"] == "inconsistente")
    todas = [(v, "si") for v in ("clic_arranque", "falla_intermitente", "se_apaga_ralenti",
                                 "ralenti_inestable", "tirones", "perdida_potencia",
                                 "sobrecalentamiento", "ruidos_anormales", "olor_gasolina",
                                 "fuga_combustible", "vacios_aceleracion", "combustible_viejo")]
    todas += [("dificultad_arranque", "no"), ("giro_arranque", "no_gira"), ("interruptor_paro", "paro"),
              ("nivel_combustible", "vacio"), ("fusible", "fundido"), ("tablero", "si"),
              ("luces", "normal"), ("voltaje", 3.0)]
    probar("Todas las contradicciones a la vez", todas,
           lambda r, i: {"c01", "c02", "c03", "c04", "c05", "c07", "c08"} <= {x["id"] for x in i}
           and all(x["tipo"] == "alerta" for x in r["resultados"]))
    return resultados


def e5_lenguaje_natural(motor):
    """Contradicciones dentro de una descripción, y textos largos o raros."""
    frases = [
        ("Mi moto arranca bien pero a veces no arranca", True),
        ("Las luces están débiles y las luces están normales", True),
        ("El motor no gira. Después el motor gira lento", True),
        ("No huele a gasolina, pero huele a gasolina", True),
        ("El filtro de aire está sucio y el filtro de aire está limpio", True),
        ("El motor no gira y la moto arranca bien", True),          # C01 entre variables distintas
        ("Las luces están débiles, las luces están débiles", False),  # repetición, no contradicción
        ("Mi moto de 150 cc no arranca, el motor gira lento y las luces están débiles", False),
        ("Quisiera saber el precio de una llanta", False),
    ]
    resultados = []
    for texto, contradice in frases:
        i = medir("interpretar_texto/4", motor.interpretar, texto)
        r = motor.consultar(i["observaciones"])
        bloqueado = r["estado"] == "inconsistente"
        resultados.append({"texto": texto, "esperado_bloqueo": contradice, "bloqueado": bloqueado,
                           "ok": bloqueado == contradice})
    largo = ("el motor gira lento y las luces están débiles, " * 400) + "pero las luces están normales"
    inicio = time.perf_counter()
    i = motor.interpretar(largo)
    ms = (time.perf_counter() - inicio) * 1000
    r = motor.consultar(i["observaciones"])
    resultados.append({"texto": f"Texto de {len(largo.split())} palabras con la contradicción al final",
                       "esperado_bloqueo": True, "bloqueado": r["estado"] == "inconsistente",
                       "ok": r["estado"] == "inconsistente", "ms": round(ms, 1)})
    raro = "¡¡¡ 🏍️ mi moto ### no arranca ??? ñandú 12,3,4 V ;;; \n\t luces débiles !!!"
    try:
        i = motor.interpretar(raro)
        ok = isinstance(i["observaciones"], list)
    except ErrorMotor:
        ok = False
    resultados.append({"texto": "Texto con emojis, símbolos y números mal formados",
                       "esperado_bloqueo": False, "bloqueado": False, "ok": ok})
    return resultados


def latencias():
    filas = {}
    for nombre, valores in TIEMPOS.items():
        ordenados = sorted(valores)
        filas[nombre] = {"llamadas": len(valores), "media_ms": round(statistics.mean(valores), 2),
                         "p95_ms": round(ordenados[int(len(ordenados) * 0.95) - 1], 2),
                         "max_ms": round(max(valores), 2)}
    return filas


# ---------------------------------------------------------------------------
def main() -> int:
    escribir(f"MotoExpert - Pruebas de estrés del manejo de contradicciones ({datetime.now():%Y-%m-%d %H:%M})")
    escribir(f"Semilla aleatoria: {SEMILLA}. Base: copia con el conocimiento aprendido vacío.")
    escribir()
    motor = MotorMotoExpert(copia_de_prueba())
    oraculo = Oraculo(motor)
    valores = valores_categoricos(motor.catalogo())
    rnd = random.Random(SEMILLA)
    inicio = time.perf_counter()

    e1 = e1_barrido_exhaustivo(motor, oraculo, valores)
    escribir("E1. Barrido exhaustivo de pares de respuestas")
    escribir(f"    {e1['pares']} pares evaluados; {e1['pares_incompatibles']} incompatibles; "
             f"{e1['subconjuntos_C06']} subconjuntos de C06; {e1['barrido_voltaje']} combinaciones de voltaje.")
    escribir(f"    Discrepancias con el oráculo: {e1['discrepancias']} {e1['ejemplos_error'] or ''}")
    escribir()

    e2 = e2_e3_aleatorios(motor, oraculo, valores, rnd)
    escribir(f"E2/E3. {e2['casos']} casos aleatorios ({e2['inconsistentes']} incompatibles, "
             f"{e2['coherentes']} coherentes)")
    for clave in ("falsos_negativos", "falsos_positivos", "diagnosticos_con_datos_incompatibles",
                  "alertas_perdidas", "que_falta_incorrecto", "entrevista_incorrecta", "excepciones"):
        escribir(f"    {clave.replace('_', ' ')}: {e2[clave]}")
    if e2["ejemplos_error"]:
        escribir(f"    Ejemplos: {e2['ejemplos_error']}")
    escribir()

    e4 = e4_entradas_hostiles(motor)
    escribir("E4. Entradas hostiles")
    for x in e4:
        escribir(f"    [{'OK' if x['ok'] else 'FALLA'}] {x['prueba']} -> {x['obtenido']} ({x['ms']} ms)")
    escribir()

    e5 = e5_lenguaje_natural(motor)
    escribir("E5. Contradicciones en lenguaje natural")
    for x in e5:
        extra = f" ({x['ms']} ms)" if "ms" in x else ""
        escribir(f"    [{'OK' if x['ok'] else 'FALLA'}] «{x['texto'][:70]}» -> bloqueado={x['bloqueado']}{extra}")
    escribir()

    duracion = time.perf_counter() - inicio
    lat = latencias()
    escribir("E6. Latencia por predicado (ms)")
    for nombre, d in lat.items():
        escribir(f"    {nombre:22} llamadas={d['llamadas']:6}  media={d['media_ms']:7}  "
                 f"p95={d['p95_ms']:7}  máx={d['max_ms']:7}")
    total_llamadas = sum(d["llamadas"] for d in lat.values())
    escribir(f"    Duración total: {duracion:.1f} s; {total_llamadas} consultas medidas.")
    escribir()

    aprobado = (e1["discrepancias"] == 0
                and all(e2[k] == 0 for k in ("falsos_negativos", "falsos_positivos",
                                             "diagnosticos_con_datos_incompatibles", "alertas_perdidas",
                                             "que_falta_incorrecto", "entrevista_incorrecta", "excepciones"))
                and all(x["ok"] for x in e4) and all(x["ok"] for x in e5))
    escribir("=" * 78)
    escribir(f"RESULTADO: {'APROBADO' if aprobado else 'CON FALLAS'}")
    escribir("=" * 78)

    with open(RUTA_EVIDENCIA, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(SALIDA) + "\n")
    with open(RUTA_RESUMEN, "w", encoding="utf-8") as archivo:
        json.dump({"fecha": f"{datetime.now():%Y-%m-%d %H:%M}", "semilla": SEMILLA,
                   "e1": e1, "e2": e2, "e4": e4, "e5": e5, "latencias": lat,
                   "duracion_s": round(duracion, 1), "aprobado": aprobado},
                  archivo, ensure_ascii=False, indent=1, default=str)
    return 0 if aprobado else 1


if __name__ == "__main__":
    sys.exit(main())
