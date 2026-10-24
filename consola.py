"""
consola.py - Consulta interactiva por consola de MotoExpert (entregable 1).

La interfaz principal es main.py (Streamlit). Esta versión se conserva
para usar el sistema sin navegador.

Prolog decide qué preguntar (siguiente_pregunta/2) y cuándo terminar.
Python solo muestra la pregunta, recibe la respuesta, la agrega a la
lista de observaciones y, al final, presenta el reporte, la traza
"¿Por qué?" y los datos sugeridos "¿Qué falta?".

Comandos durante la entrevista:
  número u opción  -> responder
  ?                -> ¿por qué me pregunta esto?
  terminar         -> finalizar y ver el reporte con lo respondido
  (Enter vacío)    -> responder 'desconocido'

Uso:  python consola.py

Autor: Bredman Estiven Velez Cortez
"""

from motor import (ErrorMotor, MotorMotoExpert, formatear_explicacion,
                   formatear_que_falta, formatear_reporte, limpiar_valor)

ENCABEZADO = """
==============================================================================
 MotoExpert - Diagnóstico preliminar de fallas en motocicletas
 Alcance: 100 a 250 cc, cuatro tiempos, carburador, sistema eléctrico de 12 V.
 Herramienta de orientación: no sustituye la evaluación de un profesional.
 Ingrese datos de pruebas técnicas solo si ya las realizó personal capacitado.
==============================================================================
"""


def leer_respuesta(motor: MotorMotoExpert, observaciones: list, variable: str):
    """Muestra una pregunta y devuelve el valor elegido, o None para terminar."""
    info = motor.info_pregunta(variable)
    print(f"\n{info['texto']}")
    if info["tipo"] == "numerico":
        print("   (escriba un número; Enter = desconocido; ? = por qué; terminar)")
    else:
        for i, opcion in enumerate(info["opciones"], start=1):
            print(f"   {i}. {opcion}")
        print("   (? = por qué; terminar)")

    while True:
        entrada = input("   > ").strip().lower()
        if entrada == "?":
            print("   Motivo:", motor.por_que(observaciones, variable))
            continue
        if entrada == "terminar":
            return None
        if entrada == "":
            return "desconocido"
        if info["tipo"] == "numerico":
            numero = limpiar_valor(entrada)
            if isinstance(numero, (int, float)):
                return numero
            print("   Escriba un número, Enter o 'terminar'.")
            continue
        if entrada.isdigit() and 1 <= int(entrada) <= len(info["opciones"]):
            return info["opciones"][int(entrada) - 1]
        if entrada in info["opciones"]:
            return entrada
        print("   Opción no reconocida. Intente de nuevo.")


def entrevista(motor: MotorMotoExpert) -> list:
    """Ciclo de preguntas guiado por Prolog. Devuelve la lista de observaciones."""
    observaciones: list = []
    alertas_mostradas: set = set()
    while True:
        variable = motor.siguiente_pregunta(observaciones)
        if variable is None:
            break
        valor = leer_respuesta(motor, observaciones, variable)
        if valor is None:
            break
        observaciones.append((variable, valor))

        # Alertas inmediatas: se avisan apenas aparecen, sin esperar el reporte.
        for alerta in motor.alertas_activas(observaciones):
            if alerta["codigo"] not in alertas_mostradas:
                alertas_mostradas.add(alerta["codigo"])
                print(f"\n   !!! ALERTA {alerta['codigo'].upper()}: {alerta['nombre']}. "
                      "Detenga la motocicleta de forma segura y siga las "
                      "recomendaciones del reporte.")
    return observaciones


def main() -> None:
    print(ENCABEZADO)
    try:
        motor = MotorMotoExpert()
    except ErrorMotor as exc:
        print(f"No fue posible iniciar el motor de Prolog: {exc}")
        return

    try:
        observaciones = entrevista(motor)
        respuesta = motor.consultar(observaciones)
        explicacion = motor.explicar(observaciones)
        falta = motor.que_falta(observaciones)
    except (ErrorMotor, KeyboardInterrupt, EOFError) as exc:
        print(f"\nConsulta interrumpida: {exc}")
        return

    print()
    print(formatear_reporte(respuesta))
    print()
    print(formatear_explicacion(explicacion))
    print()
    print(formatear_que_falta(falta))


if __name__ == "__main__":
    main()
