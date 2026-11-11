"""
motor.py - Puente entre Python y el motor de inferencia de MotoExpert.

Responsabilidad de este módulo (y solo esta):
  1. Cargar base_conocimiento.pl en SWI-Prolog mediante PySwip.
  2. Limpiar la captura (espacios, mayúsculas, coma decimal) y convertir
     las observaciones a una lista de Prolog [obs(Variable, Valor), ...]
     SIN validarlas ni interpretarlas.
  3. Invocar los predicados públicos de Prolog y devolver sus resultados
     como estructuras de Python (listas y diccionarios).
  4. Dar formato de texto a los resultados para la consola.

Toda la lógica (validación de la lista, inferencia, descarte, exclusión,
respaldo, prioridad, selección de preguntas, traza de explicación y
sugerencia de datos faltantes) reside en Prolog.

Autor: Bredman Estiven Velez Cortez
Requisitos: SWI-Prolog 9.x y PySwip (pip install pyswip)
"""

from __future__ import annotations

import os
import textwrap
from typing import Any, Iterable

from pyswip import Prolog

RUTA_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "base_conocimiento.pl")

# Nombres de los campos de cada resultado, en el mismo orden en que los
# devuelve el predicado conclusion/2 (ver Diccionario de Predicados).
CAMPOS_RESULTADO = [
    "tipo", "codigo", "nombre", "subsistema", "respaldo",
    "justificacion_respaldo", "prioridad", "etiqueta_prioridad",
    "accion_prioridad", "evidencias", "evidencias_en_contra",
    "razones_prioridad", "recomendaciones", "avisos", "coincidencia",
]

TITULO_TIPO = {
    "alerta": "ALERTA DE SEGURIDAD",
    "basica": "VERIFICACIÓN BÁSICA",
    "diagnostico": "DIAGNÓSTICO PRELIMINAR",
}


class ErrorMotor(Exception):
    """Error al comunicarse con el motor de Prolog."""


# ---------------------------------------------------------------------------
# Conversión Python -> texto de Prolog (sin lógica de dominio)
# ---------------------------------------------------------------------------
def _atomo(texto: str) -> str:
    """Escribe un texto como átomo de Prolog entre comillas simples."""
    limpio = (str(texto).replace("\\", "\\\\").replace("'", "\\'")
              .replace("\r", " ").replace("\n", " ").replace("\t", " "))
    return f"'{limpio}'"


def _lista_condiciones(condiciones: Iterable[tuple[str, Any]]) -> str:
    """[(variable, valor), ...] -> texto de Prolog [variable-valor, ...]."""
    return "[" + ", ".join(f"{_atomo(v)}-{_termino_valor(x)}" for v, x in condiciones) + "]"


def _lista_atomos(textos: Iterable[str]) -> str:
    return "[" + ", ".join(_atomo(t) for t in textos) + "]"


def _termino_ficha(ficha: dict) -> str:
    """Ficha de diagnóstico como término ficha/9 de Prolog."""
    return (f"ficha({_atomo(ficha['nombre'])}, {_atomo(ficha['subsistema'])}, "
            f"{_atomo(ficha['rama'])}, {int(ficha['prioridad'])}, "
            f"{_lista_condiciones(ficha['evidencias'])}, "
            f"{_lista_condiciones(ficha['verificaciones'])}, "
            f"{_lista_condiciones(ficha['descartes'])}, "
            f"{_lista_atomos(ficha['competidoras'])}, "
            f"{_lista_atomos(ficha['recomendaciones'])})")


def _termino_pregunta(pregunta: dict) -> str:
    """Pregunta nueva como término pregunta/6 de Prolog."""
    frases = "[" + ", ".join(f"{_atomo(o)}-{_atomo(f)}" for o, f in pregunta["frases"]) + "]"
    return (f"pregunta({_atomo(pregunta['etiqueta'])}, {_atomo(pregunta['texto'])}, "
            f"{_atomo(pregunta['grupo'])}, {_atomo(pregunta['tipo'])}, "
            f"{_lista_atomos(pregunta['opciones'])}, {frases})")


def _termino_valor(valor: Any) -> str:
    """Números se envían como números; todo lo demás, como átomo."""
    if isinstance(valor, bool):
        return _atomo(str(valor).lower())
    if isinstance(valor, (int, float)):
        return repr(valor)
    return _atomo(valor)


def limpiar_valor(valor: Any) -> Any:
    """
    Limpieza de captura: recorta espacios, pasa a minúscula y convierte
    a número los textos numéricos ("11,5" -> 11.5). Devuelve None si el
    valor quedó vacío. No decide si el valor es admitido: eso lo hace Prolog.
    """
    if valor is None or isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return int(valor) if float(valor).is_integer() else valor
    texto = str(valor).strip().lower()
    if not texto:
        return None
    try:
        numero = float(texto.replace(",", "."))
    except ValueError:
        return texto
    return int(numero) if numero.is_integer() else numero


def limpiar_observaciones(observaciones: dict | Iterable[tuple[str, Any]]) -> list[tuple[str, Any]]:
    """Aplica limpiar_valor() a cada par y omite los que quedaron vacíos."""
    pares = observaciones.items() if isinstance(observaciones, dict) else observaciones
    limpias = []
    for var, val in pares:
        var_limpia = str(var).strip().lower()
        val_limpio = limpiar_valor(val)
        if var_limpia and val_limpio is not None:
            limpias.append((var_limpia, val_limpio))
    return limpias


def lista_observaciones(observaciones: dict | Iterable[tuple[str, Any]]) -> str:
    """
    Convierte las observaciones en el texto de una lista de Prolog.

    Acepta un diccionario {variable: valor} o una secuencia de pares
    (variable, valor). La secuencia permite enviar repetidos o datos
    erróneos a propósito, para probar la validación que hace Prolog.
    """
    pares = observaciones.items() if isinstance(observaciones, dict) else observaciones
    terminos = [f"obs({_atomo(var)}, {_termino_valor(val)})" for var, val in pares]
    return "[" + ", ".join(terminos) + "]"


def _valor_python(valor) -> Any:
    """Valor devuelto por PySwip (átomo, número o cadena) como str o número."""
    if isinstance(valor, (int, float)):
        return valor
    return valor.decode("utf-8") if isinstance(valor, bytes) else str(valor)


def _paso(paso) -> dict:
    """Paso de la traza [Profundidad, IdRegla, Texto] como diccionario."""
    nivel, regla, texto = paso
    return {"nivel": nivel, "regla": regla, "texto": texto}


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------
class MotorMotoExpert:
    """Carga la base de conocimiento y expone las consultas a Prolog."""

    def __init__(self, ruta_base: str = RUTA_BASE) -> None:
        if not os.path.exists(ruta_base):
            raise ErrorMotor(f"No se encontró la base de conocimiento: {ruta_base}")
        self.prolog = Prolog()
        # consult/1 con ruta en formato Prolog (barras normales)
        self.prolog.consult(ruta_base.replace("\\", "/"))
        self.ultima_consulta = ""

    # -- utilidades internas ------------------------------------------------
    def _consultar_uno(self, consulta: str) -> dict | None:
        """Ejecuta una consulta y devuelve la primera solución (o None)."""
        self.ultima_consulta = consulta
        try:
            soluciones = list(self.prolog.query(consulta, maxresult=1))
        except Exception as exc:  # PySwip lanza PrologError u otras excepciones
            raise ErrorMotor(f"Error al ejecutar {consulta!r}: {exc}") from exc
        return soluciones[0] if soluciones else None

    @staticmethod
    def _texto_lista(observaciones) -> str:
        """Admite observaciones ya escritas como texto de Prolog (pruebas)."""
        if isinstance(observaciones, str):
            return observaciones
        return lista_observaciones(observaciones)

    # -- predicados públicos ------------------------------------------------
    def consultar(self, observaciones) -> dict:
        """Invoca consultar/6: estado, resultados, descartadas e inválidas."""
        lista = self._texto_lista(observaciones)
        sol = self._consultar_uno(f"consultar({lista}, E, M, R, D, I)")
        if sol is None:
            raise ErrorMotor("consultar/6 no devolvió solución.")
        return {
            "consulta": self.ultima_consulta,
            "estado": sol["E"],
            "mensaje": sol["M"],
            "resultados": [dict(zip(CAMPOS_RESULTADO, r)) for r in sol["R"]],
            "descartadas": [
                {"codigo": c, "nombre": n, "motivo": m} for c, n, m in sol["D"]
            ],
            "invalidas": list(sol["I"]),
        }

    def diagnosticar_todos(self, observaciones) -> list[dict]:
        """Invoca diagnosticar_todos/2 (recolección con setof/3)."""
        lista = self._texto_lista(observaciones)
        sol = self._consultar_uno(f"diagnosticar_todos({lista}, R)")
        return [dict(zip(CAMPOS_RESULTADO, r)) for r in sol["R"]] if sol else []

    def codigos(self, observaciones) -> list[str]:
        """Invoca codigos_diagnostico/2: solo códigos, sin duplicados."""
        lista = self._texto_lista(observaciones)
        sol = self._consultar_uno(f"codigos_diagnostico({lista}, C)")
        return list(sol["C"]) if sol else []

    def siguiente_pregunta(self, observaciones) -> str | None:
        """Invoca siguiente_pregunta/2. Devuelve None cuando Prolog responde 'fin'."""
        lista = self._texto_lista(observaciones)
        sol = self._consultar_uno(f"siguiente_pregunta({lista}, V)")
        if sol is None or sol["V"] == "fin":
            return None
        return sol["V"]

    def info_pregunta(self, variable: str) -> dict:
        """Invoca info_pregunta/4: texto, opciones y tipo de entrada."""
        sol = self._consultar_uno(f"info_pregunta({_atomo(variable)}, T, O, K)")
        if sol is None:
            raise ErrorMotor(f"Variable desconocida: {variable}")
        return {"texto": sol["T"], "opciones": list(sol["O"]), "tipo": sol["K"]}

    def por_que(self, observaciones, variable: str) -> str:
        """Invoca por_que_pregunta/3: explicación de por qué se hace la pregunta."""
        lista = self._texto_lista(observaciones)
        sol = self._consultar_uno(f"por_que_pregunta({lista}, {_atomo(variable)}, M)")
        return sol["M"] if sol else ""

    def alertas_activas(self, observaciones) -> list[dict]:
        """Invoca alertas_activas/2 para avisar de inmediato durante la entrevista."""
        lista = self._texto_lista(observaciones)
        sol = self._consultar_uno(f"alertas_activas({lista}, A)")
        return [{"codigo": c, "nombre": n} for c, n in sol["A"]] if sol else []

    def catalogo(self) -> list[dict]:
        """Invoca catalogo_variables/1: variables, grupos y opciones legibles."""
        sol = self._consultar_uno("catalogo_variables(V)")
        if sol is None:
            raise ErrorMotor("catalogo_variables/1 no devolvió solución.")
        return [
            {"variable": v, "grupo": g, "nombre_grupo": ng, "tipo": t,
             "etiqueta": e, "pregunta": p, "entrada": k,
             "opciones": [{"valor": x, "texto": xt} for x, xt in ops]}
            for v, g, ng, t, e, p, ops, k in sol["V"]
        ]

    def explicar(self, observaciones) -> dict:
        """Invoca explicar_consulta/5: módulo de explicabilidad "¿Por qué?"."""
        lista = self._texto_lista(observaciones)
        sol = self._consultar_uno(f"explicar_consulta({lista}, G, C, H, A)")
        if sol is None:
            raise ErrorMotor("explicar_consulta/5 no devolvió solución.")
        return {
            "consulta": self.ultima_consulta,
            "general": [_paso(p) for p in sol["G"]],
            "conclusiones": [
                {"tipo": t, "codigo": c, "nombre": n, "pasos": [_paso(p) for p in ps]}
                for t, c, n, ps in sol["C"]
            ],
            "hechos": [{"hecho": h, "usos": list(u)} for h, u in sol["H"]],
            "alternativas": [
                {"codigo": c, "nombre": n, "tipo": t,
                 "compartidos": list(s), "motivo": m}
                for c, n, t, s, m in sol["A"]
            ],
        }

    def que_falta(self, observaciones) -> dict:
        """Invoca que_falta/5: módulo de recomendación "¿Qué falta?"."""
        lista = self._texto_lista(observaciones)
        sol = self._consultar_uno(f"que_falta({lista}, S, M, E, G)")
        if sol is None:
            raise ErrorMotor("que_falta/5 no devolvió solución.")
        return {
            "consulta": self.ultima_consulta,
            "situacion": sol["S"],
            "mensaje": sol["M"],
            "evaluadas": [{"codigo": c, "nombre": n, "respaldo": r}
                          for c, n, r in sol["E"]],
            "sugerencias": [
                {"variable": v, "etiqueta": e, "pregunta": p, "peso": w,
                 "prioridad": pr, "tipo": t, "efectos": list(ef)}
                for v, e, p, w, pr, t, ef in sol["G"]
            ],
        }

    # -- entregable 3: lenguaje natural ----------------------------------
    def interpretar(self, texto: str) -> dict:
        """Invoca interpretar_texto/4: la DCG convierte la descripción en observaciones."""
        sol = self._consultar_uno(f"interpretar_texto({_atomo(texto)}, O, R, N)")
        if sol is None:
            raise ErrorMotor("interpretar_texto/4 no devolvió solución.")
        reconocidos = [
            {"variable": v, "valor": _valor_python(x), "frase": f, "texto": t, "estado": e}
            for v, x, f, t, e in sol["R"]
        ]
        return {
            "consulta": self.ultima_consulta,
            # Las mismas observaciones que Prolog devuelve como obs(V, X): las
            # que quedaron en estado "aceptado" (PySwip entrega obs/2 como texto).
            "observaciones": [(r["variable"], r["valor"]) for r in reconocidos
                              if r["estado"] == "aceptado"],
            "reconocidos": reconocidos,
            "no_reconocidas": list(sol["N"]),
        }

    # -- entregable 3: modo experto -------------------------------------
    def condiciones_posibles(self) -> list[dict]:
        """Invoca condiciones_posibles/1: pares variable-valor para una ficha."""
        sol = self._consultar_uno("condiciones_posibles(L)")
        return [{"variable": v, "valor": _valor_python(x), "texto": t} for v, x, t in sol["L"]] if sol else []

    def catalogo_diagnosticos(self) -> list[dict]:
        """Invoca catalogo_diagnosticos/1: todos los diagnósticos, base y aprendidos."""
        sol = self._consultar_uno("catalogo_diagnosticos(L)")
        return [{"codigo": c, "nombre": n, "rama": r, "aprendido": a == "si"}
                for c, n, r, a in sol["L"]] if sol else []

    def aprender(self, ficha: dict) -> dict:
        """
        Invoca aprender_diagnostico/4. Prolog valida la ficha, inyecta los
        hechos con assertz/1 y los guarda en conocimiento_aprendido.pl.
        """
        sol = self._consultar_uno(f"aprender_diagnostico({_termino_ficha(ficha)}, E, C, Errores)")
        if sol is None:
            raise ErrorMotor("aprender_diagnostico/4 no devolvió solución.")
        return {"estado": sol["E"], "codigo": sol["C"], "errores": list(sol["Errores"])}

    def datos_diagnostico(self, codigo: str) -> dict | None:
        """Invoca datos_diagnostico/2: la ficha actual, para el formulario de edición."""
        sol = self._consultar_uno(f"datos_diagnostico({_atomo(codigo)}, D)")
        if sol is None:
            return None
        n, s, r, p, ev, vf, de, comp, recs = sol["D"]
        par = lambda c: (str(c[0]), _valor_python(c[1]))  # noqa: E731
        return {"nombre": n, "subsistema": s, "rama": r, "prioridad": p,
                "evidencias": [par(c) for c in ev], "verificaciones": [par(c) for c in vf],
                "descartes": [par(c) for c in de], "competidoras": list(comp),
                "recomendaciones": list(recs)}

    def editar_diagnostico(self, codigo: str, ficha: dict) -> dict:
        """
        Invoca editar_diagnostico/4. Si hay errores, Prolog no cambia nada y
        los devuelve; si no, reemplaza la ficha conservando el código.
        """
        sol = self._consultar_uno(
            f"editar_diagnostico({_atomo(codigo)}, {_termino_ficha(ficha)}, E, Errores)")
        if sol is None:
            raise ErrorMotor("editar_diagnostico/4 no devolvió solución.")
        return {"estado": sol["E"], "errores": list(sol["Errores"])}

    def olvidar(self, codigo: str) -> dict:
        """Invoca olvidar_diagnostico/3: retira un diagnóstico aprendido (retract/1)."""
        sol = self._consultar_uno(f"olvidar_diagnostico({_atomo(codigo)}, E, Errores)")
        if sol is None:
            raise ErrorMotor("olvidar_diagnostico/3 no devolvió solución.")
        return {"estado": sol["E"], "errores": list(sol["Errores"])}

    def aprendidos(self) -> list[dict]:
        """Invoca diagnosticos_aprendidos/1."""
        sol = self._consultar_uno("diagnosticos_aprendidos(L)")
        return [
            {"codigo": c, "nombre": n, "subsistema": s, "rama": r, "prioridad": p,
             "fecha": f, "evidencias": list(ev), "recomendaciones": list(rec)}
            for c, n, s, r, p, f, ev, rec in sol["L"]
        ] if sol else []

    def aprender_pregunta(self, pregunta: dict) -> dict:
        """
        Invoca aprender_pregunta/4: una pregunta nueva con sus opciones y las
        frases con que la reconoce la gramática DCG.
        """
        sol = self._consultar_uno(f"aprender_pregunta({_termino_pregunta(pregunta)}, E, V, Errores)")
        if sol is None:
            raise ErrorMotor("aprender_pregunta/4 no devolvió solución.")
        return {"estado": sol["E"], "variable": sol["V"], "errores": list(sol["Errores"])}

    def datos_pregunta(self, variable: str) -> dict | None:
        """Invoca datos_pregunta/2: la pregunta actual, para el formulario de edición."""
        sol = self._consultar_uno(f"datos_pregunta({_atomo(variable)}, D)")
        if sol is None:
            return None
        e, t, g, tipo, respuestas, frases = sol["D"]
        return {"etiqueta": e, "texto": t, "grupo": g, "tipo": tipo,
                "opciones": list(respuestas), "frases": [(str(o), str(f)) for o, f in frases]}

    def editar_pregunta(self, variable: str, pregunta: dict) -> dict:
        """
        Invoca editar_pregunta/4. Si hay errores, Prolog no cambia nada y los
        devuelve; si no, reemplaza la pregunta conservando su identificador.
        """
        sol = self._consultar_uno(
            f"editar_pregunta({_atomo(variable)}, {_termino_pregunta(pregunta)}, E, Errores)")
        if sol is None:
            raise ErrorMotor("editar_pregunta/4 no devolvió solución.")
        return {"estado": sol["E"], "errores": list(sol["Errores"])}

    def olvidar_pregunta(self, variable: str) -> dict:
        """Invoca olvidar_pregunta/3."""
        sol = self._consultar_uno(f"olvidar_pregunta({_atomo(variable)}, E, Errores)")
        if sol is None:
            raise ErrorMotor("olvidar_pregunta/3 no devolvió solución.")
        return {"estado": sol["E"], "errores": list(sol["Errores"])}

    def preguntas_aprendidas(self) -> list[dict]:
        """Invoca preguntas_aprendidas/1."""
        sol = self._consultar_uno("preguntas_aprendidas(L)")
        return [
            {"variable": v, "etiqueta": e, "pregunta": p, "grupo": g, "tipo": t,
             "opciones": list(ops), "frases": list(fr), "fecha": f, "en_uso": uso == "si"}
            for v, e, p, g, t, ops, fr, f, uso in sol["L"]
        ] if sol else []

    def grupos(self) -> list[dict]:
        """Invoca grupos_preguntas/1."""
        sol = self._consultar_uno("grupos_preguntas(L)")
        return [{"grupo": g, "nombre": n} for g, n in sol["L"]] if sol else []

    def aprender_regla(self, codigo: str, tipo: str, variable: str, valor) -> dict:
        """Invoca aprender_regla/4: una regla nueva sobre un diagnóstico existente."""
        regla = f"regla({_atomo(codigo)}, {_atomo(tipo)}, {_atomo(variable)}-{_termino_valor(valor)})"
        sol = self._consultar_uno(f"aprender_regla({regla}, E, I, Errores)")
        if sol is None:
            raise ErrorMotor("aprender_regla/4 no devolvió solución.")
        return {"estado": sol["E"], "id": sol["I"], "errores": list(sol["Errores"])}

    def olvidar_regla(self, identificador: str) -> dict:
        """Invoca olvidar_regla/3."""
        sol = self._consultar_uno(f"olvidar_regla({_atomo(identificador)}, E, Errores)")
        if sol is None:
            raise ErrorMotor("olvidar_regla/3 no devolvió solución.")
        return {"estado": sol["E"], "errores": list(sol["Errores"])}

    def reglas_aprendidas(self) -> list[dict]:
        """Invoca reglas_aprendidas/1."""
        sol = self._consultar_uno("reglas_aprendidas(L)")
        return [{"id": i, "codigo": c, "nombre": n, "texto": t, "fecha": f}
                for i, c, n, t, f in sol["L"]] if sol else []

    def ruta_aprendido(self) -> str:
        """Ruta de conocimiento_aprendido.pl, según Prolog."""
        sol = self._consultar_uno("ruta_aprendido(R)")
        return str(sol["R"]) if sol else ""

    def consulta_libre(self, consulta: str) -> list[dict]:
        """Ejecuta cualquier consulta (uso en pruebas). Devuelve todas las soluciones."""
        self.ultima_consulta = consulta
        try:
            return list(self.prolog.query(consulta))
        except Exception as exc:
            raise ErrorMotor(f"Error al ejecutar {consulta!r}: {exc}") from exc


# ---------------------------------------------------------------------------
# Presentación en consola
# ---------------------------------------------------------------------------
def _envolver(texto: str, sangria: str = "      ") -> str:
    return textwrap.fill(texto, width=78, initial_indent=sangria,
                         subsequent_indent=sangria)


def formatear_reporte(respuesta: dict) -> str:
    """Convierte la respuesta de consultar() en un reporte legible."""
    lineas = ["=" * 78, " REPORTE MOTOEXPERT", "=" * 78]
    lineas.append(f" Estado: {respuesta['estado']}")
    lineas.append(_envolver(respuesta["mensaje"], " "))

    if respuesta["invalidas"]:
        lineas.append("")
        lineas.append(" Datos ignorados por no ser válidos:")
        for inv in respuesta["invalidas"]:
            lineas.append(f"   - {inv}")

    for i, r in enumerate(respuesta["resultados"], start=1):
        lineas.append("")
        lineas.append("-" * 78)
        lineas.append(f" {i}. [{TITULO_TIPO.get(r['tipo'], r['tipo'])}] "
                      f"{r['codigo'].upper()} - {r['nombre']}")
        lineas.append(f"    Subsistema: {r['subsistema']}")
        if r["tipo"] != "alerta":
            lineas.append(f"    Respaldo: {r['respaldo'].upper()}  ({r['coincidencia']})")
            lineas.append(_envolver(r["justificacion_respaldo"]))
        lineas.append(f"    Prioridad: {r['prioridad']} - {r['etiqueta_prioridad']}. "
                      f"{r['accion_prioridad']}")
        for razon in r["razones_prioridad"]:
            lineas.append(_envolver("· " + razon))
        lineas.append("    Evidencias a favor:")
        for ev in r["evidencias"]:
            lineas.append(_envolver("+ " + ev))
        if r["evidencias_en_contra"]:
            lineas.append("    Evidencias en contra:")
            for ev in r["evidencias_en_contra"]:
                lineas.append(_envolver("- " + ev))
        lineas.append("    Verificaciones y acciones seguras:")
        for rec in r["recomendaciones"]:
            lineas.append(_envolver("> " + rec))
        for aviso in r["avisos"]:
            lineas.append(_envolver("! " + aviso))

    if respuesta["descartadas"]:
        lineas.append("")
        lineas.append("-" * 78)
        lineas.append(" Hipótesis descartadas o excluidas:")
        for d in respuesta["descartadas"]:
            lineas.append(f"   {d['codigo'].upper()} - {d['nombre']}")
            lineas.append(_envolver(d["motivo"]))
    lineas.append("=" * 78)
    return "\n".join(lineas)


def _lineas_pasos(pasos: list[dict]) -> list[str]:
    """Árbol de reglas con sangría según la profundidad del paso."""
    return [textwrap.fill(f"[{p['regla']}] {p['texto']}", width=78,
                          initial_indent="   " + "   " * p["nivel"],
                          subsequent_indent="   " + "   " * p["nivel"] + "  ")
            for p in pasos]


def formatear_explicacion(explicacion: dict) -> str:
    """Convierte la respuesta de explicar() en texto para la consola."""
    lineas = ["=" * 78, " ¿POR QUÉ? - TRAZA DE INFERENCIA", "=" * 78,
              " Razonamiento común:"]
    lineas += _lineas_pasos(explicacion["general"])
    for c in explicacion["conclusiones"]:
        lineas.append("")
        lineas.append(f" Reglas disparadas para {c['codigo'].upper()} - {c['nombre']}:")
        lineas += _lineas_pasos(c["pasos"])
    lineas.append("")
    lineas.append(" Hechos comprobados como verdaderos:")
    for h in explicacion["hechos"]:
        usos = "; ".join(h["usos"]) if h["usos"] else "sin reglas asociadas"
        lineas.append(_envolver(f"+ {h['hecho']}  <- {usos}", "   "))
    lineas.append("")
    lineas.append(" Hipótesis alternativas descartadas:")
    if not explicacion["alternativas"]:
        lineas.append("   (ninguna)")
    for a in explicacion["alternativas"]:
        lineas.append(f"   {a['codigo'].upper()} - {a['nombre']} [{a['tipo']}]")
        if a["compartidos"]:
            lineas.append(_envolver("Síntomas compartidos: " + "; ".join(a["compartidos"])))
        lineas.append(_envolver(a["motivo"]))
    lineas.append("=" * 78)
    return "\n".join(lineas)


def formatear_que_falta(falta: dict) -> str:
    """Convierte la respuesta de que_falta() en texto para la consola."""
    lineas = ["=" * 78, " ¿QUÉ FALTA? - DATOS SUGERIDOS", "=" * 78,
              f" Situación: {falta['situacion']}", _envolver(falta["mensaje"], " ")]
    if falta["evaluadas"]:
        lineas.append(" Hipótesis evaluadas: " + ", ".join(
            f"{e['codigo'].upper()} ({e['respaldo']})" for e in falta["evaluadas"]))
    for i, s in enumerate(falta["sugerencias"], start=1):
        lineas.append("")
        lineas.append(f" {i}. {s['etiqueta']} (peso {s['peso']}, prioridad {s['prioridad']}, {s['tipo']})")
        lineas.append(_envolver(s["pregunta"]))
        for efecto in s["efectos"]:
            lineas.append(_envolver("· " + efecto))
    lineas.append("=" * 78)
    return "\n".join(lineas)
