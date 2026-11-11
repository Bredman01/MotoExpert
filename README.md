# MotoExpert

Sistema experto auditable ("caja blanca") para el diagnóstico preliminar de fallas en motocicletas de 100 a 250 cc, cuatro tiempos y carburador. El usuario puede **describir la falla con sus propias palabras**, responder una entrevista guiada o llenar un formulario. Un **experto** puede enseñarle diagnósticos nuevos, que el sistema conserva entre reinicios.

El conocimiento, la inferencia, la gramática del lenguaje natural, la traza de explicación, las recomendaciones y el aprendizaje están en SWI-Prolog. Python ofrece la interfaz web (Streamlit), limpia las entradas, presenta los resultados y, de forma opcional, convierte mediciones numéricas en datos discretos.

**Autor:** Bredman Estiven Velez Cortez — Ingeniería de Software

## Contenido de la entrega

| Archivo | Contenido |
| --- | --- |
| `main.py` | Interfaz web en Streamlit: descripción en lenguaje natural, entrevista guiada, ingreso libre, dictamen, «¿Qué falta?», auditoría «¿Por qué?» y panel del experto |
| `motor.py` | Controlador PySwip: carga la base, envía los datos y el texto a Prolog, y devuelve los resultados como diccionarios |
| `base_conocimiento.pl` | Base de conocimiento comentada. Secciones 9 (gramática DCG) y 10 (modo experto) del entregable 3 |
| `conocimiento_aprendido.pl` | Diagnósticos agregados en modo experto. Lo genera Prolog y la base lo carga al iniciar |
| `clasificador.py` | Pre-procesamiento numérico opcional con scikit-learn |
| `Diccionario_Predicados.md` | Firma, modo y descripción de cada predicado, incluidos los del entregable 3 |
| `estilos.css`, `.streamlit/config.toml`, `icono.svg` | Diseño de la interfaz. Entréguelos junto a `main.py` |
| `pruebas.py`, `evidencia_pruebas.txt` | 23 casos de prueba y su evidencia de ejecución |
| `consola.py` | Versión por consola del entregable 1 (opcional, sin navegador) |

## Requisitos

- **SWI-Prolog 9 o superior** con `swipl` en el PATH. En Windows, al instalarlo, marque la opción de agregarlo al PATH.
- **Python 3.9 o superior**, de 64 bits como SWI-Prolog.
- Dependencias de Python:

```
pip install pyswip streamlit scikit-learn
```

En Windows, si `python` abre la Microsoft Store, use `py`:

```
py -m pip install pyswip streamlit scikit-learn
```

`scikit-learn` solo se usa en la parte opcional de mediciones. Sin él, el sistema funciona igual: aplica los mismos umbrales con una regla simple.

Versiones probadas: SWI-Prolog 10.0.2, Python 3.14.7, PySwip 0.3.3, Streamlit 1.66.1 y scikit-learn 1.9.1 (Windows 11).

## Ejecución

Desde la carpeta que contiene `base_conocimiento.pl`:

```
streamlit run main.py
```

En Windows: `py -m streamlit run main.py`. El navegador se abre en `http://localhost:8501`.

### Uso de la interfaz

La columna **Captura** tiene tres formas de ingresar los datos. Todas envían a Prolog la misma lista de observaciones:

1. **Descripción.** Escriba con sus palabras qué le pasa a la moto, por ejemplo: *«Mi moto de 150 cc no arranca, el motor gira lento y las luces están débiles. No huele a gasolina»*. Prolog analiza el texto con una gramática DCG, extrae los datos y muestra qué frase produjo cada uno.
2. **Entrevista guiada.** Prolog elige cada pregunta según las respuestas anteriores y explica por qué la hace. «← Volver a la pregunta anterior» deshace la última respuesta.
3. **Ingreso libre.** El formulario completo, organizado en pestañas por grupo. La pestaña **«Mediciones»** acepta la temperatura del aceite (°C) y los días sin uso: un clasificador los convierte en los datos que usa el sistema.

A la derecha aparecen el **Dictamen** (alertas, verificaciones básicas y diagnósticos con su respaldo y prioridad) y **¿Qué falta?** (el dato pendiente que más ayuda a confirmar o desempatar). Abajo, **¿Por qué?** muestra las reglas disparadas, los hechos comprobados y las hipótesis descartadas.

### Modo experto

1. En la barra lateral, sección **Modo experto**, escriba la clave y pulse «Entrar». La clave por defecto es `experto`; puede cambiarse con la variable de entorno `MOTOEXPERT_CLAVE`.
2. El **Panel del experto** tiene tres formularios:
   - **Nuevo diagnóstico:** nombre, subsistema, rama, prioridad, síntomas a favor, pruebas que lo confirman o descartan, diagnósticos con los que se confunde y recomendaciones.
   - **Nueva pregunta:** una pregunta que el sistema no tenía (por ejemplo, «¿Sube el voltaje al acelerar?»), con sus respuestas y las frases con que la pestaña «Descripción» la reconoce. Sirve para agregar la prueba que distingue un diagnóstico de otro.
   - **Nueva regla:** sobre cualquier diagnóstico, incluso los de la base: «si la respuesta es X, entonces lo apoya / lo confirma / lo debilita / lo descarta».
3. Al guardar, Prolog valida los datos, los carga en memoria con `assertz/1` y los escribe en `conocimiento_aprendido.pl`. Desde ese momento participan en todo el sistema y se conservan al reiniciar.
4. A la derecha se listan los diagnósticos, preguntas y reglas aprendidos, en pestañas, con el contenido del archivo `.pl`. Cada uno se puede eliminar (`retract/1`); una pregunta solo se elimina si ninguna regla ni diagnóstico la usa. Lo de la base original no se puede borrar.
5. Los diagnósticos y las preguntas aprendidos también se pueden **editar** con su botón «Editar», conservando su código. Si los cambios no son válidos, aparece «No se guardaron los cambios» con el motivo, lo aprendido queda como estaba y el formulario conserva lo escrito para corregirlo. Una pregunta no puede perder respuestas que una regla o un diagnóstico usan. Las reglas no se editan: se eliminan y se crean de nuevo.

**Causas sin distinguir:** si dos diagnósticos que se confunden quedan en respaldo Alto confirmados por la misma prueba, el sistema lo avisa en lugar de dar un dictamen definitivo, y sugiere el dato que los distingue. Si ese dato no existe, el experto puede crearlo como pregunta nueva y agregar las reglas correspondientes.

Con el interruptor «Ver panel del experto» se vuelve a la vista de diagnóstico sin cerrar la sesión de experto.

### Otras formas de ejecutar

```
python pruebas.py      # 23 casos; genera evidencia_pruebas.txt
python consola.py      # entrevista por consola
```

Consulta directa en Prolog:

```prolog
?- consult(base_conocimiento).
?- interpretar_texto("el motor gira lento y las luces estan debiles", Obs, Rec, NoRec).
?- explicar_consulta([obs(giro_arranque, lento), obs(luces, debil)], G, C, H, A).
?- que_falta([obs(giro_arranque, lento), obs(luces, debil)], S, M, E, Sug).
```

## Arquitectura

```
Navegador
   │
main.py (Streamlit) ── captura, limpieza y presentación; estado en st.session_state
   │        └── clasificador.py (opcional): mediciones → datos discretos
   │
motor.py (PySwip) ──── texto o [obs(Variable, Valor), ...]  →  consultas  →  diccionarios
   │
base_conocimiento.pl
   ├─ 1. Hechos
   ├─ 2-4. Validación, inferencia intermedia, conclusiones
   ├─ 5. Selección de preguntas
   ├─ 6. Predicados públicos
   ├─ 7. Explicabilidad: explicar_consulta/5
   ├─ 8. Recomendación: que_falta/5
   ├─ 9. Lenguaje natural: interpretar_texto/4 (gramática DCG)
   ├─ 10. Modo experto: aprender_diagnostico/4, aprender_pregunta/4, aprender_regla/4
   └─ :- include(conocimiento_aprendido)   ← lo aprendido se carga al iniciar
```

Prolog no usa `read/1`. En cada recarga de la página recibe la lista completa de observaciones; solo el modo experto modifica la base, con `assertz/1` y `retract/1`.

## Problemas frecuentes

| Síntoma | Solución |
| --- | --- |
| `No module named 'pyswip'`, `'streamlit'` o `'sklearn'` | `py -m pip install pyswip streamlit scikit-learn` |
| La primera vez Streamlit pide un correo ("Email:") | Pulse Enter para dejarlo en blanco, o ejecute `py -m streamlit run main.py --server.headless true` y abra `http://localhost:8501` |
| `swipl` no se reconoce | Instale SWI-Prolog con la opción PATH y abra una terminal nueva |
| PySwip no encuentra `libswipl` | Use Python y SWI-Prolog de 64 bits y reinicie la terminal |
| "No se encontró la base de conocimiento" | Ejecute desde la carpeta que contiene `base_conocimiento.pl` |
| Error al cargar `conocimiento_aprendido.pl` | El archivo debe estar junto a la base. Si se dañó, reemplácelo por uno con solo la línea `:- encoding(utf8).` |
| La descripción no reconoce una frase | Pruebe con frases cortas y directas («el motor gira lento»). Las palabras no reconocidas se listan debajo del resultado |
| Aviso "Failed to stop Prolog threads" al cerrar | Es un mensaje de PySwip al terminar el proceso; no afecta los resultados |
