from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
import yaml

from pedidos import datos

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def config():
    return yaml.safe_load((RAIZ / "config" / "experimento.yaml").read_text())


@pytest.fixture(scope="module")
def params(config):
    return datos.ParametrosGenerador.desde_config(config)


@pytest.fixture(scope="module")
def pedidos(params):
    return datos.generar_pedidos(params)


def test_misma_semilla_mismo_historico(params, pedidos):
    pd.testing.assert_frame_equal(datos.generar_pedidos(params), pedidos)


def test_otra_semilla_otro_historico(params, pedidos):
    otro = datos.generar_pedidos(replace(params, semilla=params.semilla + 1))
    assert len(otro) != len(pedidos) or not otro["llegada"].equals(pedidos["llegada"])


def test_columnas_y_tipos(pedidos):
    assert list(pedidos.columns) == datos.COLUMNAS_PEDIDOS
    assert pedidos["pedido_id"].is_unique
    assert pedidos["llegada"].is_monotonic_increasing
    assert (pedidos["lineas"] >= 1).all()
    assert set(pedidos["metodo_entrega"]) <= {"retiro", "envio"}


def test_llegadas_dentro_del_horario_y_periodo(config, params, pedidos):
    horas = pedidos["llegada"].dt.hour
    assert horas.min() >= config["datos"]["hora_apertura"]
    assert horas.max() < config["datos"]["hora_cierre"]
    assert pedidos["llegada"].min() >= params.fecha_inicio
    assert pedidos["llegada"].max() < params.fecha_inicio + pd.Timedelta(weeks=params.semanas)


def test_tasa_esperada_coincide_con_parametros(params):
    tasa = datos.tasa_esperada(params)
    horas = len(params.perfil_horario)
    assert len(tasa) == params.semanas * 7 * horas
    # Primer día (lunes): nivel inicial × factor del lunes, repartido en el perfil.
    primer_dia = tasa.iloc[:horas].sum()
    assert primer_dia == pytest.approx(params.pedidos_dia_inicio * params.factor_dia_semana[1])


def test_volumen_simulado_cercano_al_esperado(params, pedidos):
    esperado = datos.tasa_esperada(params).sum()
    # Con ruido diario de CV 0,10 sobre 182 días el error relativo del total es ~1 %.
    assert len(pedidos) == pytest.approx(esperado, rel=0.03)


def test_serie_horaria_conserva_pedidos_y_completa_ceros():
    llegadas = pd.Series(pd.to_datetime(["2026-01-05 08:10", "2026-01-05 08:50", "2026-01-06 10:00", "2026-01-06 22:00"]))
    serie = datos.serie_horaria(llegadas, hora_apertura=8, hora_cierre=11)
    assert len(serie) == 2 * 3
    assert serie.sum() == 3  # la de las 22 queda fuera de horario
    assert serie[pd.Timestamp("2026-01-05 08:00")] == 2
    assert serie[pd.Timestamp("2026-01-05 09:00")] == 0


def test_factor_semanal_reproduce_el_del_erp(params, pedidos):
    observado = datos.factor_semanal(pedidos["llegada"])
    esperado = pd.Series(params.factor_dia_semana) / params.factor_dia_semana[4]
    # El crecimiento dentro de la semana y el ruido desvían unos pocos puntos.
    assert observado.to_numpy() == pytest.approx(esperado.sort_index().to_numpy(), abs=0.05)


def test_lineas_y_retiro_segun_parametros(params, pedidos):
    assert pedidos["lineas"].mean() == pytest.approx(params.lineas_media, rel=0.02)
    retiro = (pedidos["metodo_entrega"] == "retiro").mean()
    assert retiro == pytest.approx(params.proporcion_retiro, abs=0.01)


def test_erp_congelado_es_legible(config):
    erp = datos.leer_erp_csv(RAIZ / config["datos"]["erp_csv"])
    assert len(erp) > 0
    pagados = erp.dropna(subset=["pago"])  # un pedido quedó pendiente de pago
    assert (pagados["llegada"] <= pagados["pago"]).all()
    assert "customer_id" not in erp.columns
