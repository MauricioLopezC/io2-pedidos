"""Pronóstico de pedidos por hora con métodos estacionales simples.

Los dos métodos de la propuesta (Hyndman y Athanasopoulos, FPP3, cap. 5) usan solo
rezagos de semanas completas:

- ingenuo estacional: la misma hora del mismo día de la semana anterior;
- media estacional: el promedio de esa hora y día en las últimas k semanas.

Como el rezago mínimo es de 7 días, el pronóstico de una semana entera hecho al inicio
de esa semana usa solo datos pasados: alcanza con reindexar la serie desplazada, sin un
bucle de origen móvil.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEMANA = pd.Timedelta(days=7)


def media_estacional(serie: pd.Series, objetivos: pd.DatetimeIndex, semanas: int) -> pd.Series:
    """Promedio de la serie en las mismas horas de las `semanas` semanas anteriores.

    Devuelve NaN en los instantes a los que les falta alguno de los rezagos.
    """
    if semanas < 1:
        raise ValueError("semanas debe ser al menos 1")
    objetivos = pd.DatetimeIndex(objetivos)
    rezagos = [serie.reindex(objetivos - j * SEMANA).to_numpy(dtype=float) for j in range(1, semanas + 1)]
    valores = np.mean(rezagos, axis=0)
    return pd.Series(valores, index=objetivos, name=f"media_{semanas}s")


def ingenuo_estacional(serie: pd.Series, objetivos: pd.DatetimeIndex) -> pd.Series:
    """Valor de la misma hora una semana antes."""
    return media_estacional(serie, objetivos, 1).rename("ingenuo")


def errores(real: pd.Series, pronostico: pd.Series) -> dict[str, float]:
    """Métricas de error; el sesgo es pronóstico − real (positivo = sobrestima)."""
    real, pronostico = real.align(pronostico, join="inner")
    if pronostico.isna().any():
        raise ValueError("el pronóstico tiene valores faltantes en el período evaluado")
    error = pronostico - real
    diario = error.groupby(error.index.normalize()).sum()
    mae = error.abs().mean()
    return {
        "mae": mae,
        "rmse": float(np.sqrt((error**2).mean())),
        "sesgo": error.mean(),
        "mae_diario": diario.abs().mean(),
        "mae_relativo": mae / real.mean(),
    }


def particion(
    serie: pd.Series, semanas_validacion: int, semanas_prueba: int
) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """Índices de validación y prueba: las últimas semanas completas de la serie, en orden."""
    ultimo_dia = serie.index.max().normalize()
    inicio_prueba = ultimo_dia + pd.Timedelta(days=1) - semanas_prueba * SEMANA
    inicio_validacion = inicio_prueba - semanas_validacion * SEMANA
    if inicio_validacion <= serie.index.min():
        raise ValueError("la serie es demasiado corta para esa partición")

    indice = serie.index
    validacion = indice[(indice >= inicio_validacion) & (indice < inicio_prueba)]
    prueba = indice[indice >= inicio_prueba]
    return validacion, prueba


def elegir_semanas(serie: pd.Series, objetivos: pd.DatetimeIndex, candidatos: list[int]) -> int:
    """Cantidad de semanas de la media estacional con menor MAE en `objetivos`."""
    real = serie.reindex(objetivos)
    mae = {k: errores(real, media_estacional(serie, objetivos, k))["mae"] for k in candidatos}
    return min(mae, key=mae.get)


def horas_siguientes(serie: pd.Series, dias: int = 7) -> pd.DatetimeIndex:
    """Horas de apertura de los `dias` días posteriores al último de la serie."""
    horas = sorted(serie.index.hour.unique())
    primer_dia = serie.index.max().normalize() + pd.Timedelta(days=1)
    fechas = pd.date_range(primer_dia, periods=dias, freq="D")
    return pd.DatetimeIndex([f + pd.Timedelta(hours=h) for f in fechas for h in horas], name="hora")


def pronosticar_semana(serie: pd.Series, semanas: int) -> pd.Series:
    """Pronóstico de la semana posterior a la serie con la media estacional de `semanas`."""
    return media_estacional(serie, horas_siguientes(serie), semanas).rename("pronostico")


def intervalo_empirico(pronostico: pd.Series, residuos: pd.Series, nivel: float) -> pd.DataFrame:
    """Intervalo sumando cuantiles de residuos (real − pronóstico) ya observados.

    Supone que los errores de la semana pronosticada se parecen a los del período usado
    para obtener los residuos. Los límites se recortan en 0 porque no hay pedidos negativos.
    """
    alfa = (1 - nivel) / 2
    inferior, superior = residuos.quantile([alfa, 1 - alfa])
    return pd.DataFrame(
        {
            "pronostico": pronostico,
            "inferior": (pronostico + inferior).clip(lower=0),
            "superior": (pronostico + superior).clip(lower=0),
        }
    )
