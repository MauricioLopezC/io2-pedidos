"""Referencia estacionaria para verificar una fila común con servicio exponencial."""

from math import isfinite
from numbers import Integral


def validar_dotacion(dotacion: int) -> None:
    if isinstance(dotacion, bool) or not isinstance(dotacion, Integral) or dotacion < 1:
        raise ValueError("La dotación debe ser un entero positivo.")


def erlang_c(llegadas_h: float, servicio_h: float, dotacion: int) -> dict[str, float]:
    """Calcula Erlang C para tasas por hora; servicio_h corresponde a un preparador.

    Se evalúa la suma normalizadora por la recurrencia de Erlang B y se convierte
    a probabilidad de espera C. Esto evita factoriales para dotaciones grandes.
    Los tiempos se devuelven en minutos y las longitudes en pedidos.
    """
    validar_dotacion(dotacion)
    if not isfinite(llegadas_h) or llegadas_h < 0 or not isfinite(servicio_h) or servicio_h <= 0:
        raise ValueError("Se requiere demanda no negativa y servicio positivo, ambos finitos.")
    carga = llegadas_h / servicio_h
    rho = carga / dotacion
    if rho >= 1:
        raise ValueError("Sin régimen estacionario: la demanda alcanza o supera la capacidad.")
    bloqueo = 1.0
    for servidores in range(1, dotacion + 1):
        termino = carga * bloqueo
        bloqueo = termino / (servidores + termino)
    probabilidad = bloqueo / (1 - rho + rho * bloqueo)
    espera_h = probabilidad / (dotacion * servicio_h - llegadas_h)
    total_h = espera_h + 1 / servicio_h
    return {
        "probabilidad_espera": probabilidad,
        "utilizacion": rho,
        "espera_media_min": 60 * espera_h,
        "total_medio_min": 60 * total_h,
        "cola_media": llegadas_h * espera_h,
        "sistema_medio": llegadas_h * total_h,
    }
