# AGENTS.md

Guía para agentes de IA (y personas) que trabajen en este repositorio.
Es el **Trabajo Final Integrador de Investigación Operativa II (UCASAL, 2026)**, Modalidad A — Aplicación práctica.

## 1. Qué es este trabajo

**Pregunta:** ¿cuántos preparadores de pedidos online conviene asignar en un supermercado para cumplir un tiempo objetivo de preparación bajo demanda baja, media y alta?

**Proceso modelado:** llegada del pedido → espera en fila común (FIFO) → preparación por un empleado → pedido listo.
El estudio termina cuando el pedido queda preparado: ruteo en depósito, reparto, turnos y faltantes quedan **fuera de alcance**.

**Técnicas, y cómo se encadenan:**

1. **Pronóstico** de pedidos por hora (referencia estacional semanal vs. promedio de semanas recientes), evaluado con MAE sobre un período final reservado, respetando el orden temporal.
2. **Teoría de colas:** fila común con *c* servidores equivalentes; M/M/c de tasas constantes como referencia analítica para verificar.
3. **Simulación de eventos discretos** (SimPy) con el perfil horario pronosticado, dotación fija por jornada, arrastre de pendientes entre horas y semillas registradas.
4. **Recomendación:** la menor dotación evaluada que cumple el objetivo en cada escenario, informando también cuándo ninguna lo cumple, más sensibilidad a errores de pronóstico y a tiempos de servicio.

Documentos de referencia, leerlos antes de decidir algo de fondo:

- `propuesta.md`: propuesta acordada por el equipo (alcance, técnicas, resultados esperados).
- `docs/inspeccion-erp.md`: diagnóstico del histórico del ERP y justificación del histórico sintético.

## 2. Estructura

| Ruta | Contenido |
| :-- | :-- |
| `config/experimento.yaml` | **Todos** los parámetros del estudio, por sección y con responsable. |
| `datos/raw/` | Datos originales versionados (`erp_web_orders.csv`). No se modifican a mano. |
| `datos/procesados/` | Salidas de `make datos`. No se versionan; se regeneran de forma determinística. |
| `src/pedidos/` | Paquete Python: `datos`, `pronostico`, `colas`, `simulacion`, `verificacion`, `experimentos`. |
| `scripts/0N_*.py` | Pasos numerados del pipeline; leen config, llaman a `src/pedidos` y escriben salidas. |
| `tests/` | pytest, un archivo por módulo de `src/pedidos`. |
| `resultados/` | Salidas numéricas de los experimentos. |
| `informe/` | Informe en LaTeX (`main.tex`, `secciones/`, `figuras/`, `tablas/`, `referencias.bib`). |
| `notebooks/` | Exploración. Nada del informe sale solo de un notebook. |
| `docs/` | Notas de diseño y decisiones del equipo, en Markdown. |

Estado al momento de escribir esto: todos los módulos (`datos`, `pronostico`, `colas`, `simulacion`, `verificacion` y `experimentos`), los scripts `01`–`05`, los tests y las secciones del informe están implementados y verificados.
Revisar el árbol antes de suponer que algo existe.

## 3. Comandos

```bash
pip install -r requirements.txt   # instala el paquete en modo editable (-e .)
nbstripout --install              # una vez por clon: limpia salidas de notebooks
make test                         # pytest -q
make datos                        # scripts/01_preparar_datos.py
make pronostico | verificacion | experimentos | sensibilidad
make informe                      # latexmk -pdf en informe/ (biber)
make all                          # pipeline completo + informe
```

- Correr `make test` antes de dar por terminado cualquier cambio de código.
- Si se toca el informe, compilarlo con `make informe` y revisar que no haya referencias ni citas sin resolver.
- La CI (`.github/workflows/informe.yml`) solo compila el informe; los tests corren en local.
- Volver a congelar el histórico del ERP requiere la base del ERP, que **no** está en el repo: `python scripts/01_preparar_datos.py --desde-erp RUTA/database.sqlite`. No hacerlo salvo pedido explícito.

## 4. Reglas de código

- **Python ≥ 3.11**, con pandas, numpy, SimPy, Matplotlib y PyYAML. No agregar dependencias sin motivo; si se agrega una, va a `requirements.txt`.
- **Nombres, comentarios y docstrings en español**, siguiendo el estilo de `src/pedidos/datos.py`: docstring de módulo que explica el *porqué*, type hints y funciones puras siempre que se pueda.
- **Parámetros en `config/`, nunca en el código.** Nada de números mágicos (tasas, semillas, horarios, tiempo objetivo, dotaciones, escenarios). Cada parámetro nuevo se agrega con un comentario que lo justifica.
- **Rutas machine-specific nunca en `config/`**: se pasan por argumento (ver `--desde-erp`).
- **Reproducibilidad:** toda aleatoriedad usa `numpy.random.Generator` con semilla de config. Las réplicas usan semillas derivadas y registradas. Misma config → mismos resultados.
- **Unidades explícitas:** declarar en nombres o docstrings si un tiempo está en minutos u horas y si una tasa es por hora. Las marcas de tiempo son hora local Argentina sin zona.
- **Scripts delgados:** la lógica va en `src/pedidos/`; el script solo lee config, orquesta y escribe archivos. Cada script documenta sus salidas en el docstring.
- **Figuras y tablas del informe se generan desde `scripts/`** hacia `informe/figuras/` e `informe/tablas/`. Nunca editarlas a mano.

## 5. Reglas del modelo (no romper sin acuerdo del equipo)

- La **llegada** de un pedido es `placed_at` del ERP (`llegada` en el CSV).
- El estudio trabaja sobre el **histórico sintético** (Poisson no homogéneo, ~200 pedidos/día, 8 a 21 h); el ERP solo calibra calendario semanal, proporción retiro/envío y definición de llegada. El motivo está en `docs/inspeccion-erp.md`.
- Los **tiempos de preparación** no existen en los datos: son un supuesto documentado (p. ej., función de `lineas`) y se varían en la sensibilidad.
- **No mezclar** fórmulas de régimen estacionario con jornadas de demanda variable: M/M/c sirve para verificar el simulador con tasas constantes y para dar intuición, no para afirmar resultados de una jornada real.
- **El pronóstico se evalúa solo con datos no usados para ajustarlo.** Nunca usar `tasa_esperada.csv` como insumo del pronóstico: es la verdad del generador y solo sirve para validar.
- El tiempo objetivo y los niveles de demanda se fijan y justifican **antes** de mirar resultados.
- Las conclusiones se refieren al sistema modelado y a sus datos sintéticos, no al supermercado real.

### Verificación mínima esperada del simulador

- Con tasas constantes y servicio exponencial, *Wq*, *W*, *Lq* y la utilización simulados deben coincidir con M/M/c dentro de un intervalo de confianza; agregar un test que lo compruebe.
- Conservación de pedidos: llegados = preparados + pendientes al cierre.
- Casos triviales: con un solo pedido no hay espera; con muchos servidores, *Wq* ≈ 0.
- Ley de Little (*L = λW*) como chequeo de coherencia.

## 6. Informe (LaTeX)

- Estructura fijada por la consigna (sección 6): portada, resumen, introducción, objetivos, marco teórico, metodología, desarrollo, resultados, discusión, conclusiones, referencias. Extensión orientativa de 12 a 20 páginas sin anexos.
- **Una oración por línea** en los `.tex`, para que los diffs sean legibles.
- `main.tex` **no se toca** salvo acuerdo del equipo; el contenido va en `informe/secciones/`.
- Notación común en `informe/macros.tex`; usar las macros en lugar de redefinir símbolos por sección.
- Bibliografía con biblatex (estilo `ieee`, backend biber) en `referencias.bib`. Claves con formato `autor_tema` (ej. `hyndman_athanasopoulos_fpp3`).
- Español formal, en tercera persona o impersonal, coherente con las secciones ya redactadas.
- Cada número que aparezca en el texto debe salir de una tabla o figura generada por el pipeline.
- Cada sección tiene un responsable; no reescribir secciones ajenas sin que se pida.

## 7. Uso de IA (consigna, sección 10)

La cátedra admite IA como apoyo, pero **el equipo responde por fórmulas, algoritmos, referencias, código, resultados y conclusiones**, y tiene que poder explicarlos en la defensa oral. Por lo tanto, el agente:

- **No inventa resultados.** Ningún número va al informe ni a `docs/` sin haber salido de ejecutar el código.

## 8. Flujo de trabajo con Git

- Una rama por tarea y PR revisado por un compañero antes de mergear a `main`. No commitear directo en `main`.
- Commits con Conventional Commits en español: `tipo(alcance): descripción en minúscula`, con `tipo` ∈ `feat`, `fix`, `refactor`, `test`, `docs`, `chore` y `alcance` ∈ `datos`, `pronostico`, `colas`, `simulacion`, `experimentos`, `informe`, etc. El cuerpo explica el porqué.
- No versionar salidas regenerables (`datos/procesados/`, auxiliares de LaTeX, `main.pdf`) ni datos personales de clientes del ERP.

## 9. Equipo

- Flores, Facundo Néstor
- Lopez, Mauricio Agustín
- Sgabussi Donaire, Pablo Bernardo

Los responsables por sección se indican como "Persona A/B/C" en `config/` y `docs/` (A: datos y pronóstico; B: modelo de servicio; el resto del reparto, a completar por el equipo).
