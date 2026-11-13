"""Evaluación experimental de dotaciones por escenario, contraste en prueba y sensibilidad.

Conecta los perfiles horarios pronosticados (Persona A) con el simulador FIFO de
jornadas (Persona B) para responder cuántos preparadores conviene asignar en
demanda baja, media y alta, y cuán sensible es esa recomendación a errores del
pronóstico y a cambios en la duración del servicio.

Para aislar el efecto de la dotación del azar muestral, todas las dotaciones de
una misma réplica se evalúan con la misma semilla (números aleatorios comunes),
de modo que reciben exactamente los mismos pedidos e instantes de llegada.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .simulacion import preparar_traza, resumir_jornada, simular_jornada, simular_pedidos

METRICAS_RESUMEN = [
    "llegados",
    "preparados_al_cierre",
    "pendientes_al_cierre",
    "en_fila_al_cierre",
    "en_preparacion_al_cierre",
    "espera_media_min",
    "total_medio_min",
    "proporcion_a_tiempo",
    "cola_media",
    "utilizacion",
    "sistema_medio",
]


def generar_semillas(semilla_raiz: int, replicas: int) -> list[int]:
    """Deriva semillas de 64 bits reproducibles e independientes para las réplicas."""
    if replicas < 1:
        raise ValueError("Se requiere al menos una réplica.")
    secuencia = np.random.SeedSequence(int(semilla_raiz))
    return [int(fuente.generate_state(1, dtype=np.uint64)[0]) for fuente in secuencia.spawn(replicas)]


def perfil_jornada(
    pronostico_semana: pd.DataFrame,
    fecha: str | pd.Timestamp,
    columna: str = "pronostico",
) -> pd.Series:
    """Extrae el perfil horario (pedidos/h) de una fecha dentro de la semana pronosticada."""
    if columna not in pronostico_semana.columns:
        raise ValueError(f"La columna '{columna}' no existe en el pronóstico.")
    tabla = pronostico_semana.copy()
    if not isinstance(tabla.index, pd.DatetimeIndex):
        tabla.index = pd.to_datetime(tabla.index)
    dia = pd.Timestamp(fecha).normalize()
    serie = tabla.loc[tabla.index.normalize() == dia, columna].sort_index()
    if serie.empty:
        raise ValueError(f"No hay horas pronosticadas para la fecha {dia:%Y-%m-%d}.")
    serie.index.name = "hora"
    return serie.astype(float)


def perfiles_escenarios(
    pronostico_semana: pd.DataFrame,
    escenarios: dict[str, str | pd.Timestamp],
    columna: str = "pronostico",
) -> dict[str, pd.Series]:
    """Construye el diccionario {escenario: perfil_horario} para la columna indicada."""
    return {nombre: perfil_jornada(pronostico_semana, fecha, columna) for nombre, fecha in escenarios.items()}


def simular_escenario(
    perfil: pd.Series,
    dotaciones: list[int],
    plazo_min: float,
    semillas: list[int],
    config: dict,
) -> pd.DataFrame:
    """Simula todas las dotaciones sobre las mismas réplicas (números aleatorios comunes)."""
    if not dotaciones:
        raise ValueError("La lista de dotaciones no puede estar vacía.")
    if not semillas:
        raise ValueError("La lista de semillas no puede estar vacía.")
    filas = []
    for indice_replica, semilla in enumerate(semillas, start=1):
        for dotacion in dotaciones:
            _, resumen = simular_jornada(perfil, int(dotacion), plazo_min, int(semilla), config)
            filas.append({"replica": indice_replica, **resumen})
    return pd.DataFrame(filas)


def resumir_escenario(replicas: pd.DataFrame, cumplimiento_min: float) -> pd.DataFrame:
    """Agrega las réplicas por dotación con medias, desvíos e indicador de cumplimiento."""
    agrupado = replicas.groupby("dotacion", as_index=False, sort=True)
    medias = agrupado[METRICAS_RESUMEN].mean()
    desvios = agrupado[["espera_media_min", "total_medio_min", "proporcion_a_tiempo", "pendientes_al_cierre"]].std(
        ddof=0
    )
    desvios = desvios.rename(
        columns={
            "espera_media_min": "espera_std_min",
            "total_medio_min": "total_std_min",
            "proporcion_a_tiempo": "proporcion_a_tiempo_std",
            "pendientes_al_cierre": "pendientes_std",
        }
    )
    resumen = medias.merge(desvios, on="dotacion")
    resumen["cumple_objetivo"] = resumen["proporcion_a_tiempo"] >= cumplimiento_min
    return resumen


def elegir_dotacion(resumen_escenario: pd.DataFrame, cumplimiento_min: float) -> int | None:
    """Devuelve la menor dotación evaluada cuya proporción media a tiempo alcanza el umbral."""
    ordenado = resumen_escenario.sort_values("dotacion")
    cumplen = ordenado.loc[ordenado["proporcion_a_tiempo"] >= cumplimiento_min, "dotacion"]
    if cumplen.empty:
        return None
    return int(cumplen.iloc[0])


def evaluar_escenarios(
    pronostico_semana: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ejecuta las réplicas de los escenarios configurados y devuelve (replicas, resumen)."""
    cfg = config["experimentos"]
    plazo_min = float(cfg["plazo_min"])
    cumplimiento_min = float(cfg["cumplimiento_min"])
    dotaciones = [int(c) for c in cfg["dotaciones"]]
    semillas = generar_semillas(int(cfg["semilla"]), int(cfg["replicas"]))
    perfiles = perfiles_escenarios(pronostico_semana, cfg["escenarios"])

    bloques_replicas = []
    bloques_resumen = []
    for escenario, perfil in perfiles.items():
        rep = simular_escenario(perfil, dotaciones, plazo_min, semillas, config)
        rep.insert(0, "escenario", escenario)
        res = resumir_escenario(rep, cumplimiento_min)
        res.insert(0, "escenario", escenario)
        res.insert(1, "fecha", str(cfg["escenarios"][escenario]))
        res.insert(2, "demanda_pronosticada", float(perfil.sum()))
        res.insert(3, "pico_horario", float(perfil.max()))
        bloques_replicas.append(rep)
        bloques_resumen.append(res)

    return pd.concat(bloques_replicas, ignore_index=True), pd.concat(bloques_resumen, ignore_index=True)


def tabla_recomendaciones(resumen_escenarios: pd.DataFrame, cumplimiento_min: float) -> pd.DataFrame:
    """Construye la tabla de dotación recomendada por escenario a partir del resumen simulado."""
    filas = []
    for escenario, grupo in resumen_escenarios.groupby("escenario", sort=False):
        recomendada = elegir_dotacion(grupo, cumplimiento_min)
        if recomendada is not None:
            elegida = grupo.loc[grupo["dotacion"] == recomendada].iloc[0]
            cumple = True
        else:
            elegida = grupo.sort_values("dotacion").iloc[-1]
            cumple = False
        filas.append(
            {
                "escenario": escenario,
                "fecha": elegida["fecha"],
                "demanda_pronosticada": elegida["demanda_pronosticada"],
                "pico_horario": elegida["pico_horario"],
                "dotacion_recomendada": recomendada if recomendada is not None else pd.NA,
                "dotacion_evaluada": int(elegida["dotacion"]),
                "cumple_objetivo": cumple,
                "espera_media_min": elegida["espera_media_min"],
                "total_medio_min": elegida["total_medio_min"],
                "proporcion_a_tiempo": elegida["proporcion_a_tiempo"],
                "cola_media": elegida["cola_media"],
                "utilizacion": elegida["utilizacion"],
                "pendientes_al_cierre": elegida["pendientes_al_cierre"],
            }
        )
    return pd.DataFrame(filas)


def contrastar_en_prueba(
    pedidos: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    """Evalúa las dotaciones sobre las jornadas del período de prueba reservado.

    Para cada escenario (baja, media, alta) identifica el día de la semana de su
    fecha representativa y simula los días equivalentes de las últimas semanas de
    prueba con los pedidos observados en `pedidos.csv`.
    """
    datos_cfg = config["datos"]
    apertura_h = int(datos_cfg["hora_apertura"])
    cierre_h = int(datos_cfg["hora_cierre"])
    cierre_min = float((cierre_h - apertura_h) * 60)
    semanas_prueba = int(config["pronostico"]["semanas_prueba"])

    exp_cfg = config["experimentos"]
    plazo_min = float(exp_cfg["plazo_min"])
    cumplimiento_min = float(exp_cfg["cumplimiento_min"])
    dotaciones = [int(c) for c in exp_cfg["dotaciones"]]

    df = pedidos.copy()
    df["llegada"] = pd.to_datetime(df["llegada"])
    ultimo_dia = df["llegada"].max().normalize()
    inicio_prueba = ultimo_dia + pd.Timedelta(days=1) - pd.Timedelta(weeks=semanas_prueba)
    en_prueba = df.loc[df["llegada"] >= inicio_prueba].copy()
    en_prueba["fecha"] = en_prueba["llegada"].dt.normalize()

    filas = []
    for escenario, fecha_ref in exp_cfg["escenarios"].items():
        dia_semana = pd.Timestamp(fecha_ref).isoweekday()
        dias_escenario = sorted(
            f for f in en_prueba["fecha"].unique() if pd.Timestamp(f).isoweekday() == dia_semana
        )
        for fecha_dia in dias_escenario:
            pedidos_dia = en_prueba.loc[en_prueba["fecha"] == fecha_dia, ["pedido_id", "llegada", "lineas"]]
            apertura = pd.Timestamp(fecha_dia) + pd.Timedelta(hours=apertura_h)
            traza = preparar_traza(pedidos_dia, apertura, config["servicio"])
            for dotacion in dotaciones:
                detalle = simular_pedidos(traza, dotacion, cierre_min)
                resumen = resumir_jornada(detalle, dotacion, cierre_min, plazo_min)
                filas.append(
                    {
                        "escenario": escenario,
                        "fecha_prueba": f"{pd.Timestamp(fecha_dia):%Y-%m-%d}",
                        **resumen,
                    }
                )

    por_dia = pd.DataFrame(filas)
    resumen_prueba = (
        por_dia.groupby(["escenario", "dotacion"], as_index=False, sort=False)[METRICAS_RESUMEN].mean()
    )
    resumen_prueba["cumple_objetivo"] = resumen_prueba["proporcion_a_tiempo"] >= cumplimiento_min
    return resumen_prueba


def analizar_sensibilidad_demanda(
    pronostico_semana: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evalúa cómo cambian el desempeño y la dotación recomendada ante variaciones de demanda.

    Incluye tanto las bandas del intervalo empírico del pronóstico (inferior,
    pronostico, superior) como factores multiplicativos sobre el pronóstico base.
    """
    exp_cfg = config["experimentos"]
    sens_cfg = config["sensibilidad"]
    plazo_min = float(exp_cfg["plazo_min"])
    cumplimiento_min = float(exp_cfg["cumplimiento_min"])
    dotaciones = [int(c) for c in exp_cfg["dotaciones"]]
    semillas = generar_semillas(int(exp_cfg["semilla"]), int(exp_cfg["replicas"]))
    escenarios = exp_cfg["escenarios"]

    variantes: list[tuple[str, str, dict[str, pd.Series]]] = []
    for curva in sens_cfg["curvas_pronostico"]:
        variantes.append(("intervalo_empirico", str(curva), perfiles_escenarios(pronostico_semana, escenarios, curva)))
    perfiles_base = perfiles_escenarios(pronostico_semana, escenarios, "pronostico")
    for factor in sens_cfg["factores_demanda"]:
        f = float(factor)
        etiqueta = f"{f:.2f}x"
        variantes.append(
            ("factor_demanda", etiqueta, {esc: perf * f for esc, perf in perfiles_base.items()})
        )

    bloques = []
    recomendaciones = []
    for tipo, variante, perfiles in variantes:
        for escenario, perfil in perfiles.items():
            rep = simular_escenario(perfil, dotaciones, plazo_min, semillas, config)
            res = resumir_escenario(rep, cumplimiento_min)
            res.insert(0, "tipo", tipo)
            res.insert(1, "variante", variante)
            res.insert(2, "escenario", escenario)
            res.insert(3, "demanda_diaria", float(perfil.sum()))
            res.insert(4, "pico_horario", float(perfil.max()))
            bloques.append(res)

            rec = elegir_dotacion(res, cumplimiento_min)
            elegida = (
                res.loc[res["dotacion"] == rec].iloc[0]
                if rec is not None
                else res.sort_values("dotacion").iloc[-1]
            )
            recomendaciones.append(
                {
                    "tipo": tipo,
                    "variante": variante,
                    "escenario": escenario,
                    "demanda_diaria": float(perfil.sum()),
                    "pico_horario": float(perfil.max()),
                    "dotacion_recomendada": rec if rec is not None else pd.NA,
                    "dotacion_evaluada": int(elegida["dotacion"]),
                    "cumple_objetivo": rec is not None,
                    "espera_media_min": float(elegida["espera_media_min"]),
                    "total_medio_min": float(elegida["total_medio_min"]),
                    "proporcion_a_tiempo": float(elegida["proporcion_a_tiempo"]),
                    "utilizacion": float(elegida["utilizacion"]),
                    "pendientes_al_cierre": float(elegida["pendientes_al_cierre"]),
                }
            )

    return pd.concat(bloques, ignore_index=True), pd.DataFrame(recomendaciones)


def analizar_sensibilidad_servicio(
    pronostico_semana: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evalúa la sensibilidad frente a cambios en los tiempos de preparación (b y m).

    Al usar las mismas semillas del experimento base, los instantes de llegada y
    las líneas de cada pedido se mantienen idénticos al variar el servicio.
    """
    exp_cfg = config["experimentos"]
    sens_cfg = config["sensibilidad"]
    plazo_min = float(exp_cfg["plazo_min"])
    cumplimiento_min = float(exp_cfg["cumplimiento_min"])
    dotaciones = [int(c) for c in exp_cfg["dotaciones"]]
    semillas = generar_semillas(int(exp_cfg["semilla"]), int(exp_cfg["replicas"]))
    perfiles = perfiles_escenarios(pronostico_semana, exp_cfg["escenarios"], "pronostico")

    fijo_base = float(config["servicio"]["minutos_fijos"])
    linea_base = float(config["servicio"]["minutos_por_linea"])
    lineas_media = float(config["datos"]["generador"]["lineas_media"])

    bloques = []
    recomendaciones = []
    for factor in sens_cfg["factores_servicio"]:
        f = float(factor)
        fijo = fijo_base * f
        por_linea = linea_base * f
        servicio_medio = fijo + por_linea * lineas_media
        cfg_var = {**config, "servicio": {"minutos_fijos": fijo, "minutos_por_linea": por_linea}}
        etiqueta = f"{f:.2f}x"

        for escenario, perfil in perfiles.items():
            rep = simular_escenario(perfil, dotaciones, plazo_min, semillas, cfg_var)
            res = resumir_escenario(rep, cumplimiento_min)
            res.insert(0, "factor_servicio", f)
            res.insert(1, "variante", etiqueta)
            res.insert(2, "minutos_fijos", fijo)
            res.insert(3, "minutos_por_linea", por_linea)
            res.insert(4, "servicio_medio_min", servicio_medio)
            res.insert(5, "escenario", escenario)
            bloques.append(res)

            rec = elegir_dotacion(res, cumplimiento_min)
            elegida = (
                res.loc[res["dotacion"] == rec].iloc[0]
                if rec is not None
                else res.sort_values("dotacion").iloc[-1]
            )
            recomendaciones.append(
                {
                    "factor_servicio": f,
                    "variante": etiqueta,
                    "minutos_fijos": fijo,
                    "minutos_por_linea": por_linea,
                    "servicio_medio_min": servicio_medio,
                    "escenario": escenario,
                    "dotacion_recomendada": rec if rec is not None else pd.NA,
                    "dotacion_evaluada": int(elegida["dotacion"]),
                    "cumple_objetivo": rec is not None,
                    "espera_media_min": float(elegida["espera_media_min"]),
                    "total_medio_min": float(elegida["total_medio_min"]),
                    "proporcion_a_tiempo": float(elegida["proporcion_a_tiempo"]),
                    "utilizacion": float(elegida["utilizacion"]),
                    "pendientes_al_cierre": float(elegida["pendientes_al_cierre"]),
                }
            )

    return pd.concat(bloques, ignore_index=True), pd.DataFrame(recomendaciones)
