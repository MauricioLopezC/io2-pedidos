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

## Convenciones

- Una oración por línea en los `.tex`.
- Cada sección tiene un responsable, y `main.tex` no se toca salvo acuerdo.
- Las figuras y tablas se generan desde `scripts/`, nunca se editan a mano.
- Los parámetros van en `config/`, no en el código.
- Una rama por tarea y PR revisado por el compañero antes de mergear a `main`.
