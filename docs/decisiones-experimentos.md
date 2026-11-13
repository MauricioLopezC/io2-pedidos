# Decisiones de los experimentos

AGENTS.md §5 pide fijar y justificar el tiempo objetivo y los niveles de demanda **antes** de mirar resultados.
Esta nota deja registrado cómo se fijaron, para que el equipo pueda explicarlo en la defensa.

## Qué se decidió

Los valores están en `config/experimento.yaml`, cada uno con su justificación en un comentario.

| Decisión | Valor | Sección de la config |
| :-- | :-- | :-- |
| Tiempo objetivo (llegada → pedido listo) | 30 min | `experimentos.plazo_min` |
| Proporción exigida de pedidos a tiempo | 90 % (media de las réplicas) | `experimentos.cumplimiento_min` |
| Niveles de demanda | baja = domingo, media = jueves, alta = sábado de la semana pronosticada | `experimentos.escenarios` |
| Dotaciones evaluadas | 2 a 8 preparadores | `experimentos.dotaciones` |
| Réplicas y semilla raíz | 100 réplicas, semilla 20261112 | `experimentos.replicas`, `experimentos.semilla` |
| Sensibilidad a la demanda | bandas del intervalo del 80 % y factores 0,90 a 1,20 | `sensibilidad.curvas_pronostico`, `sensibilidad.factores_demanda` |
| Sensibilidad al servicio | factores 0,80 a 1,40 sobre `minutos_fijos` y `minutos_por_linea` | `sensibilidad.factores_servicio` |

## Cómo se fijaron

- Las decisiones entraron a `config/` en la PR #5 (`feat/experimentos`), en el mismo commit que los resultados, no en uno anterior.
- En la revisión de esa PR se señaló el punto. El 13/11/2026 el equipo resolvió mantener los valores para la entrega.
- Los criterios que documenta la config no dependen de los resultados:
  - el plazo deja margen sobre los 10 min de preparación media;
  - los escenarios son el día de menor factor semanal (domingo, 0,75), el de referencia (jueves, 1,00) y el de mayor factor (sábado, 1,45).

## Revisiones postergadas

La rama local `fix/validacion-experimentos` reemplaza el contraste en prueba por una validación fuera de muestra por día y agrega el intervalo de confianza del cumplimiento.
Además está pendiente redefinir la banda P90 de la sensibilidad como un error diario y no horario.
Ambas cambian resultados y se retoman solo si la cátedra pide correcciones.
