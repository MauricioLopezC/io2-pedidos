"""Contraste estacionario por réplicas independientes para aislar errores del motor FIFO."""

from statistics import NormalDist

import numpy as np
import pandas as pd

from .colas import erlang_c
from .simulacion import ocupacion, simular_pedidos


def verificar_mmc(parametros: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve estimaciones por semilla e intervalos normales aproximados entre réplicas.

    Condicionando al número Poisson de llegadas, los instantes son uniformes.
    Las áreas se recortan a la ventana y las medias por pedido siguen hasta el
    fin a todos los llegados en ella. Little se contrasta por diferencia pareada.
    """
    tasa = parametros["llegadas_h"]
    servicio = parametros["servicio_h"]
    dotacion = parametros["dotacion"]
    teoria = erlang_c(tasa, servicio, dotacion)
    desde = 60 * parametros["calentamiento_h"]
    duracion = 60 * parametros["observacion_h"]
    cierre = desde + duracion
    confianza = parametros["confianza"]
    replicas = parametros["replicas"]
    if tasa <= 0 or desde < 0 or duracion <= 0 or replicas < 2 or not 0 < confianza < 1:
        raise ValueError("Revisar tasa positiva, ventana, réplicas y confianza de la verificación.")
    filas = []
    for fuente in np.random.SeedSequence(parametros["semilla"]).spawn(replicas):
        semilla = int(fuente.generate_state(1, dtype=np.uint64)[0])
        rng = np.random.default_rng(semilla)
        cantidad = rng.poisson(tasa * cierre / 60)
        pedidos = pd.DataFrame({
            "pedido_id": np.arange(cantidad),
            "llegada_min": rng.uniform(0, cierre, cantidad),
            "servicio_min": rng.exponential(60 / servicio, cantidad),
        })
        detalle = simular_pedidos(pedidos, dotacion, cierre)
        cohorte = detalle.loc[detalle["llegada_min"] >= desde]
        if cohorte.empty:
            raise ValueError("Réplica sin llegadas observadas; ampliar el horizonte de verificación.")
        medidas = ocupacion(detalle, desde, cierre, dotacion)
        total = cohorte["total_min"].mean()
        filas.append({
            "semilla": semilla, "espera_media_min": cohorte["espera_min"].mean(),
            "total_medio_min": total, **medidas,
            "diferencia_little": medidas["sistema_medio"] - len(cohorte) / duracion * total,
        })
    muestras = pd.DataFrame(filas)
    valores = muestras.drop(columns="semilla")
    media = valores.mean()
    margen = NormalDist().inv_cdf((1 + confianza) / 2) * valores.std(ddof=1) / np.sqrt(replicas)
    referencia = pd.Series({**teoria, "diferencia_little": 0.0}).reindex(media.index)
    tabla = pd.DataFrame({"teoria": referencia, "simulacion": media,
                          "inferior": media - margen, "superior": media + margen})
    tabla["contiene_teoria"] = referencia.between(tabla["inferior"], tabla["superior"])
    return muestras, tabla.rename_axis("indicador")
