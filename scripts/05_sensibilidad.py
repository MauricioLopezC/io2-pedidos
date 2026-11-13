"""Paso 5: analiza la sensibilidad de la dotación frente a errores de pronóstico y tiempos de servicio.

Evalúa cómo cambian el cumplimiento del plazo objetivo y la menor dotación
requerida cuando la demanda se desvía del pronóstico (bandas del intervalo
empírico del 80 % y factores multiplicativos) y cuando varía la duración media
de preparación (factores sobre los minutos fijos y por línea).

Salidas:
- resultados/sensibilidad_demanda.csv: indicadores por variante de demanda, escenario y dotación.
- resultados/sensibilidad_servicio.csv: indicadores por factor de servicio, escenario y dotación.
- resultados/sensibilidad_recomendacion.csv: dotación recomendada y cumplimiento de la dotación
  base bajo cada perturbación de demanda y de servicio.
- resultados/sensibilidad_resumen.csv: cifras clave que cita el informe.
- informe/tablas/sensibilidad_recomendacion.tex.
- informe/figuras/sensibilidad_cumplimiento.pdf.

Uso: python scripts/05_sensibilidad.py
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
RESULTADOS = RAIZ / "resultados"
TABLAS = RAIZ / "informe" / "tablas"
FIGURAS = RAIZ / "informe" / "figuras"

def etiqueta_demanda(variante: str) -> str:
    especiales = {
        "inferior": "Banda inferior (P10)",
        "pronostico": "Pronóstico base",
        "superior": "Banda superior (P90)",
    }
    if variante in especiales:
        return especiales[variante]
    factor = float(variante.rstrip("x"))
    delta_pct = round(100 * (factor - 1.0))
    if delta_pct == 0:
        return "Demanda base ($1{,}00\\times$)"
    signo = "+" if delta_pct > 0 else "-"
    return f"Demanda ${signo}{abs(delta_pct)}$~\\%"


def etiqueta_servicio(variante: str, srv_rec: pd.DataFrame) -> str:
    fila = srv_rec.loc[srv_rec["variante"] == variante].iloc[0]
    factor = float(fila["factor_servicio"])
    media_min = fmt(float(fila["servicio_medio_min"]), 0)
    delta_pct = round(100 * (factor - 1.0))
    if delta_pct == 0:
        return f"Servicio base ({media_min} min)"
    signo = "+" if delta_pct > 0 else "-"
    return f"Servicio ${signo}{abs(delta_pct)}$~\\% ({media_min} min)"


def fmt(valor: float, decimales: int = 1) -> str:
    return f"{valor:.{decimales}f}".replace(".", ",")


def fmt_dotacion(valor: object, max_dotacion: int) -> str:
    if pd.isna(valor):
        return rf"$>{max_dotacion}$"
    return str(int(valor))


def armar_tabla_consolidada(
    dem_detalle: pd.DataFrame,
    dem_rec: pd.DataFrame,
    srv_detalle: pd.DataFrame,
    srv_rec: pd.DataFrame,
    dotacion_base: dict[str, int],
) -> pd.DataFrame:
    """Combina por perturbación la dotación recomendada y el cumplimiento con la dotación base."""
    filas = []

    # 1. Sensibilidad a la demanda (evitando duplicar 1.00x con pronóstico base en la tabla resumen).
    variantes_dem = [
        ("intervalo_empirico", "inferior"),
        ("intervalo_empirico", "pronostico"),
        ("intervalo_empirico", "superior"),
        ("factor_demanda", "0.90x"),
        ("factor_demanda", "1.10x"),
        ("factor_demanda", "1.20x"),
    ]
    idx_dem_det = dem_detalle.set_index(["tipo", "variante", "escenario", "dotacion"])
    idx_dem_rec = dem_rec.set_index(["tipo", "variante", "escenario"])

    for tipo, var in variantes_dem:
        if (tipo, var, "baja") not in idx_dem_rec.index:
            continue
        fila_out: dict[str, object] = {"eje": "demanda", "tipo": tipo, "variante": var}
        for esc in ["baja", "media", "alta"]:
            r = idx_dem_rec.loc[(tipo, var, esc)]
            c_base = dotacion_base[esc]
            det_base = idx_dem_det.loc[(tipo, var, esc, c_base)]
            fila_out[f"c_rec_{esc}"] = r["dotacion_recomendada"]
            fila_out[f"cumple_{esc}"] = bool(r["cumple_objetivo"])
            fila_out[f"a_tiempo_c_rec_{esc}"] = float(r["proporcion_a_tiempo"])
            fila_out[f"a_tiempo_c_base_{esc}"] = float(det_base["proporcion_a_tiempo"])
            fila_out[f"espera_c_base_{esc}"] = float(det_base["espera_media_min"])
        filas.append(fila_out)

    # 2. Sensibilidad al tiempo de servicio.
    idx_srv_det = srv_detalle.set_index(["variante", "escenario", "dotacion"])
    idx_srv_rec = srv_rec.set_index(["variante", "escenario"])
    for var in srv_rec["variante"].unique():
        fila_out = {"eje": "servicio", "tipo": "factor_servicio", "variante": str(var)}
        for esc in ["baja", "media", "alta"]:
            r = idx_srv_rec.loc[(var, esc)]
            c_base = dotacion_base[esc]
            det_base = idx_srv_det.loc[(var, esc, c_base)]
            fila_out[f"c_rec_{esc}"] = r["dotacion_recomendada"]
            fila_out[f"cumple_{esc}"] = bool(r["cumple_objetivo"])
            fila_out[f"a_tiempo_c_rec_{esc}"] = float(r["proporcion_a_tiempo"])
            fila_out[f"a_tiempo_c_base_{esc}"] = float(det_base["proporcion_a_tiempo"])
            fila_out[f"espera_c_base_{esc}"] = float(det_base["espera_media_min"])
        filas.append(fila_out)

    return pd.DataFrame(filas)


def tabla_sensibilidad_latex(
    consolidada: pd.DataFrame,
    srv_rec: pd.DataFrame,
    dotacion_base: dict[str, int],
    max_dotacion: int,
) -> str:
    cb_baja = dotacion_base["baja"]
    cb_media = dotacion_base["media"]
    cb_alta = dotacion_base["alta"]
    filas = [
        "% Generado por scripts/05_sensibilidad.py; no editar a mano.",
        r"{\small\setlength{\tabcolsep}{4.5pt}",
        r"\begin{tabular}{llrrrrrr}",
        r"\toprule",
        r" & & \multicolumn{3}{c}{Dotación requerida $c^*$} & \multicolumn{3}{c}{A tiempo con $c^*_{\mathrm{base}}$ (\%)} \\",
        r"\cmidrule(lr){3-5} \cmidrule(lr){6-8}",
        rf"Eje & Perturbación & Baja & Media & Alta & Baja ({cb_baja}) & Media ({cb_media}) & Alta ({cb_alta}) \\",
        r"\midrule",
    ]

    dem = consolidada.loc[consolidada["eje"] == "demanda"].reset_index(drop=True)
    for i, (_, f) in enumerate(dem.iterrows()):
        eje_txt = "Demanda" if i == 0 else ""
        etiqueta = etiqueta_demanda(str(f["variante"]))
        filas.append(
            f"{eje_txt} & {etiqueta} & {fmt_dotacion(f['c_rec_baja'], max_dotacion)} & "
            f"{fmt_dotacion(f['c_rec_media'], max_dotacion)} & {fmt_dotacion(f['c_rec_alta'], max_dotacion)} & "
            f"{fmt(100 * float(f['a_tiempo_c_base_baja']), 1)} & "
            f"{fmt(100 * float(f['a_tiempo_c_base_media']), 1)} & "
            f"{fmt(100 * float(f['a_tiempo_c_base_alta']), 1)} \\\\"
        )

    filas.append(r"\midrule")
    srv = consolidada.loc[consolidada["eje"] == "servicio"].reset_index(drop=True)
    for i, (_, f) in enumerate(srv.iterrows()):
        eje_txt = "Servicio" if i == 0 else ""
        etiqueta = etiqueta_servicio(str(f["variante"]), srv_rec)
        filas.append(
            f"{eje_txt} & {etiqueta} & {fmt_dotacion(f['c_rec_baja'], max_dotacion)} & "
            f"{fmt_dotacion(f['c_rec_media'], max_dotacion)} & {fmt_dotacion(f['c_rec_alta'], max_dotacion)} & "
            f"{fmt(100 * float(f['a_tiempo_c_base_baja']), 1)} & "
            f"{fmt(100 * float(f['a_tiempo_c_base_media']), 1)} & "
            f"{fmt(100 * float(f['a_tiempo_c_base_alta']), 1)} \\\\"
        )

    filas.extend([r"\bottomrule", r"\end{tabular}}", ""])
    return "\n".join(filas)


def figura_sensibilidad(
    dem_detalle: pd.DataFrame,
    srv_detalle: pd.DataFrame,
    dotacion_base: dict[str, int],
    cumplimiento_min: float,
    ruta: Path,
) -> None:
    fig, ejes = plt.subplots(1, 2, figsize=(6.3, 2.65))

    # Panel izquierdo: efecto del intervalo empírico en escenarios medio y alto.
    sub_dem = dem_detalle.loc[dem_detalle["tipo"] == "intervalo_empirico"]
    estilos_curva = {
        "inferior": ("--", "0.55", "P10"),
        "pronostico": ("-", "#00798c", "Base"),
        "superior": ("-.", "#d1495b", "P90"),
    }
    for curva, (ls, col, nom_curva) in estilos_curva.items():
        g_alta = sub_dem.loc[(sub_dem["variante"] == curva) & (sub_dem["escenario"] == "alta")].sort_values(
            "dotacion"
        )
        ejes[0].plot(
            g_alta["dotacion"],
            100 * g_alta["proporcion_a_tiempo"],
            linestyle=ls,
            marker="^",
            markersize=4,
            linewidth=1.4,
            color=col,
            label=f"Alta ({nom_curva})",
        )
    g_media_sup = sub_dem.loc[
        (sub_dem["variante"] == "superior") & (sub_dem["escenario"] == "media")
    ].sort_values("dotacion")
    ejes[0].plot(
        g_media_sup["dotacion"],
        100 * g_media_sup["proporcion_a_tiempo"],
        linestyle=":",
        marker="s",
        markersize=4,
        linewidth=1.3,
        color="#2b5c8f",
        label="Media (P90)",
    )
    ejes[0].axhline(100 * cumplimiento_min, color="0.4", linestyle="--", linewidth=0.8)
    ejes[0].set_xlabel("Preparadores ($c$)")
    ejes[0].set_ylabel("Pedidos a tiempo (%)")
    ejes[0].set_title("a) Sensibilidad a la demanda (intervalo 80 %)", fontsize=8.5)
    ejes[0].set_xticks(sorted(dem_detalle["dotacion"].unique()))
    ejes[0].set_ylim(-2, 104)
    ejes[0].legend(fontsize=7, frameon=False, loc="lower right")

    # Panel derecho: efecto del tiempo medio de servicio manteniendo la dotación recomendada base.
    colores_esc = {"baja": "#2b5c8f", "media": "#00798c", "alta": "#d1495b"}
    marcadores_esc = {"baja": "o", "media": "s", "alta": "^"}
    nombres_esc = {
        "baja": f"Baja ($c^*={dotacion_base['baja']}$)",
        "media": f"Media ($c^*={dotacion_base['media']}$)",
        "alta": f"Alta ($c^*={dotacion_base['alta']}$)",
    }
    for esc in ["baja", "media", "alta"]:
        c_base = dotacion_base[esc]
        g_srv = srv_detalle.loc[
            (srv_detalle["escenario"] == esc) & (srv_detalle["dotacion"] == c_base)
        ].sort_values("servicio_medio_min")
        ejes[1].plot(
            g_srv["servicio_medio_min"],
            100 * g_srv["proporcion_a_tiempo"],
            marker=marcadores_esc[esc],
            markersize=4,
            linewidth=1.4,
            color=colores_esc[esc],
            label=nombres_esc[esc],
        )

    ejes[1].axhline(
        100 * cumplimiento_min,
        color="0.4",
        linestyle="--",
        linewidth=0.8,
        label=f"Umbral {100 * cumplimiento_min:g} %",
    )
    ejes[1].set_xlabel("Tiempo medio de servicio (min/pedido)")
    ejes[1].set_ylabel("Pedidos a tiempo con $c^*_{\\mathrm{base}}$ (%)")
    ejes[1].set_title("b) Sensibilidad a la duración del servicio", fontsize=8.5)
    ejes[1].set_xticks(sorted(srv_detalle["servicio_medio_min"].unique()))
    ejes[1].set_ylim(-2, 104)
    ejes[1].legend(fontsize=7, frameon=False, loc="lower left")

    for ax in ejes:
        ax.tick_params(labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="0.9", linewidth=0.5)

    fig.tight_layout()
    fig.savefig(ruta, bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(fig)


def construir_resumen_sensibilidad(consolidada: pd.DataFrame, dotacion_base: dict[str, int]) -> pd.Series:
    valores: dict[str, object] = {}
    for esc, c_base in dotacion_base.items():
        valores[f"dotacion_base_{esc}"] = c_base
    for _, f in consolidada.iterrows():
        clave = f"{f['eje']}_{f['variante']}"
        for esc in ["baja", "media", "alta"]:
            c_rec = f[f"c_rec_{esc}"]
            valores[f"{clave}_{esc}_c_rec"] = int(c_rec) if pd.notna(c_rec) else "ninguna"
            valores[f"{clave}_{esc}_a_tiempo_c_base"] = round(float(f[f"a_tiempo_c_base_{esc}"]), 4)
            valores[f"{clave}_{esc}_espera_c_base"] = round(float(f[f"espera_c_base_{esc}"]), 2)
    return pd.Series(valores, name="valor")


def main() -> int:
    config = yaml.safe_load((RAIZ / "config" / "experimento.yaml").read_text(encoding="utf-8"))
    ruta_pronostico = RESULTADOS / "pronostico_semana_siguiente.csv"
    if not ruta_pronostico.exists():
        sys.exit(f"falta {ruta_pronostico.relative_to(RAIZ)}; generalo antes con `make pronostico`")

    pronostico_semana = pd.read_csv(ruta_pronostico, index_col="hora", parse_dates=["hora"])
    cumplimiento_min = float(config["experimentos"]["cumplimiento_min"])

    dem_detalle, dem_rec = exp.analizar_sensibilidad_demanda(pronostico_semana, config)
    srv_detalle, srv_rec = exp.analizar_sensibilidad_servicio(pronostico_semana, config)

    base_rows = dem_rec.loc[
        (dem_rec["tipo"] == "intervalo_empirico") & (dem_rec["variante"] == "pronostico")
    ]
    dotacion_base = {
        str(fila["escenario"]): int(fila["dotacion_evaluada"]) for _, fila in base_rows.iterrows()
    }

    consolidada = armar_tabla_consolidada(dem_detalle, dem_rec, srv_detalle, srv_rec, dotacion_base)
    resumen_s = construir_resumen_sensibilidad(consolidada, dotacion_base)

    RESULTADOS.mkdir(parents=True, exist_ok=True)
    TABLAS.mkdir(parents=True, exist_ok=True)
    FIGURAS.mkdir(parents=True, exist_ok=True)

    dem_detalle.to_csv(RESULTADOS / "sensibilidad_demanda.csv", index=False)
    srv_detalle.to_csv(RESULTADOS / "sensibilidad_servicio.csv", index=False)
    consolidada.to_csv(RESULTADOS / "sensibilidad_recomendacion.csv", index=False)
    resumen_s.rename_axis("indicador").to_csv(RESULTADOS / "sensibilidad_resumen.csv")

    max_dotacion = max(int(c) for c in config["experimentos"]["dotaciones"])
    (TABLAS / "sensibilidad_recomendacion.tex").write_text(
        tabla_sensibilidad_latex(consolidada, srv_rec, dotacion_base, max_dotacion), encoding="utf-8"
    )
    figura_sensibilidad(
        dem_detalle, srv_detalle, dotacion_base, cumplimiento_min, FIGURAS / "sensibilidad_cumplimiento.pdf"
    )

    print(consolidada.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
