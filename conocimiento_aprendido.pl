:- encoding(utf8).
% =========================================================================
% MotoExpert - Conocimiento aprendido en modo experto
% Archivo generado por guardar_aprendido/0: no lo edite a mano.
% base_conocimiento.pl lo incluye al final, de modo que estos hechos
% se cargan en cada inicio junto con la base original.
% =========================================================================

% Pregunta voltaje_al_acelerar - Voltaje al acelerar (aprendida el 2026-11-10 19:24)
aprendido_variable(voltaje_al_acelerar, '2026-11-10 19:24').
variable(voltaje_al_acelerar, electrico, prueba_tecnica, 'Voltaje al acelerar', 'Con el motor encendido, ¿sube el voltaje de la batería al acelerar?').
opciones(voltaje_al_acelerar, [si, no, desconocido]).
texto_valor_aprendido(voltaje_al_acelerar, si, sí).
texto_valor_aprendido(voltaje_al_acelerar, no, no).
expresion_lex(voltaje_al_acelerar, no, [voltaje, no, sube, al, acelerar]).
expresion_lex(voltaje_al_acelerar, si, [voltaje, sube, al, acelerar]).

% Pregunta tiene_gasolina - Tiene gasolina? (aprendida el 2026-11-11 08:48)
aprendido_variable(tiene_gasolina, '2026-11-11 08:48').
variable(tiene_gasolina, combustible, dato, 'Tiene gasolina?', 'Lleva mucho tiempo sin tanuqer?').
opciones(tiene_gasolina, [si, no, desconocido]).
texto_valor_aprendido(tiene_gasolina, si, si).
texto_valor_aprendido(tiene_gasolina, no, no).
expresion_lex(tiene_gasolina, no, [caso, puede, ser, otro]).
expresion_lex(tiene_gasolina, si, [debe, tanquear, la, moto]).

% D11 - Regulador de voltaje dañado (aprendido el 2026-11-10 18:48)
aprendido(d11, '2026-11-10 18:48').
diagnostico(d11, 'Regulador de voltaje dañado', 'sistema de carga', electrica).
prioridad_base(d11, 3).
evidencia(d11, luces, debil).
evidencia(d11, falla_intermitente, si).
evidencia(d11, giro_arranque, lento).
verificacion(d11, voltaje, bajo).
descarte(d11, [voltaje-normal]).
compite_con(d11, d01).
compite_con(d11, d02).
recomendacion(d11, 'Revisar el regulador de voltaje en un taller.').

% D12 - Echele gasolina (aprendido el 2026-11-11 08:41)
aprendido(d12, '2026-11-11 08:41').
diagnostico(d12, 'Echele gasolina', 'Motor', motor).
prioridad_base(d12, 3).
evidencia(d12, olor_gasolina, no).
verificacion(d12, nivel_combustible, vacio).
descarte(d12, [interruptor_paro-marcha]).
compite_con(d12, d01).
recomendacion(d12, 'No sea pobre').

% Reglas agregadas a diagnósticos existentes
regla_aprendida(r1, verificacion(d11, voltaje_al_acelerar, no), '2026-11-10 19:26').
regla_aprendida(r2, descarte(d11, [voltaje_al_acelerar-si]), '2026-11-10 19:26').
regla_aprendida(r3, descarte(d01, [voltaje_al_acelerar-no]), '2026-11-10 19:27').
verificacion(d11, voltaje_al_acelerar, no).
descarte(d11, [voltaje_al_acelerar-si]).
descarte(d01, [voltaje_al_acelerar-no]).
