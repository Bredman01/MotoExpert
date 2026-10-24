# MotoExpert

Sistema experto auditable ("caja blanca") para el diagnóstico preliminar de fallas en motocicletas de 100 a 250 cc, cuatro tiempos y carburador. El conocimiento, la inferencia, la traza de explicación y las recomendaciones están en SWI-Prolog. Python solo ofrece la interfaz web (Streamlit), limpia las entradas y presenta los resultados.

**Autor:** Bredman Estiven Velez Cortez — Ingeniería de Software

## Contenido de la entrega

| Archivo | Contenido |
| --- | --- |
| `main.py` | Interfaz web en Streamlit: entrevista guiada, ingreso libre, dictamen, panel "¿Qué falta?" y auditoría "¿Por qué?" |
| `estilos.css`, `.streamlit/config.toml`, `icono.svg` | Diseño de la interfaz: estilos de los componentes, tema claro/oscuro con sus fuentes e ícono de la pestaña. Entréguelos junto a `main.py` |
| `motor.py` | Controlador PySwip: carga la base, convierte las respuestas en `[obs(Variable, Valor), ...]`, invoca los predicados y devuelve diccionarios |
| `base_conocimiento.pl` | Base de conocimiento comentada, con los módulos de explicabilidad (sección 7) y recomendación (sección 8) |
| `Diccionario_Predicados.md` | Firma, modo y descripción de cada predicado, incluidos los nuevos |
| `pruebas.py`, `evidencia_pruebas.txt` | 15 casos de prueba y su evidencia de ejecución |
| `consola.py` | Versión por consola del entregable 1 (opcional, sin navegador) |
| `Ficha_Definicion_Proyecto.md` | Ficha del proyecto (entregable 1) |

## Requisitos

- **SWI-Prolog 9 o superior** con `swipl` en el PATH. En Windows, al instalarlo, marque la opción de agregarlo al PATH.
- **Python 3.9 o superior**, de 64 bits como SWI-Prolog.
- Dependencias de Python:

```
pip install pyswip streamlit
```

En Windows, si `python` abre la Microsoft Store, use `py`:

```
py -m pip install pyswip streamlit
```

Versiones probadas: SWI-Prolog 10.0.2, Python 3.14.7, PySwip 0.3.3 y Streamlit 1.66.1 (Windows 11).

## Ejecución

Desde la carpeta que contiene `base_conocimiento.pl`:

```
streamlit run main.py
```

En Windows: `py -m streamlit run main.py`. El navegador se abre en `http://localhost:8501`.

### Uso de la interfaz

1. **Entrevista guiada.** Prolog elige cada pregunta (`siguiente_pregunta/2`) según las respuestas anteriores. Responda o pulse «No lo sé»; «← Volver a la pregunta anterior» deshace la última respuesta. Debajo de cada pregunta se muestra el motivo que da Prolog.
2. **Ingreso libre.** Complete los datos que conozca por grupo y pulse «Diagnosticar con estos datos». Sirve cuando ya se tienen los datos, por ejemplo de una revisión previa.
3. **Dictamen.** Muestra alertas de seguridad, verificaciones básicas y diagnósticos con su respaldo, prioridad y recomendaciones.
4. **¿Qué falta?** Si la evidencia no alcanza o hay empate, indica el dato pendiente de mayor peso y qué confirmaría o descartaría cada respuesta. Puede responderlo ahí mismo. Cuando hay empate, además aparece un aviso junto a la pregunta con un enlace a este panel.
5. **¿Por qué? Auditoría del razonamiento.** Tiene tres pestañas: reglas disparadas (árbol por conclusión), hechos comprobados e hipótesis descartadas.

La barra lateral lista los datos ingresados y permite deshacer la última respuesta o iniciar una consulta nueva.

### Caso de ejemplo

Cilindrada 150, carburador, sin fuga, sin olor, sin sobrecalentamiento, interruptor en marcha, combustible medio, giro lento y luces débiles. El sistema informa un **empate** entre D01 (batería) y D02 (bornes) y sugiere revisar los bornes. Si se responde «normal», D02 queda descartada. Con un voltaje de 11,5 V, D01 pasa a respaldo Alto.

### Otras formas de ejecutar

```
python pruebas.py      # 15 casos; genera evidencia_pruebas.txt
python consola.py      # entrevista por consola
```

Consulta directa en Prolog:

```prolog
?- consult(base_conocimiento).
?- explicar_consulta([obs(giro_arranque, lento), obs(luces, debil)], G, C, H, A).
?- que_falta([obs(giro_arranque, lento), obs(luces, debil)], S, M, E, Sug).
```

## Arquitectura

```
Navegador
   │
main.py (Streamlit) ── captura, limpieza y presentación; estado en st.session_state
   │
motor.py (PySwip) ──── [obs(Variable, Valor), ...]  →  consultas  →  diccionarios
   │
base_conocimiento.pl
   ├─ 1. Hechos
   ├─ 2-4. Validación (ground/1, minúsculas), inferencia intermedia, conclusiones
   ├─ 5. Selección de preguntas
   ├─ 6. Predicados públicos
   ├─ 7. Explicabilidad: explicar_consulta/5
   └─ 8. Recomendación: que_falta/5
```

Prolog no guarda estado entre consultas y no usa `read/1`. En cada recarga de la página recibe la lista completa de observaciones.

## Problemas frecuentes

| Síntoma | Solución |
| --- | --- |
| `No module named 'pyswip'` o `'streamlit'` | `py -m pip install pyswip streamlit` |
| La primera vez Streamlit pide un correo ("Email:") | Pulse Enter para dejarlo en blanco, o ejecute `py -m streamlit run main.py --server.headless true` y abra `http://localhost:8501` |
| `swipl` no se reconoce | Instale SWI-Prolog con la opción PATH y abra una terminal nueva |
| PySwip no encuentra `libswipl` | Use Python y SWI-Prolog de 64 bits y reinicie la terminal |
| "No se encontró la base de conocimiento" | Ejecute desde la carpeta que contiene `base_conocimiento.pl` |
| Aviso "Failed to stop Prolog threads" al cerrar | Es un mensaje de PySwip al terminar el proceso; no afecta los resultados |
