# IO II · Trabajo Final Integrador

Planificación de personal para la preparación de pedidos de un supermercado online mediante pronósticos y teoría de colas.

## Estructura

- `.github/workflows/`: integración continua que compila el informe en cada push y pull request.
- `config/`: parámetros del experimento.
- `datos/raw/`: datos originales, sin modificar.
- `datos/procesados/`: datos limpios generados por los scripts.
- `src/pedidos/`: paquete Python con la lógica (datos, pronóstico, colas, simulación, experimentos).
- `scripts/`: pasos numerados del pipeline que generan resultados, figuras y tablas.
- `tests/`: pruebas automáticas con pytest.
- `notebooks/`: exploración y análisis interactivo.
- `resultados/`: salidas numéricas de los experimentos.
- `docs/`: documentación de apoyo y notas del equipo.
- `informe/`: informe en LaTeX (secciones, figuras, tablas, anexos y bibliografía).

## Reproducir

```bash
pip install -r requirements.txt
nbstripout --install
make all
```

## Simular una jornada (Persona B)

Con el paquete instalado, `make test` comprueba el motor y `make verificacion` regenera las réplicas, la comparación M/M/c y la tabla utilizada por `make informe`.
Persona C puede conectar el pronóstico de A mediante esta función:

```python
from pathlib import Path

import yaml

from pedidos.simulacion import simular_jornada

config = yaml.safe_load(Path("config/experimento.yaml").read_text(encoding="utf-8"))

def evaluar_dotacion(perfil, dotacion, plazo_min, semilla):
    return simular_jornada(perfil, dotacion, plazo_min, semilla, config)
```

`perfil` es una Serie de pandas con una fecha local por hora de apertura, en orden, y la cantidad esperada de pedidos de esa franja (puede ser cero o fraccionaria).
La función devuelve el detalle por pedido y un diccionario de indicadores de jornada.
El plazo se expresa en minutos desde la llegada hasta el fin de preparación.
Para comparar dotaciones, reutilizar la misma semilla dentro de cada réplica.
Para reproducir pedidos reservados, seleccionar una jornada de `pedidos.csv`, convertirla con `preparar_traza(pedidos, apertura, config["servicio"])` y pasarla a `simular_pedidos(traza, dotacion, cierre_min)`; el cierre se expresa en minutos desde la apertura.

## Convenciones

- Una oración por línea en los `.tex`.
- Cada sección tiene un responsable, y `main.tex` no se toca salvo acuerdo.
- Las figuras y tablas se generan desde `scripts/`, nunca se editan a mano.
- Los parámetros van en `config/`, no en el código.
- Una rama por tarea y PR revisado por el compañero antes de mergear a `main`.
