"""
clasificador.py - Pre-procesamiento numérico de MotoExpert (parte opcional
del entregable 3, componente híbrido).

Convierte mediciones continuas del mundo real en hechos discretos que la
base de conocimiento ya sabe usar, ANTES de enviarlos a Prolog:

    temperatura del aceite del motor (°C) -> sobrecalentamiento: si / no
    días sin usar la motocicleta          -> tiempo_sin_uso: dias / semanas / meses

Cada conversión es un árbol de decisión de scikit-learn entrenado con una
tabla de referencia. El árbol aprende los umbrales a partir de los ejemplos
etiquetados (por ejemplo, entre 110 °C "no" y 125 °C "si" aprende 117,5 °C),
y el resultado se envía a Prolog como cualquier otra observación.

Si scikit-learn no está instalado, se usa la misma tabla con una heurística:
el umbral es el punto medio entre dos ejemplos consecutivos con distinta
etiqueta, que es exactamente lo que aprende un árbol de una sola variable.

Python solo transforma el dato; el razonamiento sigue en Prolog.

Autor: Bredman Estiven Velez Cortez
"""

from __future__ import annotations

try:
    from sklearn.tree import DecisionTreeClassifier
except ImportError:  # el sistema funciona igual sin la dependencia opcional
    DecisionTreeClassifier = None

# Tablas de referencia (valor, etiqueta).
# Temperatura del aceite en motos de 4 tiempos refrigeradas por aire: el
# funcionamiento normal ronda 70-110 °C y por encima de unos 120 °C el aceite
# pierde capacidad de lubricar. Valores de referencia general, PENDIENTES de
# validar con el manual de servicio, igual que el umbral de 12,4 V.
REFERENCIA_TEMPERATURA = [
    (40, "no"), (60, "no"), (70, "no"), (80, "no"), (90, "no"), (100, "no"), (110, "no"),
    (125, "si"), (130, "si"), (140, "si"), (150, "si"), (170, "si"),
]
# Días sin uso: menos de una semana, menos de un mes o un mes o más.
REFERENCIA_DIAS = [
    (0, "dias"), (1, "dias"), (3, "dias"), (6, "dias"),
    (7, "semanas"), (14, "semanas"), (21, "semanas"), (29, "semanas"),
    (30, "meses"), (60, "meses"), (90, "meses"), (180, "meses"), (365, "meses"),
]


class ClasificadorMedicion:
    """Convierte una medición continua en una etiqueta discreta."""

    def __init__(self, variable: str, nombre: str, unidad: str,
                 referencia: list[tuple[float, str]], rango: tuple[float, float]) -> None:
        self.variable = variable
        self.nombre = nombre
        self.unidad = unidad
        self.rango = rango
        self.referencia = sorted(referencia)
        if DecisionTreeClassifier is not None:
            # Un nivel de profundidad por cada umbral necesario.
            niveles = len({etiqueta for _, etiqueta in referencia}) - 1
            self.modelo = DecisionTreeClassifier(max_depth=max(1, niveles), random_state=0)
            self.modelo.fit([[v] for v, _ in self.referencia], [e for _, e in self.referencia])
            self.metodo = "árbol de decisión (scikit-learn)"
        else:
            self.modelo = None
            self.metodo = "umbrales de la tabla de referencia"

    def umbrales(self) -> list[float]:
        """Umbrales que separan las etiquetas (aprendidos por el árbol o calculados)."""
        if self.modelo is not None:
            arbol = self.modelo.tree_
            return sorted(float(u) for u, f in zip(arbol.threshold, arbol.feature) if f >= 0)
        return [(a + b) / 2 for (a, ea), (b, eb) in zip(self.referencia, self.referencia[1:]) if ea != eb]

    def clasificar(self, valor: float) -> str:
        if self.modelo is not None:
            return str(self.modelo.predict([[valor]])[0])
        etiqueta = self.referencia[0][1]
        for v, e in self.referencia:
            if valor >= v:
                etiqueta = e
        return etiqueta

    def valido(self, valor: float) -> bool:
        return self.rango[0] <= valor <= self.rango[1]


CLASIFICADORES = {
    "temperatura": ClasificadorMedicion(
        "sobrecalentamiento", "Temperatura del aceite del motor", "°C", REFERENCIA_TEMPERATURA, (0, 250)),
    "dias_sin_uso": ClasificadorMedicion(
        "tiempo_sin_uso", "Días sin usar la motocicleta", "días", REFERENCIA_DIAS, (0, 3650)),
}


def convertir_mediciones(mediciones: dict[str, float | None]) -> tuple[list[tuple[str, str]], list[dict]]:
    """
    Convierte las mediciones presentes en observaciones discretas.

    Devuelve (observaciones, detalle): observaciones listas para Prolog, como
    [("sobrecalentamiento", "si")], y el detalle de cada conversión para
    mostrarlo al usuario (valor, etiqueta, umbrales y método).
    """
    observaciones, detalle = [], []
    for clave, valor in mediciones.items():
        clasificador = CLASIFICADORES.get(clave)
        if clasificador is None or valor is None:
            continue
        if not clasificador.valido(valor):
            detalle.append({"nombre": clasificador.nombre, "valor": valor, "unidad": clasificador.unidad,
                            "error": f"fuera del rango {clasificador.rango[0]:g}–{clasificador.rango[1]:g}"})
            continue
        etiqueta = clasificador.clasificar(valor)
        observaciones.append((clasificador.variable, etiqueta))
        detalle.append({"nombre": clasificador.nombre, "valor": valor, "unidad": clasificador.unidad,
                        "variable": clasificador.variable, "etiqueta": etiqueta,
                        "umbrales": clasificador.umbrales(), "metodo": clasificador.metodo})
    return observaciones, detalle
