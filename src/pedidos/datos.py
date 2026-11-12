"""Datos de pedidos online: histórico del ERP y generador sintético propio.

El ERP La Linda tiene unos 2 pedidos online por día, repartidos de manera uniforme entre
las 8 y las 16 horas y sin tiempos de preparación reales (ver docs/inspeccion-erp.md).
Por eso su histórico se congela en un CSV y se usa para describir y calibrar, mientras
que el estudio trabaja sobre un histórico sintético con el mismo calendario semanal,
escalado y con un perfil horario con picos.

Todas las marcas de tiempo son horas locales (America/Argentina/Buenos_Aires) sin zona.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNAS_PEDIDOS = ["pedido_id", "llegada", "lineas", "metodo_entrega"]

_CONSULTA_ERP = """
select w.id                     as pedido_id,
       w.placed_at              as llegada,
       w.paid_at                as pago,
       w.preparation_started_at as inicio_preparacion,
       w.delivered_at           as entrega,
       w.status                 as estado,
       w.delivery_method        as metodo_entrega,
       w.total_amount           as importe,
       count(i.id)              as lineas,
       sum(i.quantity)          as unidades
from web_orders w
join web_order_items i on i.web_order_id = w.id
group by w.id
order by w.placed_at, w.id
"""


# --- Histórico del ERP --------------------------------------------------------


def leer_erp_sqlite(ruta: str | Path) -> pd.DataFrame:
    """Lee los pedidos online del ERP en modo solo lectura, sin datos del cliente."""
    ruta = Path(ruta).expanduser()
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró la base del ERP en {ruta}")

    with sqlite3.connect(f"file:{ruta}?mode=ro", uri=True) as conexion:
        pedidos = pd.read_sql(_CONSULTA_ERP, conexion)

    return _tipar_erp(pedidos)


def leer_erp_csv(ruta: str | Path) -> pd.DataFrame:
    """Lee el histórico del ERP congelado en datos/raw."""
    return _tipar_erp(pd.read_csv(ruta))


def _tipar_erp(pedidos: pd.DataFrame) -> pd.DataFrame:
    pedidos = pedidos.copy()
    for columna in ["llegada", "pago", "inicio_preparacion", "entrega"]:
        pedidos[columna] = pd.to_datetime(pedidos[columna])
    return pedidos


# --- Generador sintético ------------------------------------------------------


@dataclass(frozen=True)
class ParametrosGenerador:
    """Parámetros del histórico sintético; ver la sección datos.generador del YAML."""

    semilla: int
    fecha_inicio: pd.Timestamp
    semanas: int
    pedidos_dia_inicio: float
    crecimiento_mensual: float
    cv_ruido_diario: float
    factor_dia_semana: dict[int, float]
    perfil_horario: dict[int, float]
    lineas_media: float
    lineas_dispersion: float
    proporcion_retiro: float

    @classmethod
    def desde_config(cls, config: dict) -> ParametrosGenerador:
        g = config["datos"]["generador"]
        return cls(
            semilla=int(g["semilla"]),
            fecha_inicio=pd.Timestamp(g["fecha_inicio"]),
            semanas=int(g["semanas"]),
            pedidos_dia_inicio=float(g["pedidos_dia_inicio"]),
            crecimiento_mensual=float(g["crecimiento_mensual"]),
            cv_ruido_diario=float(g["cv_ruido_diario"]),
            factor_dia_semana={int(k): float(v) for k, v in g["factor_dia_semana"].items()},
            perfil_horario={int(k): float(v) for k, v in g["perfil_horario"].items()},
            lineas_media=float(g["lineas_media"]),
            lineas_dispersion=float(g["lineas_dispersion"]),
            proporcion_retiro=float(g["proporcion_retiro"]),
        )

    def perfil_normalizado(self) -> pd.Series:
        """Peso de cada hora de apertura con media 1 (suma = cantidad de horas)."""
        perfil = pd.Series(self.perfil_horario).sort_index()
        return perfil / perfil.mean()


def tasa_esperada(params: ParametrosGenerador) -> pd.Series:
    """Pedidos esperados por hora, λ(d, h), sin el ruido diario.

    Es la tasa del proceso de Poisson no homogéneo que usa el generador:
    nivel inicial × crecimiento × factor del día de la semana × perfil horario / horas.
    """
    perfil = params.perfil_normalizado()
    dias = pd.date_range(params.fecha_inicio, periods=params.semanas * 7, freq="D")

    meses = np.arange(len(dias)) / 30
    nivel = params.pedidos_dia_inicio * (1 + params.crecimiento_mensual) ** meses
    factor = np.array([params.factor_dia_semana[d.isoweekday()] for d in dias])
    por_dia = pd.Series(nivel * factor, index=dias)

    indice = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dias for h in perfil.index])
    valores = [por_dia[d] * peso / len(perfil) for d in dias for peso in perfil.to_numpy()]
    return pd.Series(valores, index=indice, name="tasa")


def generar_lineas(rng: np.random.Generator, cantidad: int, media: float, dispersion: float) -> np.ndarray:
    """Suma una línea a una binomial negativa para obtener pedidos de tamaño positivo."""
    if not np.isfinite(media) or media < 1 or not np.isfinite(dispersion) or dispersion <= 0:
        raise ValueError("La media de líneas debe ser al menos uno y la dispersión positiva.")
    p = dispersion / (dispersion + (media - 1))
    return 1 + rng.negative_binomial(dispersion, p, size=cantidad)


def generar_pedidos(params: ParametrosGenerador) -> pd.DataFrame:
    """Genera el histórico sintético de pedidos online.

    Dentro de cada hora la tasa es constante, así que la cantidad de llegadas es Poisson y
    los instantes son uniformes en la hora. Un factor gamma de media 1 por día agrega la
    variación que el calendario no explica.
    """
    rng = np.random.default_rng(params.semilla)
    tasa = tasa_esperada(params)

    dias = tasa.index.normalize()
    ruido = _factor_ruido(rng, params.cv_ruido_diario, dias.unique())
    lam = tasa.to_numpy() * ruido.reindex(dias).to_numpy()
    cantidades = rng.poisson(lam)

    inicio_hora = np.repeat(tasa.index.to_numpy(), cantidades)
    segundos = rng.uniform(0, 3600, size=len(inicio_hora))
    llegada = pd.to_datetime(inicio_hora) + pd.to_timedelta(segundos, unit="s")
    llegada = llegada.floor("s").sort_values()

    n = len(llegada)
    lineas = generar_lineas(rng, n, params.lineas_media, params.lineas_dispersion)
    retiro = rng.random(n) < params.proporcion_retiro

    return pd.DataFrame(
        {
            "pedido_id": np.arange(1, n + 1),
            "llegada": llegada,
            "lineas": lineas,
            "metodo_entrega": np.where(retiro, "retiro", "envio"),
        }
    )


def _factor_ruido(rng: np.random.Generator, cv: float, dias: pd.DatetimeIndex) -> pd.Series:
    if cv <= 0:
        return pd.Series(1.0, index=dias)
    forma = 1 / cv**2
    return pd.Series(rng.gamma(forma, 1 / forma, size=len(dias)), index=dias)


# --- Series y resúmenes -------------------------------------------------------


def serie_horaria(llegadas: pd.Series, hora_apertura: int, hora_cierre: int) -> pd.Series:
    """Cuenta pedidos por hora de apertura, completando con ceros las horas sin pedidos.

    Las llegadas fuera de [hora_apertura, hora_cierre) se descartan: el sector de
    preparación no trabaja en ese horario.
    """
    llegadas = pd.to_datetime(pd.Series(llegadas))
    horas = llegadas.dt.floor("h")
    horas = horas[(horas.dt.hour >= hora_apertura) & (horas.dt.hour < hora_cierre)]

    dias = pd.date_range(llegadas.min().normalize(), llegadas.max().normalize(), freq="D")
    indice = pd.DatetimeIndex(
        [d + pd.Timedelta(hours=h) for d in dias for h in range(hora_apertura, hora_cierre)]
    )
    serie = horas.value_counts().reindex(indice, fill_value=0).astype(int)
    serie.index.name = "hora"
    serie.name = "pedidos"
    return serie


def factor_semanal(llegadas: pd.Series) -> pd.Series:
    """Pedidos medios por día de la semana (1 = lunes) relativos al jueves."""
    diarios = pd.to_datetime(pd.Series(llegadas)).dt.normalize().value_counts().sort_index()
    diarios = diarios.reindex(pd.date_range(diarios.index.min(), diarios.index.max()), fill_value=0)
    medias = diarios.groupby(diarios.index.day_of_week + 1).mean()
    return medias / medias[4]


def resumen(pedidos: pd.DataFrame, hora_apertura: int, hora_cierre: int) -> dict[str, float]:
    """Indicadores para comparar el histórico del ERP con el sintético."""
    llegadas = pedidos["llegada"]
    diarios = llegadas.dt.normalize().value_counts()
    diarios = diarios.reindex(pd.date_range(diarios.index.min(), diarios.index.max()), fill_value=0)
    horaria = serie_horaria(llegadas, hora_apertura, hora_cierre)
    return {
        "pedidos": len(pedidos),
        "dias": len(diarios),
        "pedidos_dia_media": diarios.mean(),
        "pedidos_dia_varianza": diarios.var(),
        "horas_de_atencion": len(horaria),
        "pedidos_hora_media": horaria.mean(),
        "pedidos_hora_max": horaria.max(),
        "horas_sin_pedidos": (horaria == 0).mean(),
        "lineas_media": pedidos["lineas"].mean(),
        "proporcion_retiro": (pedidos["metodo_entrega"] == "retiro").mean(),
    }
