# Ficha de Definición del Proyecto

**Asignatura:** Sistemas Expertos  **Fecha:** octubre de 2026

## 1. Integrantes

| Nombre completo | Código estudiantil | Correo institucional | Programa |
| --- | --- | --- | --- |
| Bredman Estiven Velez Cortez | *[pendiente]* | Bredman_velezco@fet.edu.co | Ingeniería de Software |

**Modalidad:** desarrollo individual. El integrante asume los dos roles: ingeniería del conocimiento y modelado lógico (Prolog), y arquitectura de integración e interfaz (Python).

## 2. Tema seleccionado

### Título

**MotoExpert: Sistema experto basado en reglas para el diagnóstico y resolución de fallas en motocicletas.**

### Descripción del problema

Las motocicletas presentan fallas mecánicas y eléctricas que afectan su rendimiento, su confiabilidad y la seguridad de quien las conduce. Problemas como la dificultad para arrancar, las fallas de batería, el ralentí inestable o la pérdida de potencia son difíciles de identificar para un conductor o un mecánico aficionado, porque síntomas parecidos pueden tener causas distintas.

Cuando una motocicleta no enciende, la causa puede estar en la batería, el circuito de arranque, el encendido, el combustible o la compresión del motor. Sin orientación técnica, se hacen revisiones innecesarias, se cambian piezas que funcionan o se ignora una condición de riesgo.

MotoExpert recibe los síntomas y observaciones del usuario por consola, plantea hipótesis, pregunta lo necesario para diferenciarlas y entrega diagnósticos preliminares con su explicación, su nivel de respaldo, su prioridad de atención y verificaciones seguras.

**Alcance:** motocicletas de 100 a 250 cc, gasolina, cuatro tiempos, carburador y sistema eléctrico de 12 V. No sustituye la evaluación profesional.

**Usuarios:** conductores, estudiantes de mecánica, mecánicos aficionados y personas que desean entender las fallas de su vehículo.

### Justificación como sistema basado en reglas

- **El conocimiento se expresa como reglas condicionales.** Por ejemplo: "si hay clic al arrancar, el motor no gira y la alimentación eléctrica está disponible, entonces es posible una falla del relé o del motor de arranque".
- **Hay razonamiento encadenado.** Las conclusiones finales dependen de conclusiones intermedias, como el estado de la alimentación eléctrica o si una hipótesis fue descartada por una verificación.
- **Hay exclusión de hipótesis.** Una condición puede invalidar una causa aunque existan síntomas a favor. Por ejemplo, con alimentación débil no se culpa al motor de arranque. Esto se modela con negación por fallo.
- **Varias causas pueden ser compatibles a la vez.** El sistema debe reunir todas las conclusiones posibles y ordenarlas, lo que se resuelve con predicados de recolección como `setof/3`.
- **Hay incertidumbre y urgencia.** Cada hipótesis recibe un nivel cualitativo de respaldo (Alto, Medio o Bajo) y, por separado, una prioridad de atención (Baja, Media, Alta o Crítica). Una posible fuga de combustible es crítica aunque su causa no esté confirmada.
- **El sistema explica su razonamiento.** Muestra las evidencias y reglas que sustentan cada conclusión y por qué hace cada pregunta.

## 3. Listado preliminar de resultados esperados

### Alertas de seguridad

| Código | Alerta | Prioridad base |
| --- | --- | --- |
| A01 | Posible fuga de combustible | Crítica |
| A02 | Señales de sobrecalentamiento | Alta |
| A03 | Indicios de posible daño mecánico | Alta |

### Verificaciones básicas

| Código | Verificación | Prioridad base |
| --- | --- | --- |
| V01 | Interruptor de paro en posición de paro | Baja |
| V02 | Tanque sin combustible | Baja |

### Diagnósticos preliminares

| Código | Diagnóstico | Evidencias orientadoras | Prioridad base |
| --- | --- | --- | --- |
| D01 | Batería descargada o debilitada | Arranque lento, luces débiles, voltaje bajo | Media |
| D02 | Conexiones deficientes de batería | Bornes sulfatados o flojos, fallas intermitentes | Media |
| D03 | Interrupción en circuito eléctrico principal | Tablero apagado, fusible fundido | Alta |
| D04 | Posible falla del relé o motor de arranque | Clic, sin giro, alimentación disponible | Alta |
| D05 | Bujía deteriorada o contaminada | Arranque difícil, marcha irregular, bujía en mal estado | Media |
| D06 | Posible falla de bobina o circuito de encendido | Chispa ausente o débil | Alta |
| D07 | Suministro insuficiente o combustible deteriorado | Falla de arranque, pérdida de potencia, combustible antiguo | Media |
| D08 | Carburador obstruido o desajustado | Ralentí irregular, tirones, vacíos al acelerar | Media |
| D09 | Filtro de aire obstruido | Pérdida de potencia, filtro sucio | Baja |
| D10 | Posible compresión insuficiente | Arranque difícil persistente, compresión baja | Alta |

Cada resultado incluye respaldo, prioridad con sus razones, evidencias, verificaciones seguras y avisos de evidencia insuficiente o de atención profesional cuando corresponda.
