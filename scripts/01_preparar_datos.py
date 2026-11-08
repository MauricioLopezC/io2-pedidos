"""Paso 1: congela el histórico del ERP y genera el histórico sintético del estudio.

Salidas:
- datos/raw/erp_web_orders.csv: pedidos online del ERP (solo si se pasa --desde-erp o
  todavía no existe y la base está disponible). Se versiona.
- datos/procesados/pedidos.csv: pedidos sintéticos (llegada, líneas, método de entrega).
- datos/procesados/serie_horaria.csv: pedidos por hora de apertura, con ceros.
- datos/procesados/tasa_esperada.csv: λ(d, h) verdadera del generador, para validar.
- datos/procesados/resumen_datos.csv: indicadores ERP vs. sintético.

Uso: python scripts/01_preparar_datos.py [--desde-erp]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

from pedidos import datos

RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "datos" / "procesados"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--desde-erp",
        action="store_true",
        help="vuelve a exportar el histórico desde la base SQLite del ERP",
    )
    args = parser.parse_args()

    config = yaml.safe_load((RAIZ / "config" / "experimento.yaml").read_text())
    cfg = config["datos"]
    apertura, cierre = cfg["hora_apertura"], cfg["hora_cierre"]

    erp_csv = RAIZ / cfg["erp_csv"]
    if args.desde_erp or not erp_csv.exists():
        erp = datos.leer_erp_sqlite(cfg["erp_sqlite"])
        erp_csv.parent.mkdir(parents=True, exist_ok=True)
        erp.to_csv(erp_csv, index=False)
        print(f"ERP exportado: {len(erp)} pedidos -> {erp_csv.relative_to(RAIZ)}")
    erp = datos.leer_erp_csv(erp_csv)

    params = datos.ParametrosGenerador.desde_config(config)
    pedidos = datos.generar_pedidos(params)
    serie = datos.serie_horaria(pedidos["llegada"], apertura, cierre)
    tasa = datos.tasa_esperada(params)

    PROCESADOS.mkdir(parents=True, exist_ok=True)
    pedidos.to_csv(PROCESADOS / "pedidos.csv", index=False)
    serie.to_csv(PROCESADOS / "serie_horaria.csv")
    tasa.rename_axis("hora").to_csv(PROCESADOS / "tasa_esperada.csv")

    tabla = pd.DataFrame(
        {
            "erp": datos.resumen(erp, apertura, cierre),
            "sintetico": datos.resumen(pedidos, apertura, cierre),
        }
    )
    semanal = pd.DataFrame(
        {"erp": datos.factor_semanal(erp["llegada"]), "sintetico": datos.factor_semanal(pedidos["llegada"])}
    )
    semanal.index = [f"factor_dia_{d}" for d in semanal.index]
    tabla = pd.concat([tabla, semanal])
    tabla.to_csv(PROCESADOS / "resumen_datos.csv")

    print(f"Sintético: {len(pedidos)} pedidos en {len(serie) // (cierre - apertura)} días")
    print(tabla.round(3).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
