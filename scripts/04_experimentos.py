"""Paso 4: evalúa las dotaciones por escenario de demanda y contrasta con el período de prueba.

Simula las jornadas de demanda baja, media y alta pronosticadas para la semana
siguiente con números aleatorios comunes entre dotaciones, identifica la menor
dotación que cumple el objetivo operativo y contrasta esa recomendación sobre
los pedidos registrados en el histórico sintético durante las cuatro semanas
reservadas de prueba.

Salidas:
- resultados/experimentos_replicas.csv: indicadores por réplica, escenario y dotación.
- resultados/experimentos_escenarios.csv: medias y desvíos por escenario y dotación.
- resultados/experimentos_recomendacion.csv: dotación recomendada por escenario y su
  contraste en las semanas de prueba.
- resultados/experimentos_prueba.csv: desempeño de todas las dotaciones en los días
  equivalentes del período de prueba.
- resultados/experimentos_resumen.csv: cifras clave que cita el informe.
- informe/tablas/experimentos_escenarios.tex y informe/tablas/experimentos_recomendacion.tex.
- informe/figuras/experimentos_desempeno.pdf.

Uso: python scripts/04_experimentos.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from pedidos import experimentos as exp  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "datos" / "procesados"
RESULTADOS = RAIZ / "resultados"
TABLAS = RAIZ / "informe" / "tablas"
FIGURAS = RAIZ / "informe" / "figuras"

NOMBRES_ESCENARIO = {
    "baja": "Baja (domingo)",
    "media": "Media (jueves)",
    "alta": "Alta (sábado)",
}

COLORES_ESCENARIO = {
    "baja": "#2b5c8f",
    "media": "#00798c",
    "alta": "#d1495b",
}


def fmt(valor: float, decimales: int = 1) -> str:
    return f"{valor:.{decimales}f}".replace(".", ",")


def tabla_escenarios_latex(resumen: pd.DataFrame, recomendaciones: pd.DataFrame) -> str:
    rec_map = recomendaciones.set_index("escenario")["dotacion_recomendada"].to_dict()
    filas = [
        "% Generado por scripts/04_experimentos.py; no editar a mano.",
        r"{\small",
        r"\begin{tabular}{llrrrrrr}",
        r"\toprule",
        r"Escenario & $c$ & $W_q$ (min) & $W$ (min) & $L_q$ & $\rho$ (\%) & Pend. & A tiempo (\%) \\",
        r"\midrule",
    ]
    escenarios = list(resumen["escenario"].unique())
    for idx_esc, escenario in enumerate(escenarios):
        grupo = resumen.loc[resumen["escenario"] == escenario].sort_values("dotacion")
        c_rec = rec_map.get(escenario)
        for idx_fila, (_, fila) in enumerate(grupo.iterrows()):
            c = int(fila["dotacion"])
            etiqueta_esc = NOMBRES_ESCENARIO.get(escenario, escenario) if idx_fila == 0 else ""
            marca = r"$\mathbf{" + str(c) + r"^*}$" if pd.notna(c_rec) and c == int(c_rec) else str(c)
            filas.append(
                f"{etiqueta_esc} & {marca} & {fmt(fila['espera_media_min'], 2)} & "
                f"{fmt(fila['total_medio_min'], 2)} & {fmt(fila['cola_media'], 2)} & "
                f"{fmt(100 * fila['utilizacion'], 1)} & {fmt(fila['pendientes_al_cierre'], 1)} & "
                f"{fmt(100 * fila['proporcion_a_tiempo'], 1)} \\\\"
            )
        if idx_esc < len(escenarios) - 1:
            filas.append(r"\midrule")
    filas.extend([r"\bottomrule", r"\end{tabular}}", ""])
    return "\n".join(filas)


def tabla_recomendacion_latex(comparacion: pd.DataFrame) -> str:
    filas = [
        "% Generado por scripts/04_experimentos.py; no editar a mano.",
        r"{\small\setlength{\tabcolsep}{4.5pt}",
        r"\begin{tabular}{lrrrrrrr}",
        r"\toprule",
        r" & & & & \multicolumn{2}{c}{Simulación} & \multicolumn{2}{c}{Prueba reservada} \\",
        r"\cmidrule(lr){5-6} \cmidrule(lr){7-8}",
        r"Escenario & Ped./día & Pico/h & $c^*$ & A tiempo (\%) & $W$ (min) & A tiempo (\%) & $W$ (min) \\",
        r"\midrule",
    ]
    for _, fila in comparacion.iterrows():
        esc = NOMBRES_ESCENARIO.get(fila["escenario"], fila["escenario"])
        c_str = str(int(fila["dotacion_recomendada"])) if pd.notna(fila["dotacion_recomendada"]) else "Ninguna"
        filas.append(
            f"{esc} & {fmt(fila['demanda_pronosticada'], 1)} & {fmt(fila['pico_horario'], 1)} & "
            f"{c_str} & {fmt(100 * fila['proporcion_a_tiempo'], 1)} & {fmt(fila['total_medio_min'], 1)} & "
            f"{fmt(100 * fila['proporcion_a_tiempo_prueba'], 1)} & {fmt(fila['total_medio_min_prueba'], 1)} \\\\"
        )
    filas.extend([r"\bottomrule", r"\end{tabular}}", ""])
    return "\n".join(filas)


def figura_desempeno(resumen: pd.DataFrame, cumplimiento_min: float, ruta: Path) -> None:
    fig, ejes = plt.subplots(1, 3, figsize=(6.3, 2.55))
    marcadores = {"baja": "o", "media": "s", "alta": "^"}

    for escenario, grupo in resumen.groupby("escenario", sort=False):
        grupo = grupo.sort_values("dotacion")
        c = grupo["dotacion"]
        color = COLORES_ESCENARIO.get(escenario, "black")
        marca = marcadores.get(escenario, "o")
        etiqueta = NOMBRES_ESCENARIO.get(escenario, escenario)

        ejes[0].plot(
            c,
            100 * grupo["proporcion_a_tiempo"],
            marker=marca,
            markersize=4,
            linewidth=1.4,
            color=color,
            label=etiqueta,
        )
        ejes[1].plot(
            c,
            grupo["espera_media_min"],
            marker=marca,
            markersize=4,
            linewidth=1.4,
            color=color,
            label=etiqueta,
        )
        ejes[2].plot(
            c,
            100 * grupo["utilizacion"],
            marker=marca,
            markersize=4,
            linewidth=1.4,
            color=color,
            label=etiqueta,
        )

    ejes[0].axhline(
        100 * cumplimiento_min,
        color="0.4",
        linestyle="--",
        linewidth=0.9,
        label=f"Umbral {100 * cumplimiento_min:g} %",
    )
    ejes[0].set_ylabel("Pedidos a tiempo (%)")
    ejes[0].set_ylim(-2, 104)

    ejes[1].set_ylabel("Espera media $W_q$ (min)")
    ejes[2].set_ylabel("Utilización $\\rho$ (%)")
    ejes[2].set_ylim(0, 105)

    dotaciones = sorted(resumen["dotacion"].unique())
    for ax in ejes:
        ax.set_xlabel("Preparadores ($c$)")
        ax.set_xticks(dotaciones)
        ax.tick_params(labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="0.9", linewidth=0.5)

    handles, labels = ejes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.98),
        fontsize=7.5,
        ncol=4,
        frameon=False,
    )
    fig.tight_layout()
    fig.savefig(ruta, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(fig)


def construir_resumen_indicadores(
    config: dict,
    resumen: pd.DataFrame,
    comparacion: pd.DataFrame,
    prueba: pd.DataFrame,
) -> pd.Series:
    """Extrae las cifras clave de los experimentos para citarlas en el informe."""
    cfg = config["experimentos"]
    valores: dict[str, object] = {
        "plazo_min": cfg["plazo_min"],
        "cumplimiento_min": cfg["cumplimiento_min"],
        "replicas": cfg["replicas"],
        "semilla": cfg["semilla"],
        "dotacion_min_evaluada": min(cfg["dotaciones"]),
        "dotacion_max_evaluada": max(cfg["dotaciones"]),
    }
    idx_res = resumen.set_index(["escenario", "dotacion"])
    idx_pru = prueba.set_index(["escenario", "dotacion"])

    for _, fila in comparacion.iterrows():
        esc = str(fila["escenario"])
        cumple = pd.notna(fila["dotacion_recomendada"])
        c_eval = int(fila["dotacion_evaluada"])
        valores[f"{esc}_fecha"] = fila["fecha"]
        valores[f"{esc}_demanda_pronosticada"] = round(float(fila["demanda_pronosticada"]), 2)
        valores[f"{esc}_pico_horario"] = round(float(fila["pico_horario"]), 2)
        valores[f"{esc}_dotacion_recomendada"] = int(fila["dotacion_recomendada"]) if cumple else "ninguna"
        valores[f"{esc}_a_tiempo_recomendada"] = round(float(fila["proporcion_a_tiempo"]), 4)
        valores[f"{esc}_espera_min_recomendada"] = round(float(fila["espera_media_min"]), 2)
        valores[f"{esc}_total_min_recomendada"] = round(float(fila["total_medio_min"]), 2)
        valores[f"{esc}_cola_recomendada"] = round(float(fila["cola_media"]), 2)
        valores[f"{esc}_utilizacion_recomendada"] = round(float(fila["utilizacion"]), 4)
        valores[f"{esc}_pendientes_recomendada"] = round(float(fila["pendientes_al_cierre"]), 2)
        valores[f"{esc}_a_tiempo_prueba_recomendada"] = round(float(fila["proporcion_a_tiempo_prueba"]), 4)
        valores[f"{esc}_espera_min_prueba_recomendada"] = round(float(fila["espera_media_min_prueba"]), 2)
        valores[f"{esc}_total_min_prueba_recomendada"] = round(float(fila["total_medio_min_prueba"]), 2)
        valores[f"{esc}_llegados_prueba_media"] = round(float(idx_pru.loc[(esc, c_eval), "llegados"]), 2)

        if cumple and (esc, c_eval - 1) in idx_res.index:
            prev = idx_res.loc[(esc, c_eval - 1)]
            valores[f"{esc}_a_tiempo_anterior"] = round(float(prev["proporcion_a_tiempo"]), 4)
            valores[f"{esc}_espera_min_anterior"] = round(float(prev["espera_media_min"]), 2)
            valores[f"{esc}_total_min_anterior"] = round(float(prev["total_medio_min"]), 2)
            valores[f"{esc}_pendientes_anterior"] = round(float(prev["pendientes_al_cierre"]), 2)
        if cumple and (esc, c_eval - 1) in idx_pru.index:
            prev_p = idx_pru.loc[(esc, c_eval - 1)]
            valores[f"{esc}_a_tiempo_prueba_anterior"] = round(float(prev_p["proporcion_a_tiempo"]), 4)

    return pd.Series(valores, name="valor")


def main() -> int:
    config = yaml.safe_load((RAIZ / "config" / "experimento.yaml").read_text(encoding="utf-8"))
    ruta_pronostico = RESULTADOS / "pronostico_semana_siguiente.csv"
    ruta_pedidos = PROCESADOS / "pedidos.csv"
    if not ruta_pronostico.exists():
        sys.exit(f"falta {ruta_pronostico.relative_to(RAIZ)}; generalo antes con `make pronostico`")
    if not ruta_pedidos.exists():
        sys.exit(f"falta {ruta_pedidos.relative_to(RAIZ)}; generalo antes con `make datos`")

    pronostico_semana = pd.read_csv(ruta_pronostico, index_col="hora", parse_dates=["hora"])
    pedidos = pd.read_csv(ruta_pedidos, parse_dates=["llegada"])

    replicas, resumen = exp.evaluar_escenarios(pronostico_semana, config)
    cumplimiento_min = float(config["experimentos"]["cumplimiento_min"])
    recomendaciones = exp.tabla_recomendaciones(resumen, cumplimiento_min)
    prueba = exp.contrastar_en_prueba(pedidos, config)

    comparacion = recomendaciones.merge(
        prueba[
            [
                "escenario",
                "dotacion",
                "llegados",
                "espera_media_min",
                "total_medio_min",
                "proporcion_a_tiempo",
                "utilizacion",
                "pendientes_al_cierre",
            ]
        ],
        left_on=["escenario", "dotacion_evaluada"],
        right_on=["escenario", "dotacion"],
        suffixes=("", "_prueba"),
    ).drop(columns=["dotacion"])

    RESULTADOS.mkdir(parents=True, exist_ok=True)
    TABLAS.mkdir(parents=True, exist_ok=True)
    FIGURAS.mkdir(parents=True, exist_ok=True)

    replicas.to_csv(RESULTADOS / "experimentos_replicas.csv", index=False)
    resumen.to_csv(RESULTADOS / "experimentos_escenarios.csv", index=False)
    comparacion.to_csv(RESULTADOS / "experimentos_recomendacion.csv", index=False)
    prueba.to_csv(RESULTADOS / "experimentos_prueba.csv", index=False)

    indicadores = construir_resumen_indicadores(config, resumen, comparacion, prueba)
    indicadores.rename_axis("indicador").to_csv(RESULTADOS / "experimentos_resumen.csv")

    (TABLAS / "experimentos_escenarios.tex").write_text(
        tabla_escenarios_latex(resumen, recomendaciones), encoding="utf-8"
    )
    (TABLAS / "experimentos_recomendacion.tex").write_text(
        tabla_recomendacion_latex(comparacion), encoding="utf-8"
    )
    figura_desempeno(resumen, cumplimiento_min, FIGURAS / "experimentos_desempeno.pdf")

    print(comparacion.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
