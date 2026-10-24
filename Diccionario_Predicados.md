# Diccionario de Predicados — MotoExpert

Archivo: `base_conocimiento.pl` (SWI-Prolog 9.x o superior). Puente: `motor.py` (PySwip). Interfaz: `main.py` (Streamlit).

**Versión 2 (entregable 2).** Se agregan el Módulo de Explicabilidad "¿Por qué?" (sección 6), el Módulo de Recomendación "¿Qué falta?" (sección 7), sus predicados públicos (sección 1), la validación con `ground/1` y minúsculas (R1.2 y R1.2b) y los hechos que usan (sección 8). Los predicados nuevos están marcados con **(nuevo)**.

**Convención de modos de instanciación**

- `+Arg`: entrada; debe llegar instanciado (por ejemplo, la lista enviada desde Python).
- `-Arg`: salida; Prolog lo instancia y Python lo recibe.
- `?Arg`: puede usarse como entrada o como salida.

**Estructura de la entrada**

`ListaObs` es una lista de términos `obs(Variable, Valor)`. Ejemplo:

```prolog
[obs(giro_arranque, lento), obs(luces, debil), obs(voltaje, 11.6)]
```

`Caso` es la misma lista ya normalizada: sin elementos inválidos y sin variables repetidas.

---

## 1. Predicados invocados desde Python

| Firma | Modo | Descripción funcional | Función de `motor.py` |
| --- | --- | --- | --- |
| `consultar/6` | `consultar(+ListaObs, -Estado, -Mensaje, -Resultados, -Descartadas, -Invalidas)` | Consulta completa. Valida la lista, obtiene todas las conclusiones ordenadas, las hipótesis descartadas o excluidas con su motivo, los elementos inválidos y el estado general de la consulta | `consultar()` |
| `diagnosticar_todos/2` | `diagnosticar_todos(+ListaObs, -Resultados)` | Predicado principal de recolección. Reúne con `setof/3` todas las conclusiones (alertas, verificaciones básicas y diagnósticos) en una sola lista, sin duplicados y ordenadas. Devuelve `[]` si no hay ninguna | `diagnosticar_todos()` |
| `codigos_diagnostico/2` | `codigos_diagnostico(+ListaObs, -Codigos)` | Versión resumida: solo los códigos de las conclusiones, sin duplicados (`setof/3`) | `codigos()` |
| `siguiente_pregunta/2` | `siguiente_pregunta(+ListaObs, -Variable)` | Elige la siguiente variable a preguntar. Devuelve `fin` cuando no quedan preguntas útiles, se alcanzó el máximo o el caso está fuera de alcance | `siguiente_pregunta()` |
| `por_que_pregunta/3` | `por_que_pregunta(+ListaObs, +Variable, -Motivo)` | Explicación "¿por qué me pregunta esto?": la fase del triaje o las hipótesis que la respuesta ayuda a confirmar o descartar | `por_que()` |
| `info_pregunta/4` | `info_pregunta(+Variable, -Texto, -Opciones, -TipoEntrada)` | Texto de la pregunta, valores admitidos y tipo de entrada (`numerico` u `opciones`) | `info_pregunta()` |
| `alertas_activas/2` | `alertas_activas(+ListaObs, -Alertas)` | Alertas de seguridad presentes, como `[[Codigo, Nombre], ...]`. Se usa para avisar durante la entrevista | `alertas_activas()` |
| `estado_alimentacion/2` | `estado_alimentacion(+Caso, -Estado)` | Conclusión intermedia: `ausente`, `debil`, `disponible` o `desconocida`. Se invoca en la prueba de exclusión | `consulta_libre()` |
| `explicar_consulta/5` **(nuevo)** | `explicar_consulta(+ListaObs, -General, -Conclusiones, -Hechos, -Alternativas)` | Módulo "¿Por qué?". Devuelve la traza del razonamiento común, el árbol de reglas disparadas de cada conclusión, los hechos comprobados como verdaderos y las hipótesis alternativas descartadas, excluidas o sin evidencia crítica | `explicar()` |
| `que_falta/5` **(nuevo)** | `que_falta(+ListaObs, -Situacion, -Mensaje, -Evaluadas, -Sugerencias)` | Módulo "¿Qué falta?". Clasifica la evidencia (`definitivo`, `empate`, `insuficiente`, `sin_hipotesis`, `fuera_de_alcance`) y propone, ordenados por peso, los datos no ingresados que más ayudan a confirmar o desempatar | `que_falta()` |
| `catalogo_variables/1` **(nuevo)** | `catalogo_variables(-Variables)` | Variables con grupo, tipo, etiqueta, pregunta, opciones legibles y tipo de entrada. La interfaz arma sus formularios con él, sin repetir el conocimiento en Python | `catalogo()` |

**Estructura de cada elemento de `Resultados`** (lista posicional; `motor.py` la convierte en diccionario con `CAMPOS_RESULTADO`):

| Pos. | Campo | Ejemplo |
| --- | --- | --- |
| 1 | Tipo | `alerta`, `basica` o `diagnostico` |
| 2 | Código | `d01` |
| 3 | Nombre | `'Batería descargada o debilitada'` |
| 4 | Subsistema | `'Batería'` |
| 5 | Respaldo | `alto`, `medio`, `bajo` o `no_aplica` (alertas) |
| 6 | Justificación del respaldo | Texto |
| 7 | Prioridad | 1 a 4 |
| 8 | Etiqueta de prioridad | `'Media'` |
| 9 | Acción recomendada por la prioridad | Texto |
| 10 | Evidencias a favor | Lista de textos |
| 11 | Evidencias en contra | Lista de textos |
| 12 | Razones de la prioridad | Lista: base, elevaciones y reducciones |
| 13 | Recomendaciones | Lista de verificaciones y acciones seguras |
| 14 | Avisos | Lista: evidencia insuficiente, atención profesional, carácter preliminar |
| 15 | Coincidencia | `'condiciones cumplidas: 3; variables del perfil: 4'` |

**Elementos de `Descartadas`:** `[Codigo, Nombre, Motivo]`.

**Valores de `Estado`:** `con_resultados`, `datos_insuficientes`, `sin_diagnostico_concluyente`, `fuera_de_alcance` o `sin_datos`.

**Estructuras de `explicar_consulta/5`:**

| Argumento | Elemento | Contenido |
| --- | --- | --- |
| `General` | `[Profundidad, IdRegla, Texto]` | Pasos comunes: normalización (R1.5), alcance (R1.10), voltaje (R1.6), alimentación (R2.1), exclusiones (R2.2), señales de riesgo (R1.11) y estado (R3.11) |
| `Conclusiones` | `[Tipo, Codigo, Nombre, Pasos]` | Un árbol por conclusión reportada. `Pasos` usa la misma forma `[Profundidad, IdRegla, Texto]`; la profundidad 0 es la conclusión y 1–3 las reglas y hechos de los que depende |
| `Hechos` | `[Texto, Usos]` | Observación válida y verdadera en el caso, con la lista de hechos y reglas de la base con los que unifica (por ejemplo `evidencia(d01, luces, debil)`) |
| `Alternativas` | `[Codigo, Nombre, Tipo, Compartidos, Motivo]` | `Tipo`: `descartada` (verificación en contra), `excluida` (`\+ excluida/3` falla) o `sin_evidencia_critica` (no cumple `requisito/2`). `Compartidos`: síntomas del caso que la hipótesis tenía a favor |

**Estructuras de `que_falta/5`:**

| Argumento | Elemento | Contenido |
| --- | --- | --- |
| `Evaluadas` | `[Codigo, Nombre, Respaldo]` | Hipótesis objetivo; `sin_evidencia` si aún no tiene evidencia a favor |
| `Sugerencias` | `[Variable, Etiqueta, Pregunta, Peso, Prioridad, Tipo, Efectos]` | Hasta `max_sugerencias` datos pendientes. `Efectos`: un texto por valor posible, por ejemplo `'Si la respuesta es «normal»: descartaría D02.'` |

---

## 2. Nivel 1 — Validación preliminar

| ID | Firma | Modo | Descripción funcional | Técnica |
| --- | --- | --- | --- | --- |
| R1.1 | `valor/3` | `valor(+Variable, +Caso, -Valor)` | Valor observado de una variable; `desconocido` si no existe | Corte + cláusula por defecto |
| R1.2 | `obs_valida/1` | `obs_valida(+Observacion)` | Comprueba con `ground/1` que no haya variables libres, luego la forma `obs/2`, que la variable exista y que el valor esté admitido o dentro del rango numérico | `ground/1` + corte entre cláusulas excluyentes |
| R1.2b | `limpiar_obs/2` **(nuevo)** | `limpiar_obs(+Observacion, -Limpia)` | Pasa a minúscula la variable y el valor de una observación `obs/2`; lo que no tiene esa forma se devuelve igual para que `obs_valida/1` lo rechace | Corte + cláusula por defecto |
| — | `minuscula/2` **(nuevo)** | `minuscula(+Termino, -Resultado)` | Si el término es un átomo lo pasa a minúscula con `downcase_atom/2`; números y variables se devuelven sin cambio | Corte + cláusula por defecto |
| R1.3 | `particionar_obs/3` | `particionar_obs(+Lista, -Validas, -Invalidas)` | Separa los elementos válidos (ya limpios) de los inválidos (tal como llegaron) | Recursión sobre listas + corte |
| R1.4 | `quitar_repetidas/3` | `quitar_repetidas(+Lista, +Vistas, -SinRepetir)` | Conserva solo la primera observación de cada variable | Recursión sobre listas + corte |
| R1.5 | `normalizar_caso/2` | `normalizar_caso(+ListaObs, -Caso)` | Filtra inválidos y repetidos; una entrada que no es lista se convierte en `[]` | Corte + cláusula por defecto |
| R1.6 | `voltaje_estado/2` | `voltaje_estado(+Caso, -Estado)` | Clasifica el voltaje en `bajo` (< 12,4 V), `normal` o `desconocido` | Corte + cláusula por defecto |
| R1.7 | `hecho_caso/3` | `hecho_caso(+Caso, +Variable, ?Valor)` | Acceso uniforme a los hechos del caso; para el voltaje entrega el estado derivado | — |
| R1.8 | `cumple_todas/2` | `cumple_todas(+Caso, +Condiciones)` | Verifica que una lista de condiciones `Variable-Valor` sea subconjunto de los hechos del caso | Recursión sobre listas |
| R1.9 | `contar_cumplidas/3` | `contar_cumplidas(+Caso, +Condiciones, -N)` | Cuenta cuántas condiciones de la lista se cumplen | Recursión sobre listas + corte |
| R1.10 | `fuera_de_alcance/2` | `fuera_de_alcance(+Caso, -Motivo)` | Cilindrada fuera de 100–250 cc o alimentación por inyección | — |
| R1.11 | `senales_riesgo_caso/2` | `senales_riesgo_caso(+Caso, -Senales)` | Lista de señales de riesgo presentes | `findall/3` |
| R1.12 | `valor_legible/2` | `valor_legible(+Valor, -Texto)` | Forma legible de un valor (por ejemplo, `debil` → `débil`) | Corte + cláusula por defecto |
| R1.13 | `describir_hecho/3` | `describir_hecho(+Caso, +Variable-Valor, -Texto)` | Texto de una observación para las explicaciones | Corte |

## 3. Nivel 2 — Inferencia intermedia

| ID | Firma | Modo | Descripción funcional | Técnica |
| --- | --- | --- | --- | --- |
| R2.1 | `estado_alimentacion/2` | `estado_alimentacion(+Caso, -Estado)` | Deduce si la alimentación eléctrica está ausente, débil, disponible o desconocida | Corte en estados excluyentes + cláusula por defecto |
| R2.2 | `excluida/3` | `excluida(+Caso, ?Diagnostico, -Motivo)` | Criterios de exclusión: rama motor si el motor no gira; D04 con alimentación débil o ausente; D06 con interruptor en paro; D07 con tanque vacío | Se usa dentro de `\+` |
| R2.3 | `descartada/3` | `descartada(+Caso, ?Diagnostico, -Motivo)` | La hipótesis queda descartada si se cumplen todas las condiciones de un hecho `descarte/2` | Subconjunto de listas (R1.8) |
| R2.4 | `evidencias_favor/3` | `evidencias_favor(+Caso, +Diagnostico, -Lista)` | Síntomas y verificaciones a favor presentes en el caso | `findall/3` + `sort/2` |
| R2.5 | `verificacion_favor/2` | `verificacion_favor(+Caso, +Diagnostico)` | Existe al menos una verificación específica a favor | Corte (basta una) |
| R2.6 | `contraevidencias/3` | `contraevidencias(+Caso, +Diagnostico, -Lista)` | Evidencias en contra presentes | `findall/3` |
| R2.7 | `cumple_requisito/2` | `cumple_requisito(+Caso, +Diagnostico)` | Sin requisitos definidos, o al menos una lista de requisitos cumplida | `\+` + corte |
| R2.8 | `competidoras/2` | `competidoras(?A, ?B)` | Relación simétrica de competencia, construida sin recursión para evitar ciclos | — |
| R2.9 | `competidoras_descartadas/2` | `competidoras_descartadas(+Caso, +Diagnostico)` | Todas las competidoras están descartadas por verificación | Recursión sobre listas (`todas_descartadas/2`) |
| R2.10 | `compatible/2` | `compatible(+Caso, ?Diagnostico)` | Hipótesis ni descartada ni excluida | Negación por fallo (`\+`) |
| R2.11 | `hipotesis_activa/2` | `hipotesis_activa(+Caso, ?Diagnostico)` | Compatible, con requisitos cumplidos y al menos una evidencia a favor | — |
| R2.12 | `perfil/2` | `perfil(+Codigo, -Condiciones)` | Condiciones que respaldan una conclusión (evidencias y verificaciones, disparadores o condiciones básicas) | Corte entre tipos |
| R2.13 | `coincidencia/4` | `coincidencia(+Caso, +Codigo, -Cumplidas, -Variables)` | Cuántas condiciones del perfil se cumplen (con `contar_cumplidas/3`) y sobre cuántas variables | Procesamiento de listas |
| R2.14 | `respaldo/4` | `respaldo(+Caso, +Diagnostico, -Nivel, -Justificacion)` | Calcula el respaldo cualitativo | — |
| R2.15 | `clasificar_respaldo/6` | `clasificar_respaldo(+Caso, +Diag, +N, +Contra, -Nivel, -Just)` | Reglas de respaldo evaluadas en orden (Alto, Medio, Bajo) | Corte en reglas excluyentes + cláusula por defecto |
| R2.16 | `alerta_activa/3` | `alerta_activa(+Caso, ?Alerta, -Disparadores)` | Alerta con al menos un disparador presente | `findall/3` |
| R2.17 | `basica_activa/3` | `basica_activa(+Caso, ?Codigo, -Condiciones)` | Verificación básica cuyas condiciones se cumplen | Subconjunto de listas |

## 4. Nivel 3 — Conclusiones, prioridad y recolección

| ID | Firma | Modo | Descripción funcional | Técnica |
| --- | --- | --- | --- | --- |
| R3.1 | `elevacion/3` | `elevacion(+Caso, +Codigo, -Razon)` | Criterios E1, E2 y E3 para elevar la prioridad | — |
| R3.2 | `reduccion/3` | `reduccion(+Caso, +Codigo, -Razon)` | Criterios R1 y R2 para reducir la prioridad | — |
| R3.3 | `acotar/4` | `acotar(+N, +Min, +Max, -Acotado)` | Mantiene la prioridad entre 1 y 4 | Corte en casos excluyentes |
| R3.4 | `prioridad/6` | `prioridad(+Caso, +Codigo, -Nivel, -Etiqueta, -Accion, -Razones)` | Prioridad = base + elevaciones − reducciones, con sus razones | `findall/3` |
| R3.5 | `avisos/4` | `avisos(+Tipo, +Nivel, +Respaldo, -Avisos)` | Avisos de evidencia insuficiente, atención profesional y carácter preliminar | `findall/3` |
| R3.6 | `conclusion/2` | `conclusion(+Caso, -Clave-Resultado)` | Cada conclusión posible: alertas siempre; básicas y diagnósticos solo si el caso está dentro del alcance | `\+ fuera_de_alcance` |
| R3.7 | `armar_resultado/11` | `armar_resultado(+Caso, +Tipo, +Codigo, +Nombre, +Subsistema, +Respaldo, +JustRespaldo, +Favor, +Contra, -Clave, -Resultado)` | Completa prioridad, textos, recomendaciones y la clave de orden `k(OrdenTipo, -Prioridad, -Respaldo, Codigo)` | `findall/3` |
| R3.8 | `diagnosticar_todos/2` | `diagnosticar_todos(+ListaObs, -Resultados)` | Recolección principal (ver sección 1) | `setof/3` + rama por defecto `[]` |
| R3.9 | `codigos_diagnostico/2` | `codigos_diagnostico(+ListaObs, -Codigos)` | Recolección de códigos (ver sección 1) | `setof/3` |
| — | `codigo_conclusion/2` | `codigo_conclusion(+Caso, -Codigo)` | Auxiliar de R3.9: código de cada conclusión, para que `setof/3` no agrupe por variables libres | — |
| R3.10 | `hipotesis_descartadas/2` | `hipotesis_descartadas(+ListaObs, -Lista)` | Hipótesis descartadas o excluidas con un solo motivo cada una | `findall/3` |
| — | `motivo_rechazo/3` | `motivo_rechazo(+Caso, +Diagnostico, -Motivo)` | Motivo de descarte o, si compartía síntomas, de exclusión | Corte (un solo motivo) |
| — | `mensaje_consulta/3` | `mensaje_consulta(+Caso, +Estado, -Mensaje)` | Mensaje del estado; si el caso está fuera de alcance, antepone el motivo | Corte + cláusula por defecto |
| — | `observaciones_invalidas/2` | `observaciones_invalidas(+ListaObs, -Invalidas)` | Elementos rechazados por la validación, como texto, para informarlos al usuario | Corte + cláusula por defecto |
| R3.11 | `estado_consulta/3` | `estado_consulta(+Caso, +Resultados, -Estado)` | Estado general de la consulta | Corte en estados excluyentes + cláusula por defecto |

## 5. Selección de preguntas

| ID | Firma | Modo | Descripción funcional | Técnica |
| --- | --- | --- | --- | --- |
| R5.1 | `ya_preguntada/2` | `ya_preguntada(+Variable, +Caso)` | La variable ya tiene respuesta | `memberchk/2` |
| R5.2 | `var_relacionada/2` | `var_relacionada(?Diagnostico, ?Variable)` | Variables que afectan una hipótesis | — |
| R5.3 | `hay_activas/1` | `hay_activas(+Caso)` | Existe al menos una hipótesis activa | Corte |
| R5.4 | `en_juego/2` | `en_juego(+Caso, ?Diagnostico)` | Hipótesis relacionadas con el caso; se usa en la explicación general de una pregunta | Cláusulas excluyentes por `\+` |
| R5.6 | `mejor_candidata/2` **(modificado)** | `mejor_candidata(+Caso, -Variable)` | La sugerencia principal del módulo "¿Qué falta?" (R8.2 y R8.6). La entrevista y el panel usan así un único criterio y nunca se contradicen. Falla si no queda ningún dato útil | Reutiliza `situacion_evidencia/3` y `sugerencias/3` |
| R5.7 | `primera_fase_pendiente/2` | `primera_fase_pendiente(+Caso, -Variable)` | Primera pregunta del triaje sin responder | `msort/2` |
| R5.8 | `elegir_pregunta/2` | `elegir_pregunta(+Caso, -Variable)` | En orden: fuera de alcance o máximo de preguntas → `fin`; triaje pendiente (siempre se completa); sugerencia principal (R5.6); `fin` cuando ningún dato pendiente cambiaría el resultado | Corte + cláusula por defecto `fin` |
| R5.9 | `motivo_pregunta/3` | `motivo_pregunta(+Caso, +Variable, -Motivo)` | Explicación de la pregunta: motivo del triaje, o el peso y el efecto de cada respuesta según "¿Qué falta?" | Corte + cláusula por defecto |

En la versión 2 se retiró `puntaje_pregunta/3` (antes R5.5): la entrevista elegía la variable que afectaba a más hipótesis, incluidas algunas sin evidencia, y podía contradecir al panel "¿Qué falta?".

## 6. Módulo de Explicabilidad "¿Por qué?" (nuevo)

La traza se construye llamando a **las mismas reglas** que producen las conclusiones: cada paso se agrega solo si la regla que documenta tiene éxito sobre el caso. Así la explicación no puede contradecir el dictamen. Los generadores de pasos se recorren con `findall/3` y no llevan cortes (un corte detendría la traza); las alternativas internas usan if-then-else.

| ID | Firma | Modo | Descripción funcional | Técnica |
| --- | --- | --- | --- | --- |
| R7.1 | `paso_hecho/4` | `paso_hecho(+Caso, +Profundidad, +Variable-Valor, -Paso)` | Hoja del árbol: hecho del caso que unificó con una condición. Para el voltaje documenta la comparación con el umbral (R1.6) | Corte en la cláusula del voltaje |
| R7.2 | `traza_general/3` | `traza_general(+ListaObs, +Caso, -Pasos)` | Reúne los pasos comunes a todas las conclusiones | `findall/3` |
| — | `paso_general/3` | `paso_general(+ListaObs, +Caso, -Paso)` | Generador de cada paso común: normalización (R1.5), alcance (R1.10), voltaje (R1.6), alimentación (R2.1), exclusiones (R2.2), señales de riesgo (R1.11) y estado (R3.11). Un paso solo se produce si su regla tiene éxito | Generador sin cortes, `setof/3` con `^` |
| R7.3 | `traza_conclusiones/2` | `traza_conclusiones(+Caso, -Conclusiones)` | Un árbol de reglas disparadas por cada conclusión, en el orden del reporte | `findall/3` anidado |
| R7.4 | `paso_conclusion/4` | `paso_conclusion(+Caso, +Tipo, +Codigo, -Paso)` | Reglas disparadas por tipo. Diagnóstico: R3.6 → R2.11 (R2.10, R2.7, R2.4 + hechos) → R2.14 (R2.13, R2.6, R2.15, R2.5 o R2.9). Alerta: R3.6 → R2.16 + disparadores. Básica: R3.6 → R2.17 + condiciones. Todos: R3.4 con base, elevaciones (R3.1) y reducciones (R3.2) | Generador sin cortes |
| R7.5 | `hechos_comprobados/2` | `hechos_comprobados(+Caso, -Hechos)` | Observaciones válidas y verdaderas en el caso, con los hechos y reglas de la base con los que unifican (`uso_hecho/3`) | `findall/3` + `sort/2` |
| — | `uso_hecho/3` | `uso_hecho(+Variable, +Valor, -Uso)` | Hecho (`evidencia/3`, `verificacion/3`, `descarte/2`, ...) o regla (R1.10, R2.1, R2.2, R3.2) que unifica con `Variable = Valor` | — |
| R7.6 | `hipotesis_alternativas/2` | `hipotesis_alternativas(+Caso, -Alternativas)` | Diagnósticos no reportados con su causa y los síntomas que compartían con el caso. Vacía si el caso está fuera de alcance | Corte + `findall/3` |
| — | `motivo_alternativa/4` | `motivo_alternativa(+Caso, +Diag, -Tipo, -Motivo)` | Un motivo por hipótesis, en orden: `descartada`, `excluida` (solo si compartía síntomas), `sin_evidencia_critica` (`\+ cumple_requisito/2`) | Corte + `\+` |
| R7.7 | `textos_hechos/3` | `textos_hechos(+Caso, +Condiciones, -Texto)` | Condiciones `Variable-Valor` como texto legible: "Etiqueta: valor; ..." | `findall/3` |
| — | `codigos_texto/2` | `codigos_texto(+Codigos, -Texto)` | Lista de códigos en mayúscula separados por comas: "D01, D02" | `findall/3` |

## 7. Módulo de Recomendación "¿Qué falta?" (nuevo)

**Peso de una variable** = suma, sobre las hipótesis objetivo, del efecto más fuerte que alguno de sus valores tendría en cada una (`peso_efecto/2`: confirmar o descartar 3, contradecir 2, apoyar o ayudar a descartar 1). Orden de las sugerencias: mayor peso, luego mayor prioridad de las hipótesis afectadas, luego menor costo de respuesta (`costo_tipo/2`). Solo se sugieren datos aún no ingresados: una variable respondida con «No lo sé» (`desconocido`) ya fue ingresada y no se vuelve a sugerir.

| ID | Firma | Modo | Descripción funcional | Técnica |
| --- | --- | --- | --- | --- |
| R8.1 | `candidatas/2` | `candidatas(+Caso, -Candidatas)` | Hipótesis activas con su respaldo: `[Rango-Codigo-Respaldo, ...]` | `findall/3` |
| R8.2 | `situacion_evidencia/3` | `situacion_evidencia(+Caso, -Situacion, -Objetivo)` | Clasifica la evidencia y elige las hipótesis objetivo. `fuera_de_alcance`; `sin_hipotesis` (objetivo: todas las compatibles); o según R8.3 | Corte en situaciones excluyentes, `\+ hay_activas/1` |
| R8.3 | `clasificar_situacion/5` | `clasificar_situacion(+RangoMax, +Tope, +Candidatas, -Situacion, -Objetivo)` | `definitivo` (mejor respaldo Alto; objetivo, las demás), `empate` (dos o más comparten el mejor respaldo; objetivo, las empatadas), `insuficiente` (objetivo, todas las activas) | Corte + cláusula por defecto |
| R8.4 | `efecto_valor/5` | `efecto_valor(+Caso, +Hipotesis, +Variable, +Valor, -Efecto)` | Efecto de un dato hipotético: `confirma`, `descarta`, `contribuye_descarte`, `contradice` o `apoya` | `select/3` + `cumple_todas/2` |
| — | `valor_posible/2` | `valor_posible(+Variable, -Valor)` | Valores que podría tomar un dato pendiente; para el voltaje, los derivados `bajo`/`normal` | Corte + `member/2` |
| R8.5 | `peso_variable/5` | `peso_variable(+Caso, +Objetivo, +Variable, -Peso, -Efectos)` | Peso de la variable y lista `Valor-Hipotesis-Efecto`. Falla si no afecta a ninguna hipótesis objetivo | `findall/3`, `max_list/2`, `sum_list/2` |
| R8.6 | `sugerencias/3` | `sugerencias(+Caso, +Objetivo, -Sugerencias)` | Datos aún no ingresados (`\+ ya_preguntada/2`) ordenados por peso, prioridad y costo; devuelve los primeros `max_sugerencias` | `\+` + `keysort/2` + `primeros/3` |
| — | `prioridad_afectadas/3` | `prioridad_afectadas(+Caso, +Efectos, -Prioridad)` | Mayor prioridad (R3.4) entre las hipótesis afectadas | `max_list/2` |
| — | `textos_efectos/3` | `textos_efectos(+Variable, +Efectos, -Textos)` | Un texto por valor posible ("Si la respuesta es «normal»: descartaría D02.") | `findall/3` anidado |
| — | `valor_sugerido/3` | `valor_sugerido(+Variable, +Valor, -Texto)` | Texto del valor dentro del efecto; para el voltaje usa el umbral ("menos de 12.4 V") | Corte + cláusula por defecto |
| — | `primeros/3` | `primeros(+Lista, +N, -Primeros)` | Los N primeros elementos | Recursión sobre listas + corte |
| R8.7 | `hipotesis_evaluadas/3` | `hipotesis_evaluadas(+Caso, +Objetivo, -Evaluadas)` | `[Codigo, Nombre, Respaldo]` de las hipótesis objetivo | if-then-else |
| — | `mensaje_falta_caso/3` | `mensaje_falta_caso(+Situacion, +Sugerencias, -Mensaje)` | Mensaje de la situación; si no es definitiva y no quedan sugerencias, recomienda revisión profesional | Corte + cláusula por defecto |

---

## 8. Hechos de la base de conocimiento

Todos los predicados de hechos tienen aridad ≥ 2 y están agrupados de forma contigua.

| Predicado | N.º de hechos | Contenido |
| --- | --- | --- |
| `grupo/2` | 5 | Grupos de variables |
| `variable/5` | 31 | Variable, grupo, tipo, etiqueta y pregunta |
| `opciones/2` | 31 | Valores admitidos por variable |
| `rango_numerico/3` | 2 | Rango válido de las variables numéricas |
| `parametro/2` | 5 | Umbral de voltaje, máximo de preguntas, rango de cilindrada y máximo de sugerencias |
| `diagnostico/4` | 10 | Código, nombre, subsistema y rama |
| `alerta/3` | 3 | Alertas de seguridad |
| `disparador_alerta/3` | 5 | Señales que activan cada alerta |
| `verificacion_basica/4` | 2 | Causas simples y sus condiciones |
| `prioridad_base/2` | 15 | Prioridad inicial de cada conclusión |
| `nivel_prioridad/3` | 4 | Escala de prioridad |
| `evidencia/3` | 38 | Evidencias a favor |
| `verificacion/3` | 12 | Verificaciones específicas a favor |
| `contraevidencia/3` | 4 | Evidencias en contra |
| `descarte/2` | 9 | Condiciones que descartan una hipótesis (listas) |
| `requisito/2` | 3 | Condiciones mínimas de activación (listas) |
| `compite_con/2` | 15 | Parejas de hipótesis competidoras |
| `senal_riesgo/2` | 6 | Señales de riesgo para la prioridad |
| `recomendacion/2` | 30 | Verificaciones y acciones seguras |
| `fase_inicial/3` | 8 | Preguntas fijas del triaje con su motivo |
| `costo_tipo/2` | 4 | Costo de responder según el tipo de variable |
| `orden_tipo/2` | 3 | Orden de los tipos de conclusión en el reporte |
| `rango_respaldo/2` | 4 | Orden de los niveles de respaldo |
| `texto_valor/2` | 9 | Forma legible de algunos valores |
| `mensaje_estado/2` | 5 | Mensaje de cada estado de la consulta |
| `valores_derivados/2` **(nuevo)** | 1 | Valores cualitativos deducidos del voltaje |
| `peso_efecto/2` **(nuevo)** | 5 | Peso de cada efecto de un dato pendiente |
| `texto_efecto/2` **(nuevo)** | 5 | Redacción de cada efecto |
| `mensaje_falta/2` **(nuevo)** | 6 | Mensaje de cada situación del módulo "¿Qué falta?" |

**Total:** 280 hechos en 29 predicados y más de 150 cláusulas de regla.

---

## 9. Cumplimiento de los requisitos del entregable 2

| Requisito | Dónde se cumple |
| --- | --- |
| Interfaz funcional (Streamlit) conectada en tiempo real con PySwip | `main.py`; cada recarga invoca `consultar/6`, `explicar_consulta/5` y `que_falta/5` (las consultas exactas quedan registradas en `evidencia_pruebas.txt`) |
| Python: solo interfaz, captura, limpieza y presentación | `main.py` y `motor.py` (`limpiar_valor()`, `limpiar_observaciones()`); el formulario se arma con `catalogo_variables/1` |
| Sin `read/1` en Prolog | Ningún predicado lee de la entrada; el caso viaja como lista |
| Validación de entradas en Prolog (`ground/1`, minúsculas) | R1.2 `obs_valida/1`, R1.2b `limpiar_obs/2` |
| Reglas disparadas (intermedias y finales) | R7.2–R7.4 |
| Hechos comprobados como verdaderos | R7.5 |
| Hipótesis alternativas descartadas (falta de evidencia crítica o `\+`) | R7.6 |
| Predicado de desempate ante evidencia insuficiente | R8.1–R8.7, `que_falta/5` |

## 10. Cumplimiento de los requisitos técnicos (entregable 1)

| Requisito | Dónde se cumple |
| --- | --- |
| ≥ 30 hechos de aridad ≥ 2, agrupados por predicado | Sección 1 del `.pl` (260 hechos en 25 predicados) |
| ≥ 15 reglas encadenadas en tres niveles | Nivel 1: R1.1–R1.13; Nivel 2: R2.1–R2.17; Nivel 3: R3.1–R3.11 |
| Prevención de ciclos | Sin recursión izquierda; recursión solo sobre la cola de listas; `competidoras/2` sin recursión; dependencias solo de niveles superiores hacia inferiores |
| Uso de listas | R1.3, R1.4, R1.8 (subconjunto), R1.9 (conteo), R2.9, `descarte/2` y `requisito/2` con listas de condiciones |
| Corte (`!`) en reglas excluyentes y cláusulas por defecto | R1.1, R1.5, R1.6, R2.1, R2.15, R3.3, R3.11, R5.8, entre otros |
| Negación por fallo (`\+`) con variables instanciadas | R2.7, R2.10, R3.6, R5.4 |
| Recolección (`setof/3`) sin duplicados | R3.8 `diagnosticar_todos/2` y R3.9 `codigos_diagnostico/2` |
| Severidad o prioridad en Prolog | R3.1–R3.4 |
| Integración con PySwip | `motor.py`; consola en `consola.py`, interfaz web en `main.py` |
| Lógica solo en Prolog | Python solo serializa la lista, invoca predicados y da formato |
