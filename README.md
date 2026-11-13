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
nbstripout --install   # solo para desarrollar: limpia las salidas de los notebooks al commitear
make all
```

`notebooks/recorrido.ipynb` (`make notebook`) vuelve a correr el pipeline y comprueba que los resultados coincidan con los versionados.
Después recorre datos, pronóstico, verificación, experimentos y sensibilidad.
Al final permite cambiar plazo, cumplimiento, demanda o servicio sobre una copia de la configuración, sin afectar los resultados del informe.

## Entrega

```bash
git tag v1.0-entrega          # fijar la versión que se entrega
make entrega REF=v1.0-entrega
```

`scripts/entrega.py` extrae esa versión en una carpeta temporal, compila el informe, ejecuta el notebook y verifica que los resultados regenerados sean idénticos a los versionados.
Si coinciden, genera `entrega/io2-pedidos-<versión>.zip` con los archivos versionados más el PDF, los datos procesados y el notebook con sus salidas.

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
