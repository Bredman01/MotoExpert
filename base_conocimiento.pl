:- encoding(utf8).
/*  =========================================================================
    MotoExpert
    Sistema experto basado en reglas para el diagnóstico preliminar de
    fallas en motocicletas.

    Archivo : base_conocimiento.pl
    Motor   : SWI-Prolog 9.x
    Autor   : Bredman Estiven Velez Cortez
    Alcance : motocicletas de 100 a 250 cc, gasolina, cuatro tiempos,
              carburador y sistema eléctrico convencional de 12 V.

    REPRESENTACIÓN DEL CASO
    -----------------------
    Python envía el caso como una LISTA de observaciones:

        [obs(Variable, Valor), obs(Variable, Valor), ...]

    Ejemplo: [obs(giro_arranque, lento), obs(luces, debil), obs(voltaje, 11.6)]

    Ningún predicado usa assert/retract: la lista viaja como argumento.
    Así cada consulta es independiente, repetible y fácil de probar.

    ORGANIZACIÓN DEL ARCHIVO
    ------------------------
      1. Hechos (agrupados de forma contigua por predicado)
      2. Nivel 1 - Validación preliminar
      3. Nivel 2 - Inferencia intermedia
      4. Nivel 3 - Conclusiones, prioridad y recolección
      5. Selección de preguntas y explicación "¿por qué pregunta esto?"
      6. Predicados de consulta invocados desde Python
      7. Módulo de explicabilidad "¿Por qué?" (traza de inferencia)
      8. Módulo de recomendación "¿Qué falta?" (desempate)

    Python (interfaz Streamlit) nunca usa read/1 en Prolog: cada consulta
    recibe la lista completa y devuelve resultados como listas.

    PREVENCIÓN DE CICLOS
    --------------------
    - Ninguna regla es recursiva por la izquierda. Las únicas reglas
      recursivas recorren listas y su primera meta consume la cabeza
      de la lista ([X|Resto]), de modo que siempre terminan.
    - La relación simétrica "compiten" NO se define como
      compiten(A,B) :- compiten(B,A) (eso cicla). Se usa un hecho
      no simétrico (compite_con/2) y una regla con dos cláusulas
      que consultan solo el hecho (R2.8).
    - Las reglas de Nivel 3 solo llaman a Nivel 2 y Nivel 1, y las de
      Nivel 2 solo a Nivel 1 y a hechos: no hay dependencias circulares.
    ========================================================================= */

/* =========================================================================
   1. HECHOS
   ========================================================================= */

% -------------------------------------------------------------------------
% 1.1 grupo(Id, Nombre): grupos de variables de entrada.
% -------------------------------------------------------------------------
grupo(general,     'Información general y condiciones del vehículo').
grupo(electrico,   'Sistema eléctrico y arranque').
grupo(motor,       'Comportamiento del motor').
grupo(combustible, 'Combustible y admisión de aire').
grupo(encendido,   'Encendido y condiciones mecánicas').

% -------------------------------------------------------------------------
% 1.2 variable(Id, Grupo, Tipo, Etiqueta, Pregunta)
%     Tipo indica el esfuerzo para responder y ordena las preguntas:
%       dato / sintoma  -> el usuario lo sabe u observa sin herramientas
%       revision        -> requiere una inspección visual sencilla
%       prueba_tecnica  -> solo si ya la realizó personal capacitado
%     31 variables (ver la tabla de trazabilidad en la propuesta revisada).
% -------------------------------------------------------------------------
variable(cilindrada,             general,     dato,           'Cilindrada',                         'Cilindrada de la motocicleta en cc (escriba el número)').
variable(alimentacion,           general,     dato,           'Tipo de alimentación',               '¿Qué sistema de alimentación de combustible tiene la motocicleta?').
variable(condicion_motor,        general,     sintoma,        'Temperatura del motor en la falla',  '¿En qué condición del motor ocurre la falla?').
variable(tiempo_sin_uso,         general,     dato,           'Tiempo sin uso',                     '¿Cuánto tiempo llevaba la motocicleta sin usarse?').
variable(nivel_combustible,      general,     revision,       'Nivel de combustible',               '¿Cuál es el nivel de combustible en el tanque?').
variable(interruptor_paro,       general,     revision,       'Interruptor de apagado del motor',   'Mire el interruptor rojo del manubrio derecho, el que apaga el motor (dice RUN y OFF). ¿En qué posición está?').
variable(mantenimiento_reciente, general,     dato,           'Mantenimiento al día',               '¿La motocicleta tiene al día su mantenimiento rutinario?').
variable(tablero,                electrico,   sintoma,        'Tablero',                            '¿Enciende el tablero al girar la llave?').
variable(luces,                  electrico,   sintoma,        'Intensidad de las luces',            '¿Cómo es la intensidad de las luces?').
variable(giro_arranque,          electrico,   sintoma,        'Giro del motor al arrancar',         'Al accionar el arranque, ¿cómo gira el motor?').
variable(clic_arranque,          electrico,   sintoma,        'Clic al arrancar',                   '¿Se escucha un clic al intentar arrancar?').
variable(falla_intermitente,     electrico,   sintoma,        'Falla eléctrica intermitente',       '¿La falla eléctrica aparece y desaparece (es intermitente)?').
variable(bornes,                 electrico,   revision,       'Bornes de batería',                  '¿Cómo se ven los bornes de la batería?').
variable(fusible,                electrico,   revision,       'Fusible principal',                  '¿En qué estado está el fusible principal?').
variable(voltaje,                electrico,   prueba_tecnica, 'Voltaje en reposo',                  'Voltaje de la batería en reposo, si ya fue medido (en V)').
variable(dificultad_arranque,    motor,       sintoma,        'Dificultad para encender',           '¿Cuesta que el motor encienda? (persistente = casi siempre, o no enciende)').
variable(se_apaga_ralenti,       motor,       sintoma,        'Se apaga en ralentí',                '¿El motor se apaga cuando queda en ralentí?').
variable(ralenti_inestable,      motor,       sintoma,        'Ralentí inestable',                  '¿El ralentí es inestable?').
variable(tirones,                motor,       sintoma,        'Tirones al acelerar',                '¿Presenta tirones durante la aceleración?').
variable(perdida_potencia,       motor,       sintoma,        'Pérdida de potencia',                '¿Ha notado pérdida de potencia?').
variable(sobrecalentamiento,     motor,       sintoma,        'Sobrecalentamiento',                 '¿Hay señales de sobrecalentamiento del motor?').
variable(humo,                   motor,       sintoma,        'Humo en el escape',                  '¿Qué tipo de humo sale por el escape?').
variable(ruidos_anormales,       motor,       sintoma,        'Ruidos anormales',                   '¿Escucha ruidos anormales en el motor?').
variable(olor_gasolina,          combustible, sintoma,        'Olor a gasolina',                    '¿Percibe un olor anormal o persistente a gasolina?').
variable(fuga_combustible,       combustible, sintoma,        'Fuga de combustible',                '¿Ve fugas de combustible?').
variable(vacios_aceleracion,     combustible, sintoma,        'Ahogos o vacíos al acelerar',        '¿El motor se ahoga o tiene vacíos al acelerar?').
variable(combustible_viejo,      combustible, dato,           'Combustible almacenado mucho tiempo','¿El combustible del tanque lleva almacenado un tiempo prolongado?').
variable(filtro_aire,            combustible, revision,       'Filtro de aire',                     '¿En qué estado está el filtro de aire?').
variable(bujia,                  encendido,   revision,       'Estado de la bujía',                 'Estado de la bujía, según una revisión previa').
variable(chispa,                 encendido,   prueba_tecnica, 'Prueba de chispa',                   'Resultado de la prueba de chispa realizada por un técnico').
variable(compresion,             encendido,   prueba_tecnica, 'Prueba de compresión',               'Resultado de la prueba de compresión realizada por un técnico').

% -------------------------------------------------------------------------
% 1.3 opciones(Variable, ListaDeValores): valores admitidos.
%     Todas las variables admiten 'desconocido' (valor unificado que
%     reemplaza a "no revisado", "no medido", "no comprobada", etc.).
% -------------------------------------------------------------------------
opciones(cilindrada,             [desconocido]).
opciones(alimentacion,           [carburador, inyeccion, desconocido]).
opciones(condicion_motor,        [frio, caliente, ambos, desconocido]).
opciones(tiempo_sin_uso,         [dias, semanas, meses, desconocido]).
opciones(nivel_combustible,      [vacio, bajo, medio, alto, desconocido]).
opciones(interruptor_paro,       [marcha, paro, desconocido]).
opciones(mantenimiento_reciente, [si, no, desconocido]).
opciones(tablero,                [si, no, desconocido]).
opciones(luces,                  [normal, debil, apagadas, desconocido]).
opciones(giro_arranque,          [normal, lento, no_gira, desconocido]).
opciones(clic_arranque,          [si, no, desconocido]).
opciones(falla_intermitente,     [si, no, desconocido]).
opciones(bornes,                 [normal, sulfatados, flojos, desconocido]).
opciones(fusible,                [bueno, fundido, desconocido]).
opciones(voltaje,                [desconocido]).
opciones(dificultad_arranque,    [no, ocasional, persistente, desconocido]).
opciones(se_apaga_ralenti,       [si, no, desconocido]).
opciones(ralenti_inestable,      [si, no, desconocido]).
opciones(tirones,                [si, no, desconocido]).
opciones(perdida_potencia,       [si, no, desconocido]).
opciones(sobrecalentamiento,     [si, no, desconocido]).
opciones(humo,                   [ninguno, blanco, azul, negro, desconocido]).
opciones(ruidos_anormales,       [si, no, desconocido]).
opciones(olor_gasolina,          [si, no, desconocido]).
opciones(fuga_combustible,       [si, no, desconocido]).
opciones(vacios_aceleracion,     [si, no, desconocido]).
opciones(combustible_viejo,      [si, no, desconocido]).
opciones(filtro_aire,            [limpio, sucio, desconocido]).
opciones(bujia,                  [normal, carbonizada, humeda, desgastada, desconocido]).
opciones(chispa,                 [adecuada, debil, ausente, desconocido]).
opciones(compresion,             [normal, baja, desconocido]).

% -------------------------------------------------------------------------
% 1.4 rango_numerico(Variable, Minimo, Maximo): variables numéricas y
%     rango aceptado como dato válido (no como rango "normal").
% -------------------------------------------------------------------------
rango_numerico(cilindrada, 30, 2000).
rango_numerico(voltaje,    0,  20).

% -------------------------------------------------------------------------
% 1.5 parametro(Nombre, Valor): parámetros de configuración.
%     voltaje_minimo_normal: valor de referencia general para una
%     batería de 12 V en reposo. PENDIENTE de validar con el manual
%     de servicio o el experto consultado.
% -------------------------------------------------------------------------
parametro(voltaje_minimo_normal, 12.4).
parametro(max_preguntas,         25).
parametro(cilindrada_minima,     100).
parametro(cilindrada_maxima,     250).
parametro(max_sugerencias,       5).

% -------------------------------------------------------------------------
% 1.6 diagnostico(Codigo, Nombre, Subsistema, Rama)
%     Rama: electrica (el problema impide o debilita el giro) o
%     motor (el motor gira, pero no enciende o funciona mal).
% -------------------------------------------------------------------------
diagnostico(d01, 'Batería descargada o debilitada',                 'Batería',                      electrica).
diagnostico(d02, 'Conexiones deficientes de batería',               'Bornes y terminales',          electrica).
diagnostico(d03, 'Interrupción en circuito eléctrico principal',    'Circuito principal y fusible', electrica).
diagnostico(d04, 'Posible falla del relé o motor de arranque',      'Sistema de arranque',          electrica).
diagnostico(d05, 'Bujía deteriorada o contaminada',                 'Encendido - bujía',            motor).
diagnostico(d06, 'Posible falla de bobina o circuito de encendido', 'Encendido - bobina y cables',  motor).
diagnostico(d07, 'Suministro insuficiente o combustible deteriorado','Alimentación de combustible', motor).
diagnostico(d08, 'Carburador obstruido o desajustado',              'Carburador',                   motor).
diagnostico(d09, 'Filtro de aire obstruido',                        'Admisión de aire',             motor).
diagnostico(d10, 'Posible compresión insuficiente',                 'Motor - parte mecánica',       motor).

% -------------------------------------------------------------------------
% 1.7 alerta(Codigo, Nombre, Subsistema): alertas de seguridad.
%     No requieren respaldo: una sola señal basta para emitirlas.
% -------------------------------------------------------------------------
alerta(a01, 'Posible fuga de combustible',        'Sistema de combustible').
alerta(a02, 'Señales de sobrecalentamiento',      'Motor y refrigeración').
alerta(a03, 'Indicios de posible daño mecánico',  'Motor - parte mecánica').

% -------------------------------------------------------------------------
% 1.8 disparador_alerta(Alerta, Variable, Valor): señal que activa la alerta.
% -------------------------------------------------------------------------
disparador_alerta(a01, fuga_combustible,   si).
disparador_alerta(a01, olor_gasolina,      si).
disparador_alerta(a02, sobrecalentamiento, si).
disparador_alerta(a03, ruidos_anormales,   si).
disparador_alerta(a03, humo,               azul).

% -------------------------------------------------------------------------
% 1.9 verificacion_basica(Codigo, Nombre, Subsistema, Condiciones)
%     Causas simples que el usuario puede resolver sin herramientas.
%     Condiciones es una lista Variable-Valor que debe cumplirse completa.
% -------------------------------------------------------------------------
verificacion_basica(v01, 'Interruptor de apagado del motor en OFF', 'Mandos',                  [interruptor_paro-paro]).
verificacion_basica(v02, 'Tanque sin combustible',                  'Combustible',             [nivel_combustible-vacio]).

% -------------------------------------------------------------------------
% 1.10 prioridad_base(Codigo, Nivel): prioridad inicial (1 a 4) antes de
%      aplicar los modificadores. Justificación en la propuesta revisada.
% -------------------------------------------------------------------------
prioridad_base(a01, 4).
prioridad_base(a02, 3).
prioridad_base(a03, 3).
prioridad_base(v01, 1).
prioridad_base(v02, 1).
prioridad_base(d01, 2).
prioridad_base(d02, 2).
prioridad_base(d03, 3).
prioridad_base(d04, 3).
prioridad_base(d05, 2).
prioridad_base(d06, 3).
prioridad_base(d07, 2).
prioridad_base(d08, 2).
prioridad_base(d09, 1).
prioridad_base(d10, 3).

% -------------------------------------------------------------------------
% 1.11 nivel_prioridad(Nivel, Etiqueta, AccionRecomendada)
% -------------------------------------------------------------------------
nivel_prioridad(1, 'Baja',    'Programar revisión o mantenimiento.').
nivel_prioridad(2, 'Media',   'Revisar antes de continuar con el uso regular.').
nivel_prioridad(3, 'Alta',    'Evitar usar la motocicleta hasta obtener revisión.').
nivel_prioridad(4, 'Crítica', 'Detenerse de forma segura y solicitar ayuda especializada.').

% -------------------------------------------------------------------------
% 1.12 evidencia(Diagnostico, Variable, Valor): síntoma u observación que
%      respalda la hipótesis (evidencia a favor, no confirmatoria).
% -------------------------------------------------------------------------
evidencia(d01, giro_arranque,       lento).
evidencia(d01, luces,               debil).
evidencia(d01, giro_arranque,       no_gira).
evidencia(d01, clic_arranque,       si).
evidencia(d01, tiempo_sin_uso,      meses).
evidencia(d02, giro_arranque,       lento).
evidencia(d02, luces,               debil).
evidencia(d02, falla_intermitente,  si).
evidencia(d03, tablero,             no).
evidencia(d03, luces,               apagadas).
evidencia(d03, giro_arranque,       no_gira).
evidencia(d04, clic_arranque,       si).
evidencia(d04, giro_arranque,       no_gira).
evidencia(d04, tablero,             si).
evidencia(d04, luces,               normal).
evidencia(d05, dificultad_arranque, ocasional).
evidencia(d05, dificultad_arranque, persistente).
evidencia(d05, condicion_motor,     frio).
evidencia(d05, ralenti_inestable,   si).
evidencia(d05, tirones,             si).
evidencia(d06, dificultad_arranque, persistente).
evidencia(d06, condicion_motor,     caliente).
evidencia(d07, dificultad_arranque, persistente).
evidencia(d07, perdida_potencia,    si).
evidencia(d07, se_apaga_ralenti,    si).
evidencia(d07, nivel_combustible,   bajo).
evidencia(d07, tiempo_sin_uso,      meses).
evidencia(d08, ralenti_inestable,   si).
evidencia(d08, tirones,             si).
evidencia(d08, vacios_aceleracion,  si).
evidencia(d08, se_apaga_ralenti,    si).
evidencia(d08, humo,                negro).
evidencia(d09, perdida_potencia,    si).
evidencia(d09, humo,                negro).
evidencia(d10, dificultad_arranque, persistente).
evidencia(d10, perdida_potencia,    si).
evidencia(d10, humo,                azul).
evidencia(d10, ruidos_anormales,    si).

% -------------------------------------------------------------------------
% 1.13 verificacion(Diagnostico, Variable, Valor): verificación específica
%      a favor (revisión o prueba). Necesaria para el respaldo Alto.
%      Para d01 el valor 'bajo' es un estado derivado del voltaje numérico.
% -------------------------------------------------------------------------
verificacion(d01, voltaje,           bajo).
verificacion(d02, bornes,            sulfatados).
verificacion(d02, bornes,            flojos).
verificacion(d03, fusible,           fundido).
verificacion(d05, bujia,             carbonizada).
verificacion(d05, bujia,             humeda).
verificacion(d05, bujia,             desgastada).
verificacion(d06, chispa,            ausente).
verificacion(d06, chispa,            debil).
verificacion(d07, combustible_viejo, si).
verificacion(d09, filtro_aire,       sucio).
verificacion(d10, compresion,        baja).

% -------------------------------------------------------------------------
% 1.14 contraevidencia(Diagnostico, Variable, Valor): observación que
%      debilita la hipótesis (no la descarta, pero impide respaldo Medio/Alto).
% -------------------------------------------------------------------------
contraevidencia(d01, luces,         normal).
contraevidencia(d01, giro_arranque, normal).
contraevidencia(d03, tablero,       si).
contraevidencia(d04, giro_arranque, normal).

% -------------------------------------------------------------------------
% 1.15 descarte(Diagnostico, Condiciones): verificación que DESCARTA la
%      hipótesis cuando TODAS las condiciones de la lista están presentes
%      (se comprueba como subconjunto del caso, ver R1.7).
% -------------------------------------------------------------------------
descarte(d01, [voltaje-normal]).
descarte(d02, [bornes-normal]).
descarte(d03, [fusible-bueno, tablero-si]).
descarte(d05, [bujia-normal]).
descarte(d06, [chispa-adecuada]).
descarte(d07, [combustible_viejo-no, nivel_combustible-alto]).
descarte(d07, [combustible_viejo-no, nivel_combustible-medio]).
descarte(d09, [filtro_aire-limpio]).
descarte(d10, [compresion-normal]).

% -------------------------------------------------------------------------
% 1.16 requisito(Diagnostico, Condiciones): condiciones mínimas para que la
%      hipótesis pueda activarse. Si hay varias cláusulas, basta una.
% -------------------------------------------------------------------------
requisito(d04, [clic_arranque-si, giro_arranque-no_gira]).
requisito(d10, [dificultad_arranque-persistente]).
requisito(d10, [compresion-baja]).

% -------------------------------------------------------------------------
% 1.17 compite_con(A, B): hipótesis que explican síntomas parecidos y que
%      el sistema debe diferenciar. Se escribe una sola vez por pareja.
% -------------------------------------------------------------------------
compite_con(d01, d02).
compite_con(d01, d03).
compite_con(d01, d04).
compite_con(d02, d03).
compite_con(d02, d04).
compite_con(d03, d04).
compite_con(d05, d06).
compite_con(d05, d08).
compite_con(d05, d10).
compite_con(d06, d07).
compite_con(d06, d10).
compite_con(d07, d08).
compite_con(d07, d09).
compite_con(d07, d10).
compite_con(d08, d09).

% -------------------------------------------------------------------------
% 1.18 senal_riesgo(Variable, Valor): señales usadas por el criterio
%      "coincidencia de varias señales de riesgo en el mismo caso".
% -------------------------------------------------------------------------
senal_riesgo(fuga_combustible,   si).
senal_riesgo(olor_gasolina,      si).
senal_riesgo(sobrecalentamiento, si).
senal_riesgo(ruidos_anormales,   si).
senal_riesgo(humo,               azul).
senal_riesgo(se_apaga_ralenti,   si).

% -------------------------------------------------------------------------
% 1.19 recomendacion(Codigo, Texto): verificaciones y acciones seguras.
%      Contenido de referencia general, PENDIENTE de validar con fuente.
% -------------------------------------------------------------------------
recomendacion(a01, 'Apagar el motor y no intentar arrancarlo de nuevo.').
recomendacion(a01, 'Alejar fuentes de calor, chispas o llamas; no fumar cerca.').
recomendacion(a01, 'Solicitar asistencia especializada para localizar la fuga.').
recomendacion(a02, 'Detenerse en un lugar seguro y dejar enfriar el motor.').
recomendacion(a02, 'No reanudar la marcha hasta que un técnico revise la lubricación y la refrigeración.').
recomendacion(a03, 'Evitar el uso de la motocicleta: el daño interno puede agravarse.').
recomendacion(a03, 'Solicitar una revisión mecánica del motor.').
recomendacion(v01, 'Pasar el interruptor de apagado a RUN (encendido) y volver a intentar el arranque.').
recomendacion(v02, 'Cargar combustible y volver a intentar el arranque.').
recomendacion(d01, 'Medir el voltaje de la batería en reposo, o pedir la medición a un técnico.').
recomendacion(d01, 'Cargar la batería con un cargador adecuado y volver a probar el arranque.').
recomendacion(d01, 'Si la batería no retiene la carga, revisar la batería y el sistema de carga en un taller.').
recomendacion(d02, 'Con la motocicleta apagada, comprobar que los bornes estén firmes y sin sulfato.').
recomendacion(d02, 'Limpiar el sulfato y ajustar los terminales; al desconectar, retirar primero el negativo.').
recomendacion(d03, 'Revisar visualmente el fusible principal.').
recomendacion(d03, 'Reemplazarlo solo por uno del mismo amperaje; si vuelve a fundirse, un técnico debe buscar el cortocircuito.').
recomendacion(d04, 'Confirmar que la batería está cargada antes de atribuir la falla al relé o al motor de arranque.').
recomendacion(d04, 'Solicitar a un técnico la prueba del relé y del motor de arranque.').
recomendacion(d05, 'Revisar la bujía o pedir su revisión: color, depósitos y desgaste del electrodo.').
recomendacion(d05, 'Reemplazarla por la referencia del manual si está carbonizada, húmeda o desgastada.').
recomendacion(d06, 'Solicitar a un técnico la prueba de chispa y la revisión de bobina, capuchón y cables.').
recomendacion(d06, 'No manipular el sistema de encendido con el motor en marcha (alto voltaje).').
recomendacion(d07, 'Verificar el nivel de combustible y que la llave de paso esté abierta.').
recomendacion(d07, 'Si el combustible lleva mucho tiempo almacenado, reemplazarlo con apoyo de un técnico.').
recomendacion(d08, 'Solicitar limpieza y ajuste del carburador en un taller.').
recomendacion(d08, 'Evitar desarmar el carburador sin experiencia ni herramientas adecuadas.').
recomendacion(d09, 'Inspeccionar el filtro de aire.').
recomendacion(d09, 'Limpiarlo o reemplazarlo según indique el manual de la motocicleta.').
recomendacion(d10, 'Solicitar una prueba de compresión a un técnico.').
recomendacion(d10, 'Evitar el uso prolongado hasta la revisión: puede existir desgaste interno.').

% -------------------------------------------------------------------------
% 1.20 fase_inicial(Variable, Orden, Motivo): preguntas fijas del triaje.
% -------------------------------------------------------------------------
fase_inicial(cilindrada,         1, 'Admisión: confirmar que la motocicleta está dentro del alcance (100 a 250 cc).').
fase_inicial(alimentacion,       2, 'Admisión: el sistema solo cubre motocicletas de carburador.').
fase_inicial(fuga_combustible,   3, 'Seguridad: una fuga de combustible requiere atención inmediata.').
fase_inicial(olor_gasolina,      4, 'Seguridad: el olor persistente a gasolina puede indicar una fuga.').
fase_inicial(sobrecalentamiento, 5, 'Seguridad: el sobrecalentamiento puede dañar el motor.').
fase_inicial(interruptor_paro,   6, 'Verificación básica: si el interruptor de apagado está en OFF, el motor no enciende aunque todo lo demás esté bien.').
fase_inicial(nivel_combustible,  7, 'Verificación básica: sin combustible el motor no enciende.').
fase_inicial(giro_arranque,      8, 'Arranque: según cómo gire el motor, se revisa primero la parte eléctrica o la del motor.').

% -------------------------------------------------------------------------
% 1.21 costo_tipo(TipoVariable, Costo): a igual utilidad, se pregunta
%      primero lo que el usuario puede responder con menos esfuerzo.
% -------------------------------------------------------------------------
costo_tipo(dato,           0).
costo_tipo(sintoma,        0).
costo_tipo(revision,       1).
costo_tipo(prueba_tecnica, 2).

% -------------------------------------------------------------------------
% 1.22 orden_tipo(TipoConclusion, Orden): orden de aparición en el reporte.
% -------------------------------------------------------------------------
orden_tipo(alerta,      0).
orden_tipo(basica,      1).
orden_tipo(diagnostico, 2).

% -------------------------------------------------------------------------
% 1.23 rango_respaldo(Respaldo, Rango): para ordenar en caso de empate.
% -------------------------------------------------------------------------
rango_respaldo(no_aplica, 4).
rango_respaldo(alto,      3).
rango_respaldo(medio,     2).
rango_respaldo(bajo,      1).

% -------------------------------------------------------------------------
% 1.24 texto_valor(Valor, Texto): forma legible de algunos valores
%      (los átomos de Prolog se escriben sin tildes ni espacios).
% -------------------------------------------------------------------------
texto_valor(si,          'sí').
texto_valor(debil,       'débil').
texto_valor(no_gira,     'no gira').
texto_valor(frio,        'frío').
texto_valor(humeda,      'húmeda').
texto_valor(vacio,       'vacío').
texto_valor(inyeccion,   'inyección').
texto_valor(marcha,      'RUN (encendido)').
texto_valor(paro,        'OFF (apagado)').

% -------------------------------------------------------------------------
% 1.25 mensaje_estado(Estado, Mensaje): estado general de la consulta.
% -------------------------------------------------------------------------
mensaje_estado(con_resultados,              'Se encontraron conclusiones con respaldo suficiente o alertas.').
mensaje_estado(datos_insuficientes,         'Hay hipótesis compatibles, pero la información no alcanza para respaldarlas. Responda más preguntas o realice las verificaciones sugeridas.').
mensaje_estado(sin_diagnostico_concluyente, 'Ningún diagnóstico del catálogo es compatible con los datos. Se recomienda una revisión profesional.').
mensaje_estado(fuera_de_alcance,            'La motocicleta está fuera del alcance del sistema. Solo se informan alertas de seguridad.').
mensaje_estado(sin_datos,                   'No se recibieron observaciones válidas. No es posible emitir un diagnóstico.').

% -------------------------------------------------------------------------
% 1.26 valores_derivados(Variable, Valores): valores cualitativos que el
%      sistema deduce de una variable numérica (R1.6). El módulo "¿Qué
%      falta?" los usa para anticipar el efecto de medir la variable.
% -------------------------------------------------------------------------
valores_derivados(voltaje, [bajo, normal]).

% -------------------------------------------------------------------------
% 1.27 peso_efecto(Efecto, Peso): cuánto cambia una hipótesis un dato
%      todavía no ingresado. Confirmar o descartar pesa más que apoyar.
% -------------------------------------------------------------------------
peso_efecto(confirma,            3).
peso_efecto(descarta,            3).
peso_efecto(contradice,          2).
peso_efecto(apoya,               1).
peso_efecto(contribuye_descarte, 1).

% -------------------------------------------------------------------------
% 1.28 texto_efecto(Efecto, Texto): redacción del efecto para el usuario.
% -------------------------------------------------------------------------
texto_efecto(confirma,            'confirmaría').
texto_efecto(descarta,            'descartaría').
texto_efecto(contradice,          'debilitaría').
texto_efecto(apoya,               'apoyaría').
texto_efecto(contribuye_descarte, 'ayudaría a descartar').

% -------------------------------------------------------------------------
% 1.29 mensaje_falta(Situacion, Mensaje): situación de la evidencia que
%      evalúa el módulo "¿Qué falta?".
% -------------------------------------------------------------------------
mensaje_falta(definitivo,       'Hay un dictamen con respaldo Alto. Los datos sugeridos solo servirían para confirmar o descartar las hipótesis restantes.').
mensaje_falta(empate,           'Varias hipótesis tienen el mismo respaldo y ninguna es Alto: hay un empate. El dato sugerido es el que más ayuda a desempatar.').
mensaje_falta(insuficiente,     'Hay una hipótesis destacada, pero su respaldo no es Alto. El dato sugerido es el que más ayuda a confirmarla o descartarla.').
mensaje_falta(sin_hipotesis,    'Ninguna hipótesis tiene todavía evidencia a favor. El dato sugerido es el que más hipótesis compatibles permite evaluar.').
mensaje_falta(fuera_de_alcance, 'La motocicleta está fuera del alcance: no se buscan datos adicionales para diagnosticar.').
mensaje_falta(sin_sugerencias,  'No queda ningún dato del catálogo que cambie el resultado. Se recomienda una revisión profesional.').


/* =========================================================================
   2. NIVEL 1 - VALIDACIÓN PRELIMINAR
   Clasifican los datos de entrada y verifican condiciones elementales.
   ========================================================================= */

% R1.1 valor(+Variable, +Caso, -Valor)
% Devuelve el valor observado de una variable.
% CORTE: una variable tiene un solo valor en el caso; al encontrar la
% primera aparición se impide buscar otras.
% FALLBACK: la segunda cláusula da 'desconocido' cuando no hay dato.
% La unificación con Valor ocurre DESPUÉS del corte, de modo que la
% llamada con Valor ya instanciado tampoco cae por error en el fallback.
valor(Var, Caso, Valor) :-
    memberchk(obs(Var, V0), Caso), !,
    Valor = V0.
valor(_, _, desconocido).

% R1.2 obs_valida(+Observacion)
% Comprueba que la observación tenga la forma obs(Variable, Valor), que
% la variable exista y que el valor sea admitido. Las dos cláusulas son
% mutuamente excluyentes: el CORTE evita reintentar la numérica.
% ground/1 va primero: una variable libre llegada desde Python unificaría
% con la primera opción de memberchk/2 y produciría un dato falso.
obs_valida(Obs) :-
    ground(Obs),
    Obs = obs(Var, Valor),
    atom(Var), atomic(Valor),
    opciones(Var, Ops),
    memberchk(Valor, Ops), !.
obs_valida(Obs) :-
    ground(Obs),
    Obs = obs(Var, Valor),
    atom(Var), number(Valor),
    rango_numerico(Var, Min, Max),
    Valor >= Min, Valor =< Max.

% R1.2b limpiar_obs(+Observacion, -Limpia)
% Pasa a minúscula la variable y el valor cuando son átomos ('Luces' y
% 'Debil' se aceptan como luces y debil). CORTE + FALLBACK: lo que no
% tiene la forma obs/2 se devuelve igual y obs_valida/1 lo rechaza.
limpiar_obs(obs(V0, X0), Limpia) :- !,
    minuscula(V0, V),
    minuscula(X0, X),
    Limpia = obs(V, X).
limpiar_obs(O, O).

minuscula(A, B) :- atom(A), !, downcase_atom(A, B).
minuscula(X, X).

% R1.3 particionar_obs(+Lista, -Validas, -Invalidas)
% Recorre la lista enviada por Python y separa elementos válidos (ya
% limpios) e inválidos (tal como llegaron, para informarlos).
% CORTE: las cláusulas 2 y 3 son mutuamente excluyentes.
particionar_obs([], [], []).
particionar_obs([O|Resto], [L|V], I) :-
    limpiar_obs(O, L),
    obs_valida(L), !,
    particionar_obs(Resto, V, I).
particionar_obs([O|Resto], V, [O|I]) :-
    particionar_obs(Resto, V, I).

% R1.4 quitar_repetidas(+Lista, +VistasAcum, -SinRepetir)
% Conserva solo la primera observación de cada variable.
% CORTE: si la variable ya se vio, se descarta y no se prueba la cláusula 3.
quitar_repetidas([], _, []).
quitar_repetidas([obs(Var, _)|Resto], Vistas, Salida) :-
    memberchk(Var, Vistas), !,
    quitar_repetidas(Resto, Vistas, Salida).
quitar_repetidas([obs(Var, Val)|Resto], Vistas, [obs(Var, Val)|Salida]) :-
    quitar_repetidas(Resto, [Var|Vistas], Salida).

% R1.5 normalizar_caso(+ListaPython, -Caso)
% Filtra elementos inválidos y repetidos. Todas las consultas públicas
% trabajan sobre el caso normalizado.
normalizar_caso(Lista, Caso) :-
    is_list(Lista), !,
    particionar_obs(Lista, Validas, _),
    quitar_repetidas(Validas, [], Caso).
normalizar_caso(_, []).                       % fallback: entrada que no es lista

% R1.6 voltaje_estado(+Caso, -Estado)
% Clasifica el voltaje numérico en bajo / normal / desconocido.
% CORTE: clasificaciones mutuamente excluyentes; FALLBACK: desconocido.
voltaje_estado(Caso, Estado) :-
    valor(voltaje, Caso, V), number(V),
    parametro(voltaje_minimo_normal, Min),
    V < Min, !,
    Estado = bajo.
voltaje_estado(Caso, Estado) :-
    valor(voltaje, Caso, V), number(V), !,
    Estado = normal.
voltaje_estado(_, desconocido).

% R1.7 hecho_caso(+Caso, +Variable, ?Valor)
% Acceso uniforme a los hechos del caso: para el voltaje entrega el
% estado derivado (bajo/normal); para el resto, el valor observado.
% Variable debe llegar instanciada (todas las llamadas la toman de un hecho).
hecho_caso(Caso, voltaje, Estado) :-
    voltaje_estado(Caso, Estado).
hecho_caso(Caso, Var, Valor) :-
    Var \== voltaje,
    valor(Var, Caso, Valor).

% R1.8 cumple_todas(+Caso, +Condiciones)
% PROCESAMIENTO DE LISTAS: verifica que la lista de condiciones
% Variable-Valor sea un subconjunto de los hechos del caso.
cumple_todas(_, []).
cumple_todas(Caso, [Var-Val|Resto]) :-
    hecho_caso(Caso, Var, Val),
    cumple_todas(Caso, Resto).

% R1.9 contar_cumplidas(+Caso, +Condiciones, -N)
% PROCESAMIENTO DE LISTAS: cuenta cuántas condiciones se cumplen.
% CORTE: la condición se cumple o no (cláusulas 2 y 3 excluyentes).
contar_cumplidas(_, [], 0).
contar_cumplidas(Caso, [Var-Val|Resto], N) :-
    hecho_caso(Caso, Var, Val), !,
    contar_cumplidas(Caso, Resto, N0),
    N is N0 + 1.
contar_cumplidas(Caso, [_|Resto], N) :-
    contar_cumplidas(Caso, Resto, N).

% R1.10 fuera_de_alcance(+Caso, -Motivo)
% La motocicleta no pertenece al dominio del sistema.
fuera_de_alcance(Caso, Motivo) :-
    hecho_caso(Caso, cilindrada, C), number(C),
    parametro(cilindrada_minima, Min),
    parametro(cilindrada_maxima, Max),
    ( C < Min ; C > Max ),
    format(atom(Motivo), 'Cilindrada de ~w cc fuera del rango ~w a ~w cc.', [C, Min, Max]).
fuera_de_alcance(Caso, 'Motocicleta con inyección electrónica (excluida del alcance).') :-
    hecho_caso(Caso, alimentacion, inyeccion).

% R1.11 senales_riesgo_caso(+Caso, -Senales)
% Lista de señales de riesgo presentes en el caso.
senales_riesgo_caso(Caso, Senales) :-
    findall(Var-Val,
            ( senal_riesgo(Var, Val), hecho_caso(Caso, Var, Val) ),
            Senales).

% R1.12 valor_legible(+Valor, -Texto)
% CORTE + FALLBACK: si hay forma legible se usa; si no, el mismo valor.
valor_legible(Val, Texto) :-
    texto_valor(Val, T), !,
    Texto = T.
valor_legible(Val, Val).

% R1.13 describir_hecho(+Caso, +Variable-Valor, -Texto)
% Texto legible de una observación, para las explicaciones.
describir_hecho(Caso, voltaje-Estado, Texto) :-
    valor(voltaje, Caso, V), number(V), !,
    variable(voltaje, _, _, Etiqueta, _),
    format(atom(Texto), '~w: ~w (~w V)', [Etiqueta, Estado, V]).
describir_hecho(_, Var-Val, Texto) :-
    variable(Var, _, _, Etiqueta, _), !,
    valor_legible(Val, Legible),
    format(atom(Texto), '~w: ~w', [Etiqueta, Legible]).
describir_hecho(_, Var-Val, Texto) :-
    format(atom(Texto), '~w: ~w', [Var, Val]).


/* =========================================================================
   3. NIVEL 2 - INFERENCIA INTERMEDIA
   Combinan reglas de Nivel 1 y hechos para deducir estados intermedios.
   ========================================================================= */

% R2.1 estado_alimentacion(+Caso, -Estado)
% Conclusión intermedia sobre la alimentación eléctrica disponible:
% ausente / debil / disponible / desconocida.
% CORTE: estados mutuamente excluyentes evaluados en orden de gravedad.
% FALLBACK: 'desconocida' si ninguna condición se cumple.
estado_alimentacion(Caso, Estado) :-
    hecho_caso(Caso, tablero, no),
    hecho_caso(Caso, luces, apagadas), !,
    Estado = ausente.
estado_alimentacion(Caso, Estado) :-
    ( hecho_caso(Caso, luces, debil) ; hecho_caso(Caso, voltaje, bajo) ), !,
    Estado = debil.
estado_alimentacion(Caso, Estado) :-
    hecho_caso(Caso, tablero, si),
    ( hecho_caso(Caso, luces, normal) ; hecho_caso(Caso, voltaje, normal) ), !,
    Estado = disponible.
estado_alimentacion(_, desconocida).

% R2.2 excluida(+Caso, +Diagnostico, -Motivo)
% Criterios de EXCLUSIÓN: condiciones que hacen incompatible una hipótesis
% aunque tenga síntomas a favor. Se usan con NEGACIÓN POR FALLO en R2.10.
excluida(Caso, Cod, 'El motor no gira: se evalúa primero el sistema eléctrico.') :-
    diagnostico(Cod, _, _, motor),
    hecho_caso(Caso, giro_arranque, no_gira).
excluida(Caso, d04, Motivo) :-
    estado_alimentacion(Caso, Estado),
    memberchk(Estado, [debil, ausente]),
    valor_legible(Estado, Legible),
    format(atom(Motivo), 'La alimentación eléctrica es ~w: la causa probable es la batería o el circuito, no el arranque.', [Legible]).
excluida(Caso, d06, 'El interruptor de apagado está en OFF: eso explica que el motor no encienda.') :-
    hecho_caso(Caso, interruptor_paro, paro).
excluida(Caso, d07, 'El tanque está vacío: la causa ya está identificada (verificación básica).') :-
    hecho_caso(Caso, nivel_combustible, vacio).

% R2.3 descartada(+Caso, +Diagnostico, -Motivo)
% Una verificación en contra descarta la hipótesis. Usa la comprobación
% de subconjunto de listas (R1.8).
descartada(Caso, Cod, Motivo) :-
    descarte(Cod, Condiciones),
    cumple_todas(Caso, Condiciones),
    findall(T, ( member(C, Condiciones), describir_hecho(Caso, C, T) ), Textos),
    atomic_list_concat(Textos, '; ', Detalle),
    format(atom(Motivo), 'Descartada por verificación: ~w.', [Detalle]).

% R2.4 evidencias_favor(+Caso, +Diagnostico, -Lista)
% Lista ordenada y sin duplicados de síntomas y verificaciones a favor.
evidencias_favor(Caso, Cod, Lista) :-
    findall(Var-Val,
            ( ( evidencia(Cod, Var, Val) ; verificacion(Cod, Var, Val) ),
              hecho_caso(Caso, Var, Val) ),
            L0),
    sort(L0, Lista).

% R2.5 verificacion_favor(+Caso, +Diagnostico)
% Existe al menos una verificación específica a favor.
% CORTE: basta con una (evita soluciones repetidas).
verificacion_favor(Caso, Cod) :-
    verificacion(Cod, Var, Val),
    hecho_caso(Caso, Var, Val), !.

% R2.6 contraevidencias(+Caso, +Diagnostico, -Lista)
contraevidencias(Caso, Cod, Lista) :-
    findall(Var-Val,
            ( contraevidencia(Cod, Var, Val), hecho_caso(Caso, Var, Val) ),
            L0),
    sort(L0, Lista).

% R2.7 cumple_requisito(+Caso, +Diagnostico)
% Si el diagnóstico tiene requisitos mínimos, al menos una lista debe
% cumplirse completa. CORTE + NEGACIÓN: la primera cláusula cubre los
% diagnósticos sin requisitos (Cod instanciado dentro de \+).
cumple_requisito(_, Cod) :-
    \+ requisito(Cod, _), !.
cumple_requisito(Caso, Cod) :-
    requisito(Cod, Condiciones),
    cumple_todas(Caso, Condiciones), !.

% R2.8 competidoras(?A, ?B)
% Relación simétrica construida SIN recursión, para evitar ciclos.
competidoras(A, B) :- compite_con(A, B).
competidoras(A, B) :- compite_con(B, A).

% R2.9 competidoras_descartadas(+Caso, +Diagnostico)
% Todas las hipótesis competidoras están descartadas por verificación.
% Permite respaldo Alto a diagnósticos sin verificación propia (d04, d08).
competidoras_descartadas(Caso, Cod) :-
    findall(C, competidoras(Cod, C), Cs0),
    sort(Cs0, Cs),
    Cs \== [],
    todas_descartadas(Caso, Cs).

todas_descartadas(_, []).
todas_descartadas(Caso, [C|Resto]) :-
    descartada(Caso, C, _), !,
    todas_descartadas(Caso, Resto).

% R2.10 compatible(+Caso, ?Diagnostico)
% Hipótesis no descartada ni excluida.
% NEGACIÓN POR FALLO: Caso y Cod están instanciados antes de cada \+.
compatible(Caso, Cod) :-
    diagnostico(Cod, _, _, _),
    \+ descartada(Caso, Cod, _),
    \+ excluida(Caso, Cod, _).

% R2.11 hipotesis_activa(+Caso, ?Diagnostico)
% Compatible, con sus requisitos cumplidos y al menos una evidencia a favor.
hipotesis_activa(Caso, Cod) :-
    compatible(Caso, Cod),
    cumple_requisito(Caso, Cod),
    evidencias_favor(Caso, Cod, Lista),
    Lista \== [].

% R2.12 perfil(+Codigo, -Condiciones)
% Lista de condiciones Variable-Valor que respaldan una conclusión:
% evidencias y verificaciones (diagnósticos), disparadores (alertas) o
% condiciones (verificaciones básicas).
perfil(Cod, Condiciones) :-
    diagnostico(Cod, _, _, _), !,
    findall(V-X, ( evidencia(Cod, V, X) ; verificacion(Cod, V, X) ), Condiciones).
perfil(Cod, Condiciones) :-
    alerta(Cod, _, _), !,
    findall(V-X, disparador_alerta(Cod, V, X), Condiciones).
perfil(Cod, Condiciones) :-
    verificacion_basica(Cod, _, _, Condiciones).

% R2.13 coincidencia(+Caso, +Codigo, -Cumplidas, -Variables)
% Cuenta (R1.9) cuántas condiciones del perfil se cumplen y sobre cuántas
% variables distintas está definido el perfil.
coincidencia(Caso, Cod, Cumplidas, NumVars) :-
    perfil(Cod, Condiciones),
    contar_cumplidas(Caso, Condiciones, Cumplidas),
    findall(V, member(V-_, Condiciones), Vs0),
    sort(Vs0, Vs),
    length(Vs, NumVars).

% R2.14 respaldo(+Caso, +Diagnostico, -Nivel, -Justificacion)
% Nivel cualitativo de respaldo (alto / medio / bajo).
respaldo(Caso, Cod, Nivel, Justificacion) :-
    coincidencia(Caso, Cod, N, _),
    contraevidencias(Caso, Cod, Contra),
    clasificar_respaldo(Caso, Cod, N, Contra, Nivel, Justificacion).

% R2.15 clasificar_respaldo/6
% CORTE: reglas mutuamente excluyentes evaluadas de mayor a menor nivel.
% FALLBACK: la última cláusula asigna 'bajo'.
clasificar_respaldo(Caso, Cod, N, [], Nivel, J) :-
    N >= 2, verificacion_favor(Caso, Cod), !,
    Nivel = alto,
    J = 'Alto: varias evidencias concordantes y al menos una verificación específica a favor.'.
clasificar_respaldo(Caso, Cod, N, [], Nivel, J) :-
    N >= 2, competidoras_descartadas(Caso, Cod), !,
    Nivel = alto,
    J = 'Alto: varias evidencias concordantes y todas las hipótesis competidoras descartadas por verificación.'.
clasificar_respaldo(_, _, N, [], Nivel, J) :-
    N >= 2, !,
    Nivel = medio,
    J = 'Medio: síntomas compatibles, pero falta una verificación que diferencie la causa.'.
clasificar_respaldo(Caso, Cod, _, [], Nivel, J) :-
    verificacion_favor(Caso, Cod), !,
    Nivel = medio,
    J = 'Medio: verificación a favor, pero sin otros síntomas concordantes.'.
clasificar_respaldo(_, _, _, Contra, Nivel, J) :-
    Contra \== [], !,
    Nivel = bajo,
    J = 'Bajo: existen evidencias en contra de la hipótesis.'.
clasificar_respaldo(_, _, _, _, bajo, 'Bajo: información escasa; la hipótesis necesita verificaciones adicionales.').

% R2.16 alerta_activa(+Caso, ?Alerta, -Disparadores)
alerta_activa(Caso, Cod, Disparadores) :-
    alerta(Cod, _, _),
    findall(Var-Val,
            ( disparador_alerta(Cod, Var, Val), hecho_caso(Caso, Var, Val) ),
            Disparadores),
    Disparadores \== [].

% R2.17 basica_activa(+Caso, ?Codigo, -Condiciones)
basica_activa(Caso, Cod, Condiciones) :-
    verificacion_basica(Cod, _, _, Condiciones),
    cumple_todas(Caso, Condiciones).

/* =========================================================================
   4. NIVEL 3 - CONCLUSIONES, PRIORIDAD Y RECOLECCIÓN
   Integran las reglas intermedias para producir el resultado final.
   ========================================================================= */

% R3.1 elevacion(+Caso, +Codigo, -Razon): criterios para ELEVAR la prioridad.
%   E1 (alertas): coinciden dos o más señales de riesgo en el caso.
%   E2 (diagnósticos con el síntoma "se apaga en ralentí"): riesgo de
%      detención inesperada del motor durante la marcha.
%   E3 (d10): manifestaciones compatibles con daño mecánico progresivo.
elevacion(Caso, Cod, Razon) :-                                 % E1
    alerta(Cod, _, _),
    senales_riesgo_caso(Caso, S),
    length(S, N), N >= 2,
    format(atom(Razon), '+1: coinciden ~w señales de riesgo en el caso.', [N]).
elevacion(Caso, Cod, '+1: la falla puede causar detención inesperada del motor (se apaga en ralentí).') :-        % E2
    diagnostico(Cod, _, _, _),
    evidencia(Cod, se_apaga_ralenti, si),
    hecho_caso(Caso, se_apaga_ralenti, si).
elevacion(Caso, d10, '+1: manifestaciones compatibles con daño mecánico progresivo (ruidos o humo azul).') :-       % E3
    ( hecho_caso(Caso, ruidos_anormales, si) ; hecho_caso(Caso, humo, azul) ), !.

% R3.2 reduccion(+Caso, +Codigo, -Razon): criterios para REDUCIR la prioridad.
% Solo para diagnósticos y nunca si hay señales de riesgo.
% Ninguna regla reduce la prioridad porque la motocicleta "todavía funciona".
reduccion(Caso, Cod, '-1: mantenimiento al día y sin señales de riesgo.') :-                                     % R1
    diagnostico(Cod, _, _, _),
    hecho_caso(Caso, mantenimiento_reciente, si),
    senales_riesgo_caso(Caso, []).
reduccion(Caso, Cod, '-1: una verificación segura (compresión normal, sin ruidos) descarta daño mecánico grave.') :- % R2
    diagnostico(Cod, _, _, motor),
    Cod \== d10,
    hecho_caso(Caso, compresion, normal),
    hecho_caso(Caso, ruidos_anormales, no),
    senales_riesgo_caso(Caso, []).

% R3.3 acotar(+N, +Min, +Max, -Acotado)
% CORTE: tres casos mutuamente excluyentes.
acotar(N, Min, _, Min) :- N < Min, !.
acotar(N, _, Max, Max) :- N > Max, !.
acotar(N, _, _, N).

% R3.4 prioridad(+Caso, +Codigo, -Nivel, -Etiqueta, -Accion, -Razones)
% Prioridad = base + elevaciones - reducciones, acotada entre 1 y 4.
prioridad(Caso, Cod, Nivel, Etiqueta, Accion, [RazonBase|Razones]) :-
    prioridad_base(Cod, Base),
    findall(R, elevacion(Caso, Cod, R), Elev),
    findall(R, reduccion(Caso, Cod, R), Red),
    length(Elev, NE),
    length(Red, NR),
    N0 is Base + NE - NR,
    acotar(N0, 1, 4, Nivel),
    nivel_prioridad(Base, EtqBase, _),
    format(atom(RazonBase), 'Prioridad base: ~w (~w).', [Base, EtqBase]),
    append(Elev, Red, Razones),
    nivel_prioridad(Nivel, Etiqueta, Accion).

% R3.5 avisos(+Tipo, +Nivel, +Respaldo, -Avisos)
% Indicaciones expresas de evidencia insuficiente o atención profesional.
avisos(Tipo, Nivel, Respaldo, Avisos) :-
    findall(A, aviso(Tipo, Nivel, Respaldo, A), Avisos).

aviso(_, Nivel, _, 'Requiere atención profesional antes de seguir usando la motocicleta.') :-
    Nivel >= 3.
aviso(diagnostico, _, bajo, 'Evidencia insuficiente: es una hipótesis por confirmar, no un diagnóstico.').
aviso(_, _, _, 'Diagnóstico preliminar: no sustituye la evaluación de un profesional.').

% R3.6 conclusion(+Caso, -Clave-Resultado)
% Construye cada conclusión posible del caso. Tres cláusulas: alertas,
% verificaciones básicas y diagnósticos. Las básicas y los diagnósticos se
% omiten (NEGACIÓN POR FALLO) cuando la motocicleta está fuera de alcance;
% las alertas de seguridad se conservan siempre.
%
% Resultado = [Tipo, Codigo, Nombre, Subsistema, Respaldo, JustRespaldo,
%              Prioridad, EtiquetaPrioridad, AccionPrioridad, Evidencias,
%              EvidenciasEnContra, RazonesPrioridad, Recomendaciones, Avisos,
%              Coincidencia]
conclusion(Caso, Clave-Resultado) :-
    alerta_activa(Caso, Cod, Disparadores),
    alerta(Cod, Nombre, Sub),
    Respaldo = no_aplica,
    JR = 'Las alertas de seguridad no dependen del respaldo: una señal basta.',
    armar_resultado(Caso, alerta, Cod, Nombre, Sub, Respaldo, JR, Disparadores, [], Clave, Resultado).
conclusion(Caso, Clave-Resultado) :-
    \+ fuera_de_alcance(Caso, _),
    basica_activa(Caso, Cod, Condiciones),
    verificacion_basica(Cod, Nombre, Sub, _),
    JR = 'Alto: observación directa del usuario que explica la falla.',
    armar_resultado(Caso, basica, Cod, Nombre, Sub, alto, JR, Condiciones, [], Clave, Resultado).
conclusion(Caso, Clave-Resultado) :-
    \+ fuera_de_alcance(Caso, _),
    hipotesis_activa(Caso, Cod),
    diagnostico(Cod, Nombre, Sub, _),
    respaldo(Caso, Cod, Respaldo, JR),
    evidencias_favor(Caso, Cod, Favor),
    contraevidencias(Caso, Cod, Contra),
    armar_resultado(Caso, diagnostico, Cod, Nombre, Sub, Respaldo, JR, Favor, Contra, Clave, Resultado).

% R3.7 armar_resultado/11: completa prioridad, textos y clave de orden.
armar_resultado(Caso, Tipo, Cod, Nombre, Sub, Respaldo, JR, Favor, Contra,
                k(OT, NegP, NegR, Cod),
                [Tipo, Cod, Nombre, Sub, Respaldo, JR, Nivel, Etq, Accion,
                 TxtFavor, TxtContra, Razones, Recs, Avisos, TxtCoinc]) :-
    prioridad(Caso, Cod, Nivel, Etq, Accion, Razones),
    coincidencia(Caso, Cod, NC, NV),
    format(atom(TxtCoinc), 'condiciones cumplidas: ~w; variables del perfil: ~w', [NC, NV]),
    findall(T, ( member(H, Favor),  describir_hecho(Caso, H, T) ), TxtFavor),
    findall(T, ( member(H, Contra), describir_hecho(Caso, H, T) ), TxtContra),
    findall(R, recomendacion(Cod, R), Recs),
    avisos(Tipo, Nivel, Respaldo, Avisos),
    orden_tipo(Tipo, OT),
    rango_respaldo(Respaldo, RR),
    NegP is -Nivel,
    NegR is -RR.

% R3.8 diagnosticar_todos(+ListaObs, -Resultados)
% PREDICADO PRINCIPAL DE RECOLECCIÓN. Usa setof/3 para reunir en una
% sola lista todas las conclusiones, sin duplicados y ordenadas por:
% tipo (alertas, básicas, diagnósticos) > prioridad > respaldo > código.
% setof/3 falla si no hay soluciones: la segunda rama devuelve [].
diagnosticar_todos(Lista, Resultados) :-
    normalizar_caso(Lista, Caso),
    (   setof(Par, conclusion(Caso, Par), Pares)
    ->  pares_a_valores(Pares, Resultados)
    ;   Resultados = []
    ).

pares_a_valores([], []).
pares_a_valores([_-V|Resto], [V|Vs]) :-
    pares_a_valores(Resto, Vs).

% R3.9 codigos_diagnostico(+ListaObs, -Codigos)
% Versión resumida: solo los códigos, sin duplicados (setof con ^).
codigos_diagnostico(Lista, Codigos) :-
    normalizar_caso(Lista, Caso),
    (   setof(Cod, codigo_conclusion(Caso, Cod), Codigos)
    ->  true
    ;   Codigos = []
    ).

% Predicado auxiliar: así setof/3 no agrupa por variables libres.
codigo_conclusion(Caso, Cod) :-
    conclusion(Caso, _-[_, Cod|_]).

% R3.10 hipotesis_descartadas(+ListaObs, -Lista)
% Hipótesis con evidencia a favor que fueron descartadas o excluidas, con
% su motivo. Forman parte de la explicación del razonamiento.
hipotesis_descartadas(Lista, Descartadas) :-
    normalizar_caso(Lista, Caso),
    findall([Cod, Nombre, Motivo],
            ( diagnostico(Cod, Nombre, _, _),
              motivo_rechazo(Caso, Cod, Motivo) ),
            Descartadas).

% CORTE: se informa un solo motivo por hipótesis (el primero aplicable).
motivo_rechazo(Caso, Cod, Motivo) :-
    descartada(Caso, Cod, Motivo), !.
motivo_rechazo(Caso, Cod, Motivo) :-
    evidencias_favor(Caso, Cod, F), F \== [],
    excluida(Caso, Cod, Motivo), !.

% R3.11 estado_consulta(+Caso, +Resultados, -Estado)
% CORTE: estados mutuamente excluyentes evaluados en orden.
% FALLBACK: 'sin_diagnostico_concluyente'.
estado_consulta([], _, Estado) :- !,
    Estado = sin_datos.
estado_consulta(Caso, _, Estado) :-
    fuera_de_alcance(Caso, _), !,
    Estado = fuera_de_alcance.
estado_consulta(_, Resultados, Estado) :-
    member(R, Resultados), concluyente(R), !,
    Estado = con_resultados.
estado_consulta(_, Resultados, Estado) :-
    Resultados \== [], !,
    Estado = datos_insuficientes.
estado_consulta(_, _, sin_diagnostico_concluyente).

concluyente([alerta|_]).
concluyente([basica|_]).
concluyente([diagnostico, _, _, _, Respaldo|_]) :-
    memberchk(Respaldo, [alto, medio]).


/* =========================================================================
   5. SELECCIÓN DE PREGUNTAS Y EXPLICACIÓN "¿POR QUÉ?"
   ========================================================================= */

% R5.1 ya_preguntada(+Variable, +Caso)
ya_preguntada(Var, Caso) :-
    memberchk(obs(Var, _), Caso).

% R5.2 var_relacionada(?Diagnostico, ?Variable)
% Variables cuyo valor afecta una hipótesis.
var_relacionada(Cod, Var) :- evidencia(Cod, Var, _).
var_relacionada(Cod, Var) :- verificacion(Cod, Var, _).
var_relacionada(Cod, Var) :- contraevidencia(Cod, Var, _).
var_relacionada(Cod, Var) :- descarte(Cod, L),  member(Var-_, L).
var_relacionada(Cod, Var) :- requisito(Cod, L), member(Var-_, L).

% R5.3 hay_activas(+Caso)
% CORTE: basta con encontrar una hipótesis activa.
hay_activas(Caso) :-
    hipotesis_activa(Caso, _), !.

% R5.4 en_juego(+Caso, ?Diagnostico)
% Hipótesis que conviene seguir investigando:
%  - si ya hay activas: las activas y sus competidoras compatibles;
%  - si no hay ninguna: todas las compatibles.
% Las dos cláusulas son excluyentes por NEGACIÓN POR FALLO.
en_juego(Caso, Cod) :-
    hay_activas(Caso),
    compatible(Caso, Cod),
    (   hipotesis_activa(Caso, Cod)
    ;   hipotesis_activa(Caso, A), competidoras(A, Cod)
    ).
en_juego(Caso, Cod) :-
    \+ hay_activas(Caso),
    compatible(Caso, Cod).

% R5.6 mejor_candidata(+Caso, -Variable)
% Después del triaje, la entrevista pregunta exactamente el dato que el
% módulo "¿Qué falta?" pone en primer lugar (R8.2 y R8.6): el de mayor peso
% para confirmar o desempatar, a igual peso el de mayor prioridad y menor
% costo. Así la entrevista y el panel usan un único criterio y nunca se
% contradicen. Falla si "¿Qué falta?" ya no tiene nada que sugerir.
mejor_candidata(Caso, Var) :-
    situacion_evidencia(Caso, _, Objetivo),
    sugerencias(Caso, Objetivo, [[Var|_]|_]).

% R5.7 primera_fase_pendiente(+Caso, -Variable)
primera_fase_pendiente(Caso, Var) :-
    findall(O-V, ( fase_inicial(V, O, _), \+ ya_preguntada(V, Caso) ), L),
    msort(L, [_-Var|_]).

% R5.8 elegir_pregunta(+Caso, -Variable)
% CORTE: criterios de parada y fases evaluados en orden.
% El triaje (admisión y seguridad) se completa siempre; después se sigue
% la sugerencia principal de "¿Qué falta?" (R5.6).
% FALLBACK: 'fin' cuando ningún dato pendiente cambiaría el resultado.
elegir_pregunta(Caso, Var) :-
    fuera_de_alcance(Caso, _), !, Var = fin.
elegir_pregunta(Caso, Var) :-
    parametro(max_preguntas, Max),
    length(Caso, N), N >= Max, !, Var = fin.
elegir_pregunta(Caso, Var) :-
    primera_fase_pendiente(Caso, V), !, Var = V.
elegir_pregunta(Caso, Var) :-
    mejor_candidata(Caso, V), !, Var = V.
elegir_pregunta(_, fin).

% R5.9 motivo_pregunta(+Caso, +Variable, -Motivo)
% Explicación "¿por qué me pregunta esto?". CORTE: un solo motivo, en
% orden: triaje; dato sugerido por "¿Qué falta?" con su efecto; hipótesis
% relacionadas; texto general.
motivo_pregunta(_, Var, Motivo) :-
    fase_inicial(Var, _, Motivo), !.
motivo_pregunta(Caso, Var, Motivo) :-
    situacion_evidencia(Caso, _, Objetivo),
    sugerencias(Caso, Objetivo, Sugerencias),
    memberchk([Var, _, _, Peso, _, _, Efectos], Sugerencias), !,
    atomic_list_concat(Efectos, ' ', Detalle),
    format(atom(Motivo), 'Es el dato con más peso (~w) para confirmar o desempatar el diagnóstico. ~w',
           [Peso, Detalle]).
motivo_pregunta(Caso, Var, Motivo) :-
    findall(Txt,
            ( en_juego(Caso, Cod), var_relacionada(Cod, Var),
              diagnostico(Cod, Nombre, _, _),
              format(atom(Txt), '~w (~w)', [Nombre, Cod]) ),
            L0),
    sort(L0, L), L \== [], !,
    atomic_list_concat(L, '; ', Lista),
    format(atom(Motivo), 'Esta respuesta ayuda a confirmar o descartar: ~w.', [Lista]).
motivo_pregunta(_, _, 'Pregunta general de diagnóstico.').


/* =========================================================================
   6. PREDICADOS DE CONSULTA INVOCADOS DESDE PYTHON
   Python solo envía la lista de observaciones y recibe listas de resultados.
   ========================================================================= */

% consultar(+ListaObs, -Estado, -Mensaje, -Resultados, -Descartadas, -Invalidas)
consultar(Lista, Estado, Mensaje, Resultados, Descartadas, Invalidas) :-
    observaciones_invalidas(Lista, Invalidas),
    normalizar_caso(Lista, Caso),
    diagnosticar_todos(Caso, Resultados),
    hipotesis_descartadas(Caso, Descartadas),
    estado_consulta(Caso, Resultados, Estado),
    mensaje_consulta(Caso, Estado, Mensaje).

% mensaje_consulta/3: añade el motivo cuando el caso está fuera de alcance.
mensaje_consulta(Caso, fuera_de_alcance, Mensaje) :-
    fuera_de_alcance(Caso, Motivo), !,
    mensaje_estado(fuera_de_alcance, Base),
    format(atom(Mensaje), '~w ~w', [Motivo, Base]).
mensaje_consulta(_, Estado, Mensaje) :-
    mensaje_estado(Estado, Mensaje).

% observaciones_invalidas(+ListaObs, -Invalidas)
% Devuelve como texto los elementos rechazados (para informar al usuario).
observaciones_invalidas(Lista, Textos) :-
    is_list(Lista), !,
    particionar_obs(Lista, _, Inv),
    findall(T, ( member(I, Inv), format(atom(T), '~q', [I]) ), Textos).
observaciones_invalidas(Lista, [T]) :-
    format(atom(T), '~q (no es una lista)', [Lista]).

% siguiente_pregunta(+ListaObs, -Variable): 'fin' si no hay más preguntas.
siguiente_pregunta(Lista, Var) :-
    normalizar_caso(Lista, Caso),
    elegir_pregunta(Caso, Var).

% por_que_pregunta(+ListaObs, +Variable, -Motivo)
por_que_pregunta(Lista, Var, Motivo) :-
    normalizar_caso(Lista, Caso),
    motivo_pregunta(Caso, Var, Motivo).

% info_pregunta(+Variable, -Texto, -Opciones, -TipoEntrada)
% TipoEntrada: numerico o opciones.
info_pregunta(Var, Texto, Opciones, numerico) :-
    rango_numerico(Var, _, _), !,
    variable(Var, _, _, _, Texto),
    opciones(Var, Opciones).
info_pregunta(Var, Texto, Opciones, opciones) :-
    variable(Var, _, _, _, Texto),
    opciones(Var, Opciones).

% alertas_activas(+ListaObs, -Alertas): [[Codigo, Nombre], ...]
alertas_activas(Lista, Alertas) :-
    normalizar_caso(Lista, Caso),
    findall([Cod, Nombre],
            ( alerta_activa(Caso, Cod, _), alerta(Cod, Nombre, _) ),
            Alertas).

% catalogo_variables(-Variables)
% Catálogo para construir el formulario de la interfaz sin repetir el
% conocimiento en Python. Cada elemento:
%   [Variable, Grupo, NombreGrupo, Tipo, Etiqueta, Pregunta, Opciones, TipoEntrada]
% Opciones = [[Valor, TextoLegible], ...].
catalogo_variables(Variables) :-
    findall([V, G, NG, T, E, P, Ops, K],
            ( variable(V, G, T, E, P),
              grupo(G, NG),
              info_pregunta(V, _, Valores, K),
              findall([X, XL], ( member(X, Valores), valor_legible(X, XL) ), Ops) ),
            Variables).

% explicar_consulta(+ListaObs, -General, -Conclusiones, -Hechos, -Alternativas)
% Módulo "¿Por qué?" (sección 7). Ver R7.6.
explicar_consulta(Lista, General, Conclusiones, Hechos, Alternativas) :-
    normalizar_caso(Lista, Caso),
    traza_general(Lista, Caso, General),
    traza_conclusiones(Caso, Conclusiones),
    hechos_comprobados(Caso, Hechos),
    hipotesis_alternativas(Caso, Alternativas).

% que_falta(+ListaObs, -Situacion, -Mensaje, -Evaluadas, -Sugerencias)
% Módulo "¿Qué falta?" (sección 8). Ver R8.7.
que_falta(Lista, Situacion, Mensaje, Evaluadas, Sugerencias) :-
    normalizar_caso(Lista, Caso),
    situacion_evidencia(Caso, Situacion, Objetivo),
    hipotesis_evaluadas(Caso, Objetivo, Evaluadas),
    sugerencias(Caso, Objetivo, Sugerencias),
    mensaje_falta_caso(Situacion, Sugerencias, Mensaje).


/* =========================================================================
   7. MÓDULO DE EXPLICABILIDAD "¿POR QUÉ?"
   Reconstruye la traza de inferencia llamando a LAS MISMAS reglas que
   producen las conclusiones: cada paso se agrega solo si la regla que
   documenta tiene éxito sobre el caso. No hay una segunda versión del
   conocimiento: si una regla cambia, la traza cambia con ella.

   Cada paso es una lista [Profundidad, IdRegla, Texto]:
     Profundidad 0 = conclusión, 1 = regla de Nivel 3 o 2 que la sostiene,
     2 y 3 = reglas y hechos de los que depende (árbol con sangría).
   Los generadores de pasos tienen varias cláusulas que se recorren con
   findall/3; por eso NO llevan cortes (un corte detendría la traza) y las
   alternativas internas se resuelven con if-then-else.
   ========================================================================= */

% R7.1 paso_hecho(+Caso, +Profundidad, +Variable-Valor, -Paso)
% Hoja del árbol: un hecho del caso que unificó con una condición.
% Para el voltaje documenta además la clasificación numérica (R1.6).
% CORTE: el voltaje numérico usa solo la primera cláusula.
paso_hecho(Caso, P, voltaje-Estado, [P, 'R1.6', Texto]) :-
    valor(voltaje, Caso, V), number(V), !,
    parametro(voltaje_minimo_normal, Min),
    (   Estado == bajo
    ->  Op = '<'
    ;   Op = '>='
    ),
    format(atom(Texto), 'voltaje_estado/2: ~w V ~w ~w V, por lo tanto el voltaje es ~w.',
           [V, Op, Min, Estado]).
paso_hecho(Caso, P, Var-Val, [P, 'R1.7', Texto]) :-
    describir_hecho(Caso, Var-Val, T),
    format(atom(Texto), 'hecho_caso/3: ~w.', [T]).

% R7.2 traza_general(+ListaObs, +Caso, -Pasos)
% Razonamiento común a todas las conclusiones: validación, alcance,
% estados intermedios, exclusiones, señales de riesgo y estado final.
traza_general(Lista, Caso, Pasos) :-
    findall(P, paso_general(Lista, Caso, P), Pasos).

paso_general(Lista, _, [0, 'R1.5', T]) :-
    \+ is_list(Lista),
    T = 'normalizar_caso/2: la entrada no es una lista; se usa el caso vacío (cláusula por defecto).'.
paso_general(Lista, Caso, [0, 'R1.5', T]) :-
    is_list(Lista),
    length(Lista, NT),
    particionar_obs(Lista, Validas, Invalidas),
    length(Validas, NV), length(Invalidas, NI), length(Caso, NC),
    NR is NV - NC,
    format(atom(T), 'normalizar_caso/2: ~w observaciones recibidas; ~w válidas tras ground/1 y la validación de opciones (~w inválidas, ~w repetidas eliminadas).',
           [NT, NC, NI, NR]).
paso_general(_, Caso, [0, 'R1.10', T]) :-
    (   fuera_de_alcance(Caso, Motivo)
    ->  format(atom(T), 'fuera_de_alcance/2: ~w Solo se evalúan alertas de seguridad.', [Motivo])
    ;   T = 'fuera_de_alcance/2 falla: \\+ fuera_de_alcance/2 permite evaluar verificaciones básicas y diagnósticos.'
    ).
paso_general(_, Caso, P) :-
    valor(voltaje, Caso, V), number(V),
    voltaje_estado(Caso, E),
    paso_hecho(Caso, 0, voltaje-E, P).
paso_general(_, Caso, [0, 'R2.1', T]) :-
    estado_alimentacion(Caso, E), E \== desconocida,
    findall(Txt,
            ( member(V, [tablero, luces, voltaje]),
              hecho_caso(Caso, V, X), X \== desconocido,
              describir_hecho(Caso, V-X, Txt) ),
            Ts),
    atomic_list_concat(Ts, '; ', Base),
    valor_legible(E, EL),
    format(atom(T), 'estado_alimentacion/2: alimentación eléctrica ~w (a partir de: ~w).', [EL, Base]).
paso_general(_, Caso, [0, 'R2.2', T]) :-
    setof(M, Cod^excluida(Caso, Cod, M), Motivos),
    member(M, Motivos),
    findall(C, excluida(Caso, C, M), Cs),
    codigos_texto(Cs, CsT),
    format(atom(T), 'excluida/3: ~w Afecta a: ~w.', [M, CsT]).
paso_general(_, Caso, [0, 'R1.11', T]) :-
    senales_riesgo_caso(Caso, S), S \== [],
    length(S, N),
    textos_hechos(Caso, S, L),
    format(atom(T), 'senales_riesgo_caso/2: ~w señal(es) de riesgo: ~w.', [N, L]).
paso_general(_, Caso, [0, 'R3.11', T]) :-
    diagnosticar_todos(Caso, Resultados),
    estado_consulta(Caso, Resultados, E),
    format(atom(T), 'estado_consulta/3: el estado de la consulta es ~w.', [E]).

% R7.3 traza_conclusiones(+Caso, -Conclusiones)
% Una traza por conclusión reportada, en el mismo orden del reporte.
% Elemento: [Tipo, Codigo, Nombre, Pasos].
traza_conclusiones(Caso, Conclusiones) :-
    diagnosticar_todos(Caso, Resultados),
    findall([Tipo, Cod, Nombre, Pasos],
            ( member([Tipo, Cod, Nombre|_], Resultados),
              findall(P, paso_conclusion(Caso, Tipo, Cod, P), Pasos) ),
            Conclusiones).

% R7.4 paso_conclusion(+Caso, +Tipo, +Codigo, -Paso)
% Árbol de reglas disparadas para una conclusión. Las cláusulas están en
% el orden en que se presentan: primero las propias del tipo y al final
% las de prioridad, comunes a todos los tipos.

% --- Diagnósticos ---------------------------------------------------------
paso_conclusion(_, diagnostico, Cod, [0, 'R3.6', T]) :-
    diagnostico(Cod, Nombre, _, _),
    upcase_atom(Cod, CU),
    format(atom(T), 'conclusion/2: ~w - ~w se reporta como diagnóstico preliminar.', [CU, Nombre]).
paso_conclusion(_, diagnostico, _, [1, 'R2.11',
    'hipotesis_activa/2: la hipótesis es compatible, cumple sus requisitos y tiene evidencia a favor.']).
paso_conclusion(Caso, diagnostico, Cod, [2, 'R2.10',
    'compatible/2: \\+ descartada/3 y \\+ excluida/3 tienen éxito (ninguna verificación la descarta y ninguna condición del caso la excluye).']) :-
    compatible(Caso, Cod).
paso_conclusion(Caso, diagnostico, Cod, [2, 'R2.7', T]) :-
    (   \+ requisito(Cod, _)
    ->  T = 'cumple_requisito/2: no tiene requisitos mínimos (primera cláusula, \\+ requisito/2).'
    ;   requisito(Cod, L), cumple_todas(Caso, L)
    ->  textos_hechos(Caso, L, LT),
        format(atom(T), 'cumple_requisito/2: requisito mínimo cumplido (cumple_todas/2): ~w.', [LT])
    ).
paso_conclusion(Caso, diagnostico, Cod, [2, 'R2.4', T]) :-
    evidencias_favor(Caso, Cod, L),
    length(L, N),
    format(atom(T), 'evidencias_favor/3: ~w condición(es) del perfil presentes en el caso.', [N]).
paso_conclusion(Caso, diagnostico, Cod, P) :-
    evidencias_favor(Caso, Cod, L),
    member(H, L),
    paso_hecho(Caso, 3, H, P).
paso_conclusion(Caso, diagnostico, Cod, [1, 'R2.14', T]) :-
    respaldo(Caso, Cod, Nivel, _),
    format(atom(T), 'respaldo/4: respaldo ~w.', [Nivel]).
paso_conclusion(Caso, diagnostico, Cod, [2, 'R2.13', T]) :-
    coincidencia(Caso, Cod, NC, NV),
    format(atom(T), 'coincidencia/4: ~w condición(es) cumplida(s) sobre un perfil de ~w variable(s).', [NC, NV]).
paso_conclusion(Caso, diagnostico, Cod, [2, 'R2.6', T]) :-
    contraevidencias(Caso, Cod, Contra),
    (   Contra == []
    ->  T = 'contraevidencias/3: no hay evidencias en contra.'
    ;   textos_hechos(Caso, Contra, CT),
        format(atom(T), 'contraevidencias/3: evidencias en contra: ~w.', [CT])
    ).
paso_conclusion(Caso, diagnostico, Cod, [2, 'R2.15', T]) :-
    respaldo(Caso, Cod, _, J),
    format(atom(T), 'clasificar_respaldo/6: ~w', [J]).
paso_conclusion(Caso, diagnostico, Cod, [3, 'R2.5', T]) :-
    findall(V-X, ( verificacion(Cod, V, X), hecho_caso(Caso, V, X) ), Vs),
    Vs \== [],
    textos_hechos(Caso, Vs, VT),
    format(atom(T), 'verificacion_favor/2: verificación específica a favor: ~w.', [VT]).
% Respaldo Alto sin verificación propia: solo puede venir de la segunda
% cláusula de clasificar_respaldo/6 (competidoras descartadas).
paso_conclusion(Caso, diagnostico, Cod, [3, 'R2.9', T]) :-
    respaldo(Caso, Cod, alto, _),
    \+ verificacion_favor(Caso, Cod),
    findall(C, competidoras(Cod, C), Cs0),
    sort(Cs0, Cs),
    codigos_texto(Cs, CsT),
    format(atom(T), 'competidoras_descartadas/2: todas las competidoras (~w) están descartadas por verificación.', [CsT]).

% --- Alertas --------------------------------------------------------------
paso_conclusion(_, alerta, Cod, [0, 'R3.6', T]) :-
    alerta(Cod, Nombre, _),
    upcase_atom(Cod, CU),
    format(atom(T), 'conclusion/2: ~w - ~w se emite como alerta de seguridad (se conserva aunque el caso esté fuera de alcance).', [CU, Nombre]).
paso_conclusion(Caso, alerta, Cod, [1, 'R2.16', T]) :-
    alerta_activa(Caso, Cod, D),
    length(D, N),
    format(atom(T), 'alerta_activa/3: ~w disparador(es) presente(s); basta uno para emitir la alerta.', [N]).
paso_conclusion(Caso, alerta, Cod, P) :-
    alerta_activa(Caso, Cod, D),
    member(H, D),
    paso_hecho(Caso, 2, H, P).

% --- Verificaciones básicas -----------------------------------------------
paso_conclusion(_, basica, Cod, [0, 'R3.6', T]) :-
    verificacion_basica(Cod, Nombre, _, _),
    upcase_atom(Cod, CU),
    format(atom(T), 'conclusion/2: ~w - ~w se reporta como verificación básica.', [CU, Nombre]).
paso_conclusion(_, basica, _, [1, 'R2.17',
    'basica_activa/3: todas sus condiciones están en el caso (cumple_todas/2, R1.8).']).
paso_conclusion(Caso, basica, Cod, P) :-
    verificacion_basica(Cod, _, _, L),
    member(H, L),
    paso_hecho(Caso, 2, H, P).

% --- Prioridad (todos los tipos) ------------------------------------------
paso_conclusion(Caso, _, Cod, [1, 'R3.4', T]) :-
    prioridad(Caso, Cod, N, E, _, _),
    format(atom(T), 'prioridad/6: prioridad ~w (~w) = base + elevaciones - reducciones, acotada entre 1 y 4 (R3.3).', [N, E]).
paso_conclusion(_, _, Cod, [2, 'H1.10', T]) :-
    prioridad_base(Cod, B),
    nivel_prioridad(B, E, _),
    format(atom(T), 'prioridad_base/2: base ~w (~w).', [B, E]).
paso_conclusion(Caso, _, Cod, [2, 'R3.1', R]) :-
    elevacion(Caso, Cod, R).
paso_conclusion(Caso, _, Cod, [2, 'R3.2', R]) :-
    reduccion(Caso, Cod, R).

% R7.5 hechos_comprobados(+Caso, -Hechos)
% Observaciones del usuario que pasaron la validación y valen como
% verdaderas en el caso. Para cada una se listan los hechos y reglas de la
% base con los que unifica. Elemento: [Texto, Usos].
hechos_comprobados(Caso, Hechos) :-
    findall([Texto, Usos],
            ( member(obs(Var, _), Caso),
              hecho_caso(Caso, Var, Val), Val \== desconocido,
              describir_hecho(Caso, Var-Val, Texto),
              findall(U, uso_hecho(Var, Val, U), Us0),
              sort(Us0, Usos) ),
            Hechos).

% uso_hecho(+Variable, +Valor, -Uso): hecho o regla de la base que unifica
% con la observación Variable = Valor.
uso_hecho(V, X, U) :-
    evidencia(C, V, X),
    format(atom(U), 'evidencia(~w, ~w, ~w)', [C, V, X]).
uso_hecho(V, X, U) :-
    verificacion(C, V, X),
    format(atom(U), 'verificacion(~w, ~w, ~w)', [C, V, X]).
uso_hecho(V, X, U) :-
    contraevidencia(C, V, X),
    format(atom(U), 'contraevidencia(~w, ~w, ~w)', [C, V, X]).
uso_hecho(V, X, U) :-
    disparador_alerta(C, V, X),
    format(atom(U), 'disparador_alerta(~w, ~w, ~w)', [C, V, X]).
uso_hecho(V, X, U) :-
    descarte(C, L), memberchk(V-X, L),
    format(atom(U), 'descarte(~w, ~w)', [C, L]).
uso_hecho(V, X, U) :-
    requisito(C, L), memberchk(V-X, L),
    format(atom(U), 'requisito(~w, ~w)', [C, L]).
uso_hecho(V, X, U) :-
    verificacion_basica(C, _, _, L), memberchk(V-X, L),
    format(atom(U), 'verificacion_basica(~w, ~w)', [C, L]).
uso_hecho(V, X, U) :-
    senal_riesgo(V, X),
    format(atom(U), 'senal_riesgo(~w, ~w)', [V, X]).
uso_hecho(V, _, 'regla estado_alimentacion/2 (R2.1)') :-
    memberchk(V, [tablero, luces, voltaje]).
uso_hecho(giro_arranque, no_gira, 'regla excluida/3 (R2.2): excluye la rama motor').
uso_hecho(interruptor_paro, paro, 'regla excluida/3 (R2.2): excluye d06').
uso_hecho(nivel_combustible, vacio, 'regla excluida/3 (R2.2): excluye d07').
uso_hecho(V, _, 'regla fuera_de_alcance/2 (R1.10)') :-
    memberchk(V, [cilindrada, alimentacion]).
uso_hecho(mantenimiento_reciente, si, 'regla reduccion/3 (R3.2)').
uso_hecho(compresion, normal, 'regla reduccion/3 (R3.2)').
uso_hecho(ruidos_anormales, no, 'regla reduccion/3 (R3.2)').

% R7.6 hipotesis_alternativas(+Caso, -Alternativas)
% Diagnósticos que NO se reportan y por qué. Elemento:
%   [Codigo, Nombre, Tipo, SintomasCompartidos, Motivo]
% Tipo: descartada            (una verificación en contra, descarte/2)
%       excluida              (\+ excluida/3 falla dentro de compatible/2)
%       sin_evidencia_critica (comparte síntomas, pero no cumple requisito/2)
% Fuera de alcance no se evalúan diagnósticos, así que la lista es vacía.
hipotesis_alternativas(Caso, []) :-
    fuera_de_alcance(Caso, _), !.
hipotesis_alternativas(Caso, Alternativas) :-
    findall([Cod, Nombre, Tipo, Compartidos, Motivo],
            ( diagnostico(Cod, Nombre, _, _),
              motivo_alternativa(Caso, Cod, Tipo, Motivo),
              evidencias_favor(Caso, Cod, F),
              findall(T, ( member(H, F), describir_hecho(Caso, H, T) ), Compartidos) ),
            Alternativas).

% motivo_alternativa(+Caso, +Diagnostico, -Tipo, -Motivo)
% CORTE: un solo motivo por hipótesis, en orden: descarte, exclusión,
% falta de evidencia crítica. Las exclusiones solo se informan si la
% hipótesis compartía algún síntoma con el caso (si no, no es alternativa).
motivo_alternativa(Caso, Cod, descartada, Motivo) :-
    descartada(Caso, Cod, Motivo), !.
motivo_alternativa(Caso, Cod, excluida, Motivo) :-
    evidencias_favor(Caso, Cod, F), F \== [],
    excluida(Caso, Cod, M), !,
    format(atom(Motivo), '~w (compatible/2: \\+ excluida/3 falla).', [M]).
motivo_alternativa(Caso, Cod, sin_evidencia_critica, Motivo) :-
    compatible(Caso, Cod),
    evidencias_favor(Caso, Cod, F), F \== [],
    \+ cumple_requisito(Caso, Cod), !,
    findall(Txt,
            ( requisito(Cod, L), textos_hechos(Caso, L, Txt0),
              format(atom(Txt), '(~w)', [Txt0]) ),
            Opciones),
    atomic_list_concat(Opciones, ' o ', Req),
    format(atom(Motivo), 'Comparte síntomas, pero falta evidencia crítica: no cumple el requisito mínimo ~w.', [Req]).

% R7.7 Utilidades de texto para la traza.
% textos_hechos(+Caso, +Condiciones, -Texto): "Etiqueta: valor; ...".
textos_hechos(Caso, Condiciones, Texto) :-
    findall(T, ( member(C, Condiciones), describir_hecho(Caso, C, T) ), Ts),
    atomic_list_concat(Ts, '; ', Texto).

% codigos_texto(+Codigos, -Texto): "D01, D02".
codigos_texto(Codigos, Texto) :-
    findall(U, ( member(C, Codigos), upcase_atom(C, U) ), Us),
    atomic_list_concat(Us, ', ', Texto).


/* =========================================================================
   8. MÓDULO DE RECOMENDACIÓN "¿QUÉ FALTA?"
   Evalúa las hipótesis parcialmente activas y decide qué dato todavía no
   ingresado tiene más peso para confirmar o desempatar el diagnóstico.

   Peso de una variable = suma, sobre las hipótesis objetivo, del efecto
   más fuerte que alguno de sus valores tendría en cada una (peso_efecto/2).
   Orden de las sugerencias: mayor peso > mayor prioridad de las hipótesis
   afectadas > menor costo de respuesta (costo_tipo/2).
   ========================================================================= */

% R8.1 candidatas(+Caso, -Candidatas)
% Hipótesis activas con su respaldo: [Rango-Codigo-Respaldo, ...].
candidatas(Caso, Candidatas) :-
    findall(R-Cod-Nivel,
            ( hipotesis_activa(Caso, Cod),
              respaldo(Caso, Cod, Nivel, _),
              rango_respaldo(Nivel, R) ),
            Candidatas).

% R8.2 situacion_evidencia(+Caso, -Situacion, -Objetivo)
% Clasifica la evidencia y elige las hipótesis objetivo de la sugerencia.
% CORTE: situaciones mutuamente excluyentes evaluadas en orden.
situacion_evidencia(Caso, fuera_de_alcance, []) :-
    fuera_de_alcance(Caso, _), !.
situacion_evidencia(Caso, sin_hipotesis, Objetivo) :-
    \+ hay_activas(Caso), !,
    findall(C, compatible(Caso, C), Objetivo).
situacion_evidencia(Caso, Situacion, Objetivo) :-
    candidatas(Caso, Cands),
    findall(R, member(R-_-_, Cands), Rs),
    max_list(Rs, Max),
    findall(C, member(Max-C-_, Cands), Tope),
    clasificar_situacion(Max, Tope, Cands, Situacion, Objetivo).

% R8.3 clasificar_situacion(+RangoMax, +Tope, +Candidatas, -Situacion, -Objetivo)
% definitivo  : la mejor tiene respaldo Alto; el objetivo son las demás.
% empate      : dos o más comparten el mejor respaldo (Medio o Bajo).
% insuficiente: una sola destaca sin llegar a Alto; objetivo, todas las activas.
% CORTE: casos excluyentes; la última cláusula es el caso por defecto.
clasificar_situacion(Max, _, Cands, definitivo, Objetivo) :-
    rango_respaldo(alto, Max), !,
    findall(C, ( member(R-C-_, Cands), R < Max ), Objetivo).
clasificar_situacion(_, Tope, _, empate, Tope) :-
    length(Tope, N), N >= 2, !.
clasificar_situacion(_, _, Cands, insuficiente, Objetivo) :-
    findall(C, member(_-C-_, Cands), Objetivo).

% R8.4 efecto_valor(+Caso, +Hipotesis, +Variable, +Valor, -Efecto)
% Efecto que tendría Variable = Valor sobre la hipótesis.
efecto_valor(_, H, V, X, confirma) :-
    verificacion(H, V, X).
efecto_valor(Caso, H, V, X, descarta) :-
    descarte(H, L),
    select(V-X, L, Resto),
    cumple_todas(Caso, Resto).
efecto_valor(Caso, H, V, X, contribuye_descarte) :-
    descarte(H, L),
    select(V-X, L, Resto),
    \+ cumple_todas(Caso, Resto).
efecto_valor(_, H, V, X, contradice) :-
    contraevidencia(H, V, X).
efecto_valor(_, H, V, X, apoya) :-
    evidencia(H, V, X).

% valor_posible(+Variable, -Valor): valores que podría tomar un dato
% pendiente. CORTE: las variables numéricas usan sus valores derivados.
valor_posible(V, X) :-
    valores_derivados(V, Xs), !,
    member(X, Xs).
valor_posible(V, X) :-
    opciones(V, Xs),
    member(X, Xs),
    X \== desconocido.

% R8.5 peso_variable(+Caso, +Objetivo, +Variable, -Peso, -Efectos)
% Efectos = [Valor-Hipotesis-Efecto, ...] sin repetidos. Falla si la
% variable no afecta a ninguna hipótesis objetivo.
peso_variable(Caso, Objetivo, V, Peso, Efectos) :-
    findall(X-H-E,
            ( valor_posible(V, X),
              member(H, Objetivo),
              efecto_valor(Caso, H, V, X, E) ),
            Efectos0),
    Efectos0 \== [],
    sort(Efectos0, Efectos),
    findall(P,
            ( member(H, Objetivo),
              findall(W, ( member(_-H-E, Efectos), peso_efecto(E, W) ), Ws),
              Ws \== [],
              max_list(Ws, P) ),
            Ps),
    sum_list(Ps, Peso).

% R8.6 sugerencias(+Caso, +Objetivo, -Sugerencias)
% Datos aún no ingresados ordenados por peso, prioridad y costo; se
% devuelven los primeros max_sugerencias. Un dato respondido como
% 'desconocido' ("No lo sé") ya fue ingresado y no se vuelve a sugerir.
% NEGACIÓN POR FALLO: V llega instanciada desde variable/5. Elemento:
%   [Variable, Etiqueta, Pregunta, Peso, Prioridad, Tipo, Efectos]
sugerencias(_, [], []) :- !.
sugerencias(Caso, Objetivo, Sugerencias) :-
    findall(k(NegPeso, NegPrio, Costo, V)-[V, Etq, Preg, Peso, Prio, Tipo, Textos],
            ( variable(V, _, Tipo, Etq, Preg),
              \+ ya_preguntada(V, Caso),
              peso_variable(Caso, Objetivo, V, Peso, Efectos),
              prioridad_afectadas(Caso, Efectos, Prio),
              costo_tipo(Tipo, Costo),
              textos_efectos(V, Efectos, Textos),
              NegPeso is -Peso,
              NegPrio is -Prio ),
            Pares),
    keysort(Pares, Ordenados),
    parametro(max_sugerencias, Max),
    primeros(Ordenados, Max, Top),
    pares_a_valores(Top, Sugerencias).

% prioridad_afectadas(+Caso, +Efectos, -Prioridad): la mayor prioridad
% entre las hipótesis a las que afecta la variable.
prioridad_afectadas(Caso, Efectos, Prio) :-
    findall(N, ( member(_-H-_, Efectos), prioridad(Caso, H, N, _, _, _) ), Ns),
    max_list(Ns, Prio).

% textos_efectos(+Variable, +Efectos, -Textos): un texto por valor posible.
textos_efectos(V, Efectos, Textos) :-
    findall(X, member(X-_-_, Efectos), Xs0),
    sort(Xs0, Xs),
    findall(T,
            ( member(X, Xs),
              findall(F,
                      ( member(X-H-E, Efectos),
                        texto_efecto(E, TE),
                        upcase_atom(H, HU),
                        format(atom(F), '~w ~w', [TE, HU]) ),
                      Fs),
              atomic_list_concat(Fs, ', ', FsT),
              valor_sugerido(V, X, XT),
              format(atom(T), 'Si la respuesta es «~w»: ~w.', [XT, FsT]) ),
            Textos).

% valor_sugerido(+Variable, +Valor, -Texto)
% CORTE: el voltaje se expresa con el umbral; el resto, con valor_legible/2.
valor_sugerido(voltaje, X, T) :- !,
    parametro(voltaje_minimo_normal, Min),
    (   X == bajo
    ->  format(atom(T), 'menos de ~w V', [Min])
    ;   format(atom(T), '~w V o más', [Min])
    ).
valor_sugerido(_, X, T) :-
    valor_legible(X, T).

% primeros(+Lista, +N, -Primeros). CORTE: con N = 0 se termina.
primeros(_, 0, []) :- !.
primeros([], _, []).
primeros([X|Xs], N, [X|Ys]) :-
    N1 is N - 1,
    primeros(Xs, N1, Ys).

% R8.7 hipotesis_evaluadas(+Caso, +Objetivo, -Evaluadas)
% [Codigo, Nombre, Respaldo] de las hipótesis objetivo; 'sin_evidencia'
% para las compatibles que todavía no tienen evidencia a favor.
hipotesis_evaluadas(Caso, Objetivo, Evaluadas) :-
    findall([Cod, Nombre, R],
            ( member(Cod, Objetivo),
              diagnostico(Cod, Nombre, _, _),
              (   hipotesis_activa(Caso, Cod)
              ->  respaldo(Caso, Cod, R, _)
              ;   R = sin_evidencia
              ) ),
            Evaluadas).

% mensaje_falta_caso(+Situacion, +Sugerencias, -Mensaje)
% CORTE: si una situación no definitiva se queda sin sugerencias se
% informa que no quedan datos útiles.
mensaje_falta_caso(Situacion, [], Mensaje) :-
    \+ memberchk(Situacion, [definitivo, fuera_de_alcance]), !,
    mensaje_falta(sin_sugerencias, Mensaje).
mensaje_falta_caso(Situacion, _, Mensaje) :-
    mensaje_falta(Situacion, Mensaje).
