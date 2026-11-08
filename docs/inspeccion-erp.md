# Inspección del histórico del ERP y datos del estudio

Responsable: Persona A (datos y pronóstico).
Fecha: 2026-11-08.

## Origen

Los pedidos online del ERP La Linda están en las tablas `web_orders` y `web_order_items` de `database/database.sqlite`.
Los genera `database/seeders/Sales/SalesHistorySeeder.php` con semilla fija `20260416`, pasando por las mismas Actions que producción.
El histórico se congeló en `datos/raw/erp_web_orders.csv` (sin datos de clientes) con `python scripts/01_preparar_datos.py --desde-erp`.

## Qué tiene

| Campo | Significado en el seeder |
| :-- | :-- |
| `llegada` (`placed_at`) | Entrada del pedido al sistema: es la llegada al proceso. |
| `pago` (`paid_at`) | Entre 2 y 8 minutos después de la llegada. |
| `inicio_preparacion` | Entre 30 y 90 minutos después de la llegada, independiente de la carga. |
| `entrega` | Entre 60 y 240 minutos después del inicio de la preparación. |
| `lineas`, `unidades` | Artículos distintos (1 a 5) y unidades por pedido. |
| `metodo_entrega` | Retiro en sucursal (62 %) o envío (38 %). |

- 369 pedidos entre el 17/04 y el 18/10/2026 (185 días), en hora local de Argentina.
- 1,99 pedidos por día en promedio, con varianza 0,66 y ningún día sin pedidos.
- Llegadas uniformes entre las 8 y las 16 (`getInt(8, 16)`): no hay picos dentro del día.
- Factor por día de la semana (relativo al jueves): lunes 0,77, sábado 1,46, domingo 0,76.

## Por qué no alcanza para el estudio

1. **Volumen**: 0,15 pedidos por hora de apertura y 86 % de horas sin pedidos. Con unos 10 minutos de preparación por pedido un solo empleado estaría ocupado un 3 % del tiempo, así que la dotación no es una decisión.
2. **Sin patrón horario**: un pronóstico por hora no tiene señal que captar.
3. **Sin tiempos de servicio**: el inicio de la preparación es un retardo aleatorio que no depende de la cola, y no existe marca de fin de preparación.
4. **No es Poisson**: varianza diaria menor que la media.
5. **No reproducible**: las fechas son relativas al día en que se siembra (hoy − 183 días), y la base local no coincide con el código actual del seeder (la fórmula vigente crece de ~0,5 a ~2 pedidos por día; la base muestra ~2 desde abril). Por eso se trabaja con el CSV congelado.

Lo que sí se aprovecha: el **calendario semanal**, la **proporción retiro/envío** y la definición de **llegada**.

## Histórico sintético del estudio

`src/pedidos/datos.py` genera un histórico propio con los parámetros de `config/experimento.yaml` (sección `datos`).

- 26 semanas desde el lunes 20/04/2026, horario de atención de 8 a 21 (13 horas).
- Proceso de Poisson no homogéneo con tasa constante dentro de cada hora:
  λ(d, h) = nivel(d) × factor_semana(d) × perfil(h) / 13 × ruido(d).
- Nivel de 180 pedidos por día con factor 1 al inicio y crecimiento del 2 % mensual (~200 al final).
- Factor semanal copiado del seeder del ERP.
- Perfil horario con un pico de media mañana (11 h) y uno mayor después del horario laboral (19 h).
- Ruido diario gamma de media 1 y CV 0,10, que agrega variación no explicada por el calendario.
- Líneas por pedido: 1 + binomial negativa con media 12, típico de una compra online de supermercado.
- Retiro con probabilidad 0,62, como en el ERP.

Resultado con la semilla acordada: 35 402 pedidos, 194,5 por día y 15 por hora en promedio, con un máximo de 47 en una hora.
El factor semanal sintético difiere del configurado en el seeder en menos de 0,02 y del observado en la base del ERP en menos de 0,07, salvo el lunes (0,87 contra 0,77, que en el ERP sale de solo 26 lunes con 1 o 2 pedidos); ver `datos/procesados/resumen_datos.csv`.

### Por qué unos 200 pedidos por día

El volumen se eligió para que la cantidad de preparadores sea una decisión con alternativas reales.
Si el tiempo medio de preparación ronda los 10 minutos (lo define la Persona B en el modelo de servicio, por ejemplo en función de `lineas`):

- un día medio tiene unos 15 pedidos por hora, una carga de unos 2,5 preparadores ocupados;
- la hora pico de un sábado tiene una tasa esperada de unos 35 pedidos por hora (carga cercana a 6), y con el ruido diario se observan horas de hasta 47;
- la dotación razonable queda entre 2 y 8 personas, con escenarios bajo, medio y alto que surgen solos del calendario (domingo, jueves, sábado).

Es la escala de un supermercado regional con venta online consolidada; cambiar `pedidos_dia_inicio` reescala todo el estudio sin tocar código.

## Salidas de `make datos`

- `datos/raw/erp_web_orders.csv`: histórico del ERP congelado (versionado).
- `datos/procesados/pedidos.csv`: pedidos sintéticos (`pedido_id`, `llegada`, `lineas`, `metodo_entrega`).
- `datos/procesados/serie_horaria.csv`: pedidos por hora de apertura, con ceros (entrada del pronóstico).
- `datos/procesados/tasa_esperada.csv`: λ(d, h) verdadera, útil para validar pronóstico y simulación.
- `datos/procesados/resumen_datos.csv`: comparación ERP vs. sintético.

Los archivos de `datos/procesados/` no se versionan: se regeneran de forma determinística.
