from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pedidos import datos
from pedidos import pronostico as pr

RAIZ = Path(__file__).resolve().parents[1]
APERTURA, CIERRE = 8, 21


def serie_sintetica(semanas: int, valores_semana: np.ndarray | None = None) -> pd.Series:
    """Serie horaria de lunes a domingo, de 8 a 21; por defecto, un valor distinto por hora."""
    dias = pd.date_range("2026-01-05", periods=7 * semanas, freq="D")  # lunes
    indice = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dias for h in range(APERTURA, CIERRE)])
    if valores_semana is None:
        valores = np.arange(len(indice), dtype=float)
    else:
        valores = np.tile(valores_semana, semanas)
    return pd.Series(valores, index=indice, name="pedidos")


def test_ingenuo_devuelve_la_misma_hora_de_la_semana_anterior():
    serie = serie_sintetica(3)
    objetivo = pd.DatetimeIndex([pd.Timestamp("2026-01-21 10:00")])  # miércoles de la semana 3
    esperado = serie[pd.Timestamp("2026-01-14 10:00")]
    assert pr.ingenuo_estacional(serie, objetivo).iloc[0] == esperado


def test_media_promedia_los_rezagos_semanales():
    serie = serie_sintetica(3)
    t = pd.Timestamp("2026-01-21 10:00")
    esperado = (serie[t - pr.SEMANA] + serie[t - 2 * pr.SEMANA]) / 2
    assert pr.media_estacional(serie, pd.DatetimeIndex([t]), 2).iloc[0] == esperado


def test_media_sin_historia_suficiente_es_nan():
    serie = serie_sintetica(3)
    t = pd.DatetimeIndex([pd.Timestamp("2026-01-14 10:00")])  # semana 2: no hay rezago de 14 días
    assert np.isnan(pr.media_estacional(serie, t, 2).iloc[0])
    with pytest.raises(ValueError):
        pr.media_estacional(serie, t, 0)


def test_patron_semanal_exacto_no_tiene_error():
    rng = np.random.default_rng(1)
    serie = serie_sintetica(6, rng.integers(0, 30, size=7 * (CIERRE - APERTURA)))
    objetivos = serie.index[serie.index >= pd.Timestamp("2026-02-02")]  # semanas 5 y 6
    for metodo in [pr.ingenuo_estacional(serie, objetivos), pr.media_estacional(serie, objetivos, 4)]:
        assert pr.errores(serie.reindex(objetivos), metodo)["mae"] == 0


def test_errores_calculados_a_mano():
    indice = pd.DatetimeIndex(["2026-01-05 08:00", "2026-01-05 09:00", "2026-01-06 08:00", "2026-01-06 09:00"])
    real = pd.Series([10.0, 20.0, 10.0, 10.0], index=indice)
    pronostico = pd.Series([12.0, 16.0, 10.0, 13.0], index=indice)  # errores +2, -4, 0, +3
    e = pr.errores(real, pronostico)
    assert e["mae"] == pytest.approx(9 / 4)
    assert e["rmse"] == pytest.approx(np.sqrt(29 / 4))
    assert e["sesgo"] == pytest.approx(1 / 4)  # sobrestima en promedio
    assert e["mae_diario"] == pytest.approx((2 + 3) / 2)  # días: -2 y +3
    assert e["mae_relativo"] == pytest.approx((9 / 4) / 12.5)


def test_errores_rechaza_pronosticos_faltantes():
    indice = pd.DatetimeIndex(["2026-01-05 08:00"])
    with pytest.raises(ValueError):
        pr.errores(pd.Series([1.0], index=indice), pd.Series([np.nan], index=indice))


def test_particion_toma_las_ultimas_semanas_sin_solaparse():
    serie = serie_sintetica(10)
    validacion, prueba = pr.particion(serie, semanas_validacion=2, semanas_prueba=3)
    horas_semana = 7 * (CIERRE - APERTURA)
    assert len(validacion) == 2 * horas_semana
    assert len(prueba) == 3 * horas_semana
    assert validacion.max() < prueba.min()
    assert prueba.max() == serie.index.max()
    with pytest.raises(ValueError):
        pr.particion(serie, semanas_validacion=6, semanas_prueba=4)


def test_pronostico_de_la_semana_siguiente():
    serie = serie_sintetica(4)
    siguiente = pr.pronosticar_semana(serie, 2)
    assert len(siguiente) == 7 * (CIERRE - APERTURA)
    assert siguiente.index.min() == pd.Timestamp("2026-02-02 08:00")
    assert set(siguiente.index.hour) == set(range(APERTURA, CIERRE))
    assert not siguiente.isna().any()


def test_intervalo_empirico_contiene_al_pronostico_y_no_es_negativo():
    indice = pd.date_range("2026-01-05 08:00", periods=5, freq="h")
    pronostico = pd.Series([0.5, 5.0, 10.0, 15.0, 20.0], index=indice)
    residuos = pd.Series(np.linspace(-4, 6, 101))
    intervalo = pr.intervalo_empirico(pronostico, residuos, nivel=0.8)
    assert (intervalo["inferior"] <= intervalo["pronostico"]).all()
    assert (intervalo["pronostico"] <= intervalo["superior"]).all()
    assert (intervalo["inferior"] >= 0).all()
    assert intervalo.loc[indice[2], "superior"] == pytest.approx(10 + 5)


def test_sobre_los_datos_del_estudio():
    """La media elegida mejora al ingenuo en la prueba, sin bajar del piso de la tasa verdadera."""
    config = yaml.safe_load((RAIZ / "config" / "experimento.yaml").read_text())
    params = datos.ParametrosGenerador.desde_config(config)
    pedidos = datos.generar_pedidos(params)
    serie = datos.serie_horaria(pedidos["llegada"], config["datos"]["hora_apertura"], config["datos"]["hora_cierre"])
    cfg = config["pronostico"]

    validacion, prueba = pr.particion(serie, cfg["semanas_validacion"], cfg["semanas_prueba"])
    k = pr.elegir_semanas(serie, validacion, cfg["semanas_media"])
    real = serie.reindex(prueba)

    mae_media = pr.errores(real, pr.media_estacional(serie, prueba, k))["mae"]
    mae_ingenuo = pr.errores(real, pr.ingenuo_estacional(serie, prueba))["mae"]
    mae_tasa = pr.errores(real, datos.tasa_esperada(params).reindex(prueba))["mae"]
    assert mae_tasa < mae_media < mae_ingenuo
