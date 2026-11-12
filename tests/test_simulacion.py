"""Trazas manuales de jornada y contraste estacionario reproducible."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pedidos.simulacion import resumir_jornada, simular_jornada, simular_pedidos
from pedidos.verificacion import verificar_mmc

CONFIG = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/experimento.yaml").read_text(encoding="utf-8"))


def traza(llegadas, servicios):
    return pd.DataFrame({"pedido_id": range(len(llegadas)), "llegada_min": llegadas, "servicio_min": servicios})


def test_cruce_de_hora():
    # Apertura a las 9:00. Se conserva la ocupación a las 10:00.
    detalle = simular_pedidos(traza([58, 61], [6, 4]), 1, 120)
    assert detalle.inicio_min.tolist() == [58, 64]
    assert detalle.fin_min.tolist() == [64, 68]
    assert detalle.espera_min.tolist() == [0, 3]
    assert detalle.total_min.tolist() == [6, 7]


def test_cierre_con_espera_y_fin_exacto():
    detalle = simular_pedidos(traza([0, 1, 1], [5, 3, 3]), 1, 5)
    assert detalle.inicio_min.tolist() == [0, 5, 8]
    resumen = resumir_jornada(detalle, 1, 5, 7)
    assert resumen["llegados"] == 3
    assert resumen["preparados_al_cierre"] == resumen["en_fila_al_cierre"] == resumen["en_preparacion_al_cierre"] == 1
    assert resumen["pendientes_al_cierre"] == 2
    assert resumen["cola_media"] == pytest.approx(8 / 5)
    assert resumen["utilizacion"] == 1
    assert resumen["proporcion_a_tiempo"] == pytest.approx(2 / 3)


@pytest.mark.parametrize("llegadas, dotacion", [([3], 1), ([0, 0, 3], 3)])
def test_servicio_inmediato(llegadas, dotacion):
    detalle = simular_pedidos(traza(llegadas, [5] * len(llegadas)), dotacion, 10)
    assert (detalle.espera_min == 0).all()


@pytest.mark.parametrize("llegadas, servicios", [([5], [1]), ([-1], [2]), ([0], [0]), ([1], [float("inf")])])
def test_rechaza_traza_invalida(llegadas, servicios):
    with pytest.raises(ValueError):
        simular_pedidos(traza(llegadas, servicios), 1, 5)


def perfil_diario(tasa):
    datos = CONFIG["datos"]
    horas = datos["hora_cierre"] - datos["hora_apertura"]
    apertura = pd.Timestamp("2026-11-09") + pd.Timedelta(hours=datos["hora_apertura"])
    return pd.Series(tasa, index=pd.date_range(apertura, periods=horas, freq="h"))


def test_jornada_vacia():
    detalle, resumen = simular_jornada(perfil_diario(0), 2, 10, 123, CONFIG)
    assert detalle.empty
    assert resumen["llegados"] == resumen["cola_media"] == resumen["utilizacion"] == 0
    assert np.isnan(resumen["proporcion_a_tiempo"])


def test_semillas_comunes_y_sensibilidad():
    perfil = perfil_diario(12)
    perfil.iloc[0] = 0
    detalle, resumen = simular_jornada(perfil, 1, 10, 123, CONFIG)
    otro, repetido = simular_jornada(perfil, 1, 10, 123, CONFIG)
    pd.testing.assert_frame_equal(detalle, otro)
    assert repetido == resumen
    variante = {**CONFIG, "servicio": {"minutos_fijos": 1, "minutos_por_linea": 1}}
    alternativo, _ = simular_jornada(perfil, 3, 10, 123, variante)
    columnas = ["pedido_id", "llegada_min", "lineas"]
    pd.testing.assert_frame_equal(detalle[columnas], alternativo[columnas])
    assert (alternativo.servicio_min == 1 + alternativo.lineas).all()
    assert (detalle.llegada_min >= 60).all()


def test_rechaza_hora_faltante():
    with pytest.raises(ValueError, match="todas las horas"):
        simular_jornada(perfil_diario(1).iloc[:-1], 1, 10, 123, CONFIG)


def test_contraste_mmc_y_little():
    # Exige que los 6 IC del 99 % contengan la teoría a la vez. Con la semilla de
    # config es determinístico; si se cambia la sección verificacion, un fallo
    # aislado puede ser azar (~6 %) y conviene probar otra semilla antes de buscar un error.
    replicas, tabla = verificar_mmc(CONFIG["verificacion"])
    assert replicas.semilla.is_unique
    assert tabla.contiene_teoria.all(), tabla
