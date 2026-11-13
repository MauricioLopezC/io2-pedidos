"""Pruebas del módulo de experimentos, recomendación, contraste en prueba y sensibilidad."""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from pedidos import experimentos as exp

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def config():
    return yaml.safe_load((RAIZ / "config" / "experimento.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pronostico_semana():
    return pd.read_csv(
        RAIZ / "resultados" / "pronostico_semana_siguiente.csv",
        index_col="hora",
        parse_dates=["hora"],
    )


def test_generar_semillas_reproducibles_y_unicas():
    s1 = exp.generar_semillas(20261112, 10)
    s2 = exp.generar_semillas(20261112, 10)
    assert s1 == s2
    assert len(set(s1)) == 10
    with pytest.raises(ValueError):
        exp.generar_semillas(20261112, 0)


def test_perfil_jornada_extrae_dia_y_valida(pronostico_semana):
    serie = exp.perfil_jornada(pronostico_semana, "2026-10-24", "pronostico")
    assert len(serie) == 13
    assert serie.sum() == pytest.approx(300.5)
    with pytest.raises(ValueError, match="columna"):
        exp.perfil_jornada(pronostico_semana, "2026-10-24", "inexistente")
    with pytest.raises(ValueError, match="No hay horas"):
        exp.perfil_jornada(pronostico_semana, "2026-12-31", "pronostico")


def test_numeros_aleatorios_comunes_y_monotonia(pronostico_semana, config):
    perfil = exp.perfil_jornada(pronostico_semana, "2026-10-22")
    semillas = exp.generar_semillas(12345, 5)
    dotaciones = [2, 4, 6]
    replicas = exp.simular_escenario(perfil, dotaciones, 30.0, semillas, config)

    # En cada réplica todas las dotaciones reciben exactamente la misma cantidad de pedidos.
    for _, grupo in replicas.groupby("replica"):
        assert grupo["llegados"].nunique() == 1
        assert grupo["espera_media_min"].is_monotonic_decreasing
        assert grupo["cola_media"].is_monotonic_decreasing
        assert grupo["proporcion_a_tiempo"].is_monotonic_increasing

    resumen = exp.resumir_escenario(replicas, 0.90)
    assert resumen["espera_media_min"].is_monotonic_decreasing
    assert resumen["proporcion_a_tiempo"].is_monotonic_increasing


def test_elegir_dotacion_con_y_sin_cumplimiento():
    df = pd.DataFrame(
        {
            "escenario": ["alta", "alta", "alta"],
            "fecha": ["2026-10-24"] * 3,
            "demanda_pronosticada": [300.5] * 3,
            "pico_horario": [38.25] * 3,
            "dotacion": [3, 4, 5],
            "espera_media_min": [25.0, 8.0, 3.0],
            "total_medio_min": [35.0, 18.0, 13.0],
            "proporcion_a_tiempo": [0.45, 0.91, 0.98],
            "cola_media": [6.0, 1.5, 0.5],
            "utilizacion": [0.95, 0.78, 0.62],
            "pendientes_al_cierre": [12.0, 2.0, 0.5],
        }
    )
    assert exp.elegir_dotacion(df, 0.90) == 4
    tabla_ok = exp.tabla_recomendaciones(df, 0.90)
    assert bool(tabla_ok.loc[0, "cumple_objetivo"]) is True
    assert tabla_ok.loc[0, "dotacion_recomendada"] == 4

    # Si se exige 99 %, ninguna de las dotaciones evaluadas (3, 4, 5) alcanza el objetivo.
    assert exp.elegir_dotacion(df, 0.99) is None
    tabla_no = exp.tabla_recomendaciones(df, 0.99)
    assert bool(tabla_no.loc[0, "cumple_objetivo"]) is False
    assert pd.isna(tabla_no.loc[0, "dotacion_recomendada"])
    assert tabla_no.loc[0, "dotacion_evaluada"] == 5


def test_evaluar_escenarios_coherencia(pronostico_semana, config):
    cfg_rapida = {
        **config,
        "experimentos": {**config["experimentos"], "replicas": 8, "dotaciones": [2, 3, 4, 5, 6, 7]},
    }
    replicas, resumen = exp.evaluar_escenarios(pronostico_semana, cfg_rapida)
    assert set(resumen["escenario"]) == {"baja", "media", "alta"}
    assert (resumen["llegados"] == resumen["preparados_al_cierre"] + resumen["pendientes_al_cierre"]).all()

    rec = exp.tabla_recomendaciones(resumen, cfg_rapida["experimentos"]["cumplimiento_min"]).set_index("escenario")
    assert rec.loc["baja", "demanda_pronosticada"] < rec.loc["media", "demanda_pronosticada"]
    assert rec.loc["media", "demanda_pronosticada"] < rec.loc["alta", "demanda_pronosticada"]
    assert rec.loc["baja", "dotacion_recomendada"] <= rec.loc["media", "dotacion_recomendada"]
    assert rec.loc["media", "dotacion_recomendada"] <= rec.loc["alta", "dotacion_recomendada"]


def test_sensibilidad_conserva_llegadas_y_monotonia(pronostico_semana, config):
    cfg_rapida = {
        **config,
        "experimentos": {
            **config["experimentos"],
            "escenarios": {"media": "2026-10-22"},
            "dotaciones": [3, 4, 5],
            "replicas": 6,
        },
        "sensibilidad": {
            "curvas_pronostico": ["inferior", "pronostico", "superior"],
            "factores_demanda": [0.90, 1.00, 1.20],
            "factores_servicio": [0.80, 1.00, 1.20],
        },
    }
    dem_detalle, _ = exp.analizar_sensibilidad_demanda(pronostico_semana, cfg_rapida)
    srv_detalle, _ = exp.analizar_sensibilidad_servicio(pronostico_semana, cfg_rapida)

    # En sensibilidad al servicio, la cantidad media de pedidos llegados no cambia entre factores.
    assert srv_detalle["llegados"].nunique() == 1

    # Para una dotación fija, un servicio más lento incrementa la espera media y reduce la proporción a tiempo.
    c4_srv = srv_detalle.loc[srv_detalle["dotacion"] == 4].sort_values("factor_servicio")
    assert c4_srv["espera_media_min"].is_monotonic_increasing
    assert c4_srv["proporcion_a_tiempo"].is_monotonic_decreasing

    # Para una dotación fija, mayor factor de demanda incrementa la espera media.
    c4_dem = dem_detalle.loc[
        (dem_detalle["tipo"] == "factor_demanda") & (dem_detalle["dotacion"] == 4)
    ].sort_values("demanda_diaria")
    assert c4_dem["espera_media_min"].is_monotonic_increasing


def test_contrastar_en_prueba_conserva_pedidos():
    fechas = pd.date_range("2026-10-01", "2026-10-18", freq="D")
    filas = []
    pedido_id = 1
    for fecha in fechas:
        for hora in [9, 11, 18, 19]:
            filas.append(
                {
                    "pedido_id": pedido_id,
                    "llegada": fecha + pd.Timedelta(hours=hora, minutes=10),
                    "lineas": 10,
                    "metodo_entrega": "retiro",
                }
            )
            pedido_id += 1
    pedidos = pd.DataFrame(filas)
    cfg = {
        "datos": {"hora_apertura": 8, "hora_cierre": 21},
        "pronostico": {"semanas_prueba": 2},
        "servicio": {"minutos_fijos": 4.0, "minutos_por_linea": 0.5},
        "experimentos": {
            "plazo_min": 30.0,
            "cumplimiento_min": 0.90,
            "escenarios": {"baja": "2026-10-25", "media": "2026-10-22", "alta": "2026-10-24"},
            "dotaciones": [1, 2],
        },
    }
    resumen = exp.contrastar_en_prueba(pedidos, cfg)
    assert set(resumen["escenario"]) == {"baja", "media", "alta"}
    assert (resumen["llegados"] == 4.0).all()
    assert (resumen["espera_media_min"] == 0.0).all()
