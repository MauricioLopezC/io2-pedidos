"""Simulación FIFO de jornadas con arrastre entre horas y vaciado después del cierre.

Los instantes y duraciones del motor se expresan en minutos desde la apertura.
La misma traza puede reutilizarse al variar la dotación, incluso en sobrecarga.
"""

from collections.abc import Generator

import numpy as np
import pandas as pd
import simpy

from .colas import validar_dotacion
from .datos import generar_lineas


def simular_pedidos(pedidos: pd.DataFrame, dotacion: int, cierre_min: float) -> pd.DataFrame:
    """Atiende pedido_id, llegada_min y servicio_min en FIFO; los empates siguen el orden de entrada."""
    validar_dotacion(dotacion)
    if not np.isfinite(cierre_min) or cierre_min <= 0:
        raise ValueError("El cierre debe ser positivo y finito.")
    detalle = pedidos.astype({"llegada_min": float, "servicio_min": float})
    detalle = detalle.sort_values("llegada_min", kind="stable").reset_index(drop=True)
    llegada = detalle["llegada_min"].to_numpy(dtype=float)
    servicio = detalle["servicio_min"].to_numpy(dtype=float)
    if detalle["pedido_id"].isna().any() or not detalle["pedido_id"].is_unique:
        raise ValueError("Se requiere un identificador único por pedido.")
    if not np.isfinite(llegada).all() or np.any((llegada < 0) | (llegada >= cierre_min)):
        raise ValueError("Las llegadas deben pertenecer a [apertura, cierre).")
    if not np.isfinite(servicio).all() or np.any(servicio <= 0):
        raise ValueError("La duración del servicio debe ser positiva y finita.")

    entorno = simpy.Environment()
    preparadores = simpy.Resource(entorno, capacity=int(dotacion))
    inicio = np.empty(len(detalle))
    fin = np.empty(len(detalle))

    def atender(i: int) -> Generator:
        yield entorno.timeout(llegada[i])
        with preparadores.request() as turno:
            yield turno
            inicio[i] = entorno.now
            yield entorno.timeout(servicio[i])
            fin[i] = entorno.now

    for i in range(len(detalle)):
        entorno.process(atender(i))
    entorno.run()
    espera = inicio - llegada
    return detalle.assign(inicio_min=inicio, fin_min=fin, espera_min=espera, total_min=espera + servicio)


def ocupacion(detalle: pd.DataFrame, desde_min: float, hasta_min: float, dotacion: int) -> dict[str, float]:
    """Integra personas y pedidos en la ventana, aun si llegaron antes o terminan después."""
    duracion = hasta_min - desde_min
    llegada = detalle["llegada_min"].clip(desde_min, hasta_min)
    inicio = detalle["inicio_min"].clip(desde_min, hasta_min)
    fin = detalle["fin_min"].clip(desde_min, hasta_min)
    return {
        "cola_media": (inicio - llegada).sum() / duracion,
        "utilizacion": (fin - inicio).sum() / (dotacion * duracion),
        "sistema_medio": (fin - llegada).sum() / duracion,
    }


def preparar_traza(pedidos: pd.DataFrame, apertura: pd.Timestamp, servicio: dict) -> pd.DataFrame:
    """Convierte pedidos con llegada local y líneas (generados o reservados) a minutos del motor."""
    fijo = servicio["minutos_fijos"]
    por_linea = servicio["minutos_por_linea"]
    if not np.isfinite([fijo, por_linea]).all() or min(fijo, por_linea) < 0 or fijo + por_linea <= 0:
        raise ValueError("Los tiempos de servicio deben ser no negativos y sumar un valor positivo.")
    lineas = pedidos["lineas"].to_numpy(dtype=float)
    if not np.isfinite(lineas).all() or np.any(lineas < 1) or np.any(lineas != np.floor(lineas)):
        raise ValueError("Cada pedido debe tener un número entero positivo de líneas.")
    llegada = pd.to_datetime(pedidos["llegada"])
    return pedidos.assign(llegada_min=(llegada - apertura) / pd.Timedelta(minutes=1),
                          servicio_min=fijo + por_linea * lineas)


def simular_jornada(perfil: pd.Series, dotacion: int, plazo_min: float, semilla: int,
                    config: dict) -> tuple[pd.DataFrame, dict]:
    """Recibe una Serie con índice de horas locales de una fecha y tasas en pedidos/h.

    config contiene datos (horario y distribución de líneas) y servicio (minutos
    fijos y por línea). Con igual semilla, las alternativas reciben los mismos
    pedidos. El detalle incluye minutos desde la apertura y la marca local de llegada.
    """
    datos = config["datos"]
    indice = perfil.index
    if not isinstance(indice, pd.DatetimeIndex) or indice.empty or indice.tz is not None:
        raise ValueError("El perfil requiere horas locales sin zona de una misma jornada.")
    horas = datos["hora_cierre"] - datos["hora_apertura"]
    apertura = indice[0].normalize() + pd.Timedelta(hours=datos["hora_apertura"])
    if horas <= 0 or not indice.equals(pd.date_range(apertura, periods=horas, freq="h")):
        raise ValueError("Incluir en orden todas las horas de apertura, también las de tasa cero.")
    tasas = perfil.to_numpy(dtype=float)
    if not np.isfinite(tasas).all() or np.any(tasas < 0):
        raise ValueError("El pronóstico requiere tasas finitas y no negativas.")
    if not np.isfinite(plazo_min) or plazo_min <= 0:
        raise ValueError("El plazo debe ser positivo y finito.")

    fuente_llegadas, fuente_lineas = np.random.SeedSequence(semilla).spawn(2)
    rng = np.random.default_rng(fuente_llegadas)
    cantidades = rng.poisson(tasas)
    franjas = np.repeat(np.arange(horas), cantidades)
    llegada = np.sort((franjas + rng.random(len(franjas))) * 60)
    generador = datos["generador"]
    lineas = generar_lineas(np.random.default_rng(fuente_lineas), len(llegada),
                            generador["lineas_media"], generador["lineas_dispersion"])
    pedidos = pd.DataFrame({
        "pedido_id": np.arange(1, len(llegada) + 1), "lineas": lineas,
        "llegada": apertura + pd.to_timedelta(llegada, unit="min"),
    })
    cierre = horas * 60
    traza = preparar_traza(pedidos, apertura, config["servicio"])
    detalle = simular_pedidos(traza, dotacion, cierre)
    resumen = resumir_jornada(detalle, dotacion, cierre, plazo_min)
    return detalle, {"semilla": semilla, **resumen}


def resumir_jornada(detalle: pd.DataFrame, dotacion: int, cierre_min: float, plazo_min: float) -> dict:
    """Cuenta al cierre después de las finalizaciones e inicios que ocurren en ese instante."""
    preparados = int((detalle["fin_min"] <= cierre_min).sum())
    en_fila = int((detalle["inicio_min"] > cierre_min).sum())
    pendientes = len(detalle) - preparados
    return {
        "dotacion": dotacion, "plazo_min": plazo_min, "llegados": len(detalle),
        "preparados_al_cierre": preparados, "pendientes_al_cierre": pendientes,
        "en_fila_al_cierre": en_fila, "en_preparacion_al_cierre": pendientes - en_fila,
        "espera_media_min": detalle["espera_min"].mean(), "total_medio_min": detalle["total_min"].mean(),
        "proporcion_a_tiempo": (detalle["total_min"] <= plazo_min).mean(),
        **ocupacion(detalle, 0, cierre_min, dotacion),
    }
