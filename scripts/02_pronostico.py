"""Paso 2: pronostica los pedidos por hora y evalúa el error en un período reservado.

Compara el ingenuo estacional con la media estacional de k semanas. k se elige en las
semanas de validación y los errores finales se informan en las semanas de prueba, que
no intervienen en ninguna elección. La tasa verdadera del generador se agrega como
referencia: es el error que queda solo por el azar de las llegadas.

Salidas:
- resultados/pronostico_errores.csv: métricas por período y método.
- resultados/pronostico_prueba.csv: real, tasa verdadera y pronósticos en la prueba.
- resultados/pronostico_semana_siguiente.csv: pronóstico e intervalo de la semana
  posterior al histórico, con el método elegido en validación.
- resultados/pronostico_resumen.csv: partición, k y método elegidos y cifras derivadas
  que cita el informe (reducción del MAE, sesgo diario, cuantiles de residuos, totales
  de la semana siguiente).
- informe/tablas/pronostico_errores.tex y informe/figuras/pronostico_prueba.pdf.

Uso: python scripts/02_pronostico.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from pedidos import pronostico as pr  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "datos" / "procesados"
RESULTADOS = RAIZ / "resultados"
TABLAS = RAIZ / "informe" / "tablas"
FIGURAS = RAIZ / "informe" / "figuras"

NOMBRES = {"ingenuo": "Ingenuo estacional", "tasa_verdadera": "Tasa verdadera (referencia)"}


def nombre(metodo: str) -> str:
    if metodo.startswith("media_"):
        return f"Media estacional ($k={metodo.removeprefix('media_').removesuffix('s')}$)"
    return NOMBRES[metodo]


def leer_serie(archivo: str, columna: str) -> pd.Series:
    ruta = PROCESADOS / archivo
    if not ruta.exists():
        sys.exit(f"falta {ruta.relative_to(RAIZ)}; generalo antes con `make datos`")
    return pd.read_csv(ruta, index_col="hora", parse_dates=["hora"])[columna]


def pronosticos(serie: pd.Series, objetivos: pd.DatetimeIndex, candidatos: list[int]) -> dict[str, pd.Series]:
    resultado = {"ingenuo": pr.ingenuo_estacional(serie, objetivos)}
    for k in candidatos:
        resultado[f"media_{k}s"] = pr.media_estacional(serie, objetivos, k)
    return resultado


def tabla_latex(errores: pd.DataFrame) -> str:
    filas = []
    for metodo, fila in errores.iterrows():
        filas.append(
            f"{nombre(metodo)} & \\num{{{fila.mae:.2f}}} & \\num{{{fila.rmse:.2f}}} & "
            f"\\num{{{fila.sesgo:.2f}}} & \\num{{{fila.mae_diario:.1f}}} & "
            f"\\num{{{100 * fila.mae_relativo:.1f}}} \\\\"
        )
    return "\n".join(
        [
            "% Generado por scripts/02_pronostico.py; no editar a mano. Errores en pedidos por hora, salvo MAE diario (pedidos por día).",
            r"\begin{tabular}{lrrrrr}",
            r"\toprule",
            r"Método & MAE & RMSE & Sesgo & MAE diario & MAE rel. (\%) \\",
            r"\midrule",
            *filas,
            r"\bottomrule",
            r"\end{tabular}",
            "",
        ]
    )


def figura(prueba: pd.DataFrame, metodos: list[str], ruta: Path) -> None:
    semana = prueba[prueba.index >= prueba.index.max().normalize() - pd.Timedelta(days=6)]
    x = range(len(semana))
    fig, ax = plt.subplots(figsize=(6.3, 2.9))  # ancho de texto: letra a tamaño real
    ax.bar(x, semana["real"], color="0.82", width=1.0, label="Pedidos observados")
    ax.plot(x, semana["tasa_verdadera"], color="black", linestyle="--", linewidth=1, label="Tasa verdadera")
    estilos = {"ingenuo": ("#d1495b", "-"), "media": ("#00798c", "-")}
    for metodo in metodos:
        color, linea = estilos["ingenuo" if metodo == "ingenuo" else "media"]
        ax.plot(x, semana[metodo], color=color, linestyle=linea, linewidth=1.4, label=nombre(metodo))

    dias = semana.index.normalize()
    inicios = [i for i in range(len(dias)) if i == 0 or dias[i] != dias[i - 1]]
    etiquetas = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    ax.set_xticks(
        [i + 6 for i in inicios],
        [f"{etiquetas[dias[i].day_of_week]} {dias[i]:%d/%m}" for i in inicios],
        fontsize=8,
    )
    for i in inicios[1:]:
        ax.axvline(i - 0.5, color="0.6", linewidth=0.5)
    ax.set_xlim(-0.5, len(semana) - 0.5)
    ax.set_ylabel("Pedidos por hora")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), fontsize=7.5, ncol=4, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(ruta, metadata={"CreationDate": None})  # misma salida en cada corrida
    plt.close(fig)


def main() -> int:
    config = yaml.safe_load((RAIZ / "config" / "experimento.yaml").read_text())
    cfg = config["pronostico"]
    candidatos = [int(k) for k in cfg["semanas_media"]]

    serie = leer_serie("serie_horaria.csv", "pedidos")
    tasa = leer_serie("tasa_esperada.csv", "tasa")
    validacion, prueba = pr.particion(serie, cfg["semanas_validacion"], cfg["semanas_prueba"])

    # Validación: elegir k y, después, el método.
    k = pr.elegir_semanas(serie, validacion, candidatos)
    media = f"media_{k}s"
    filas = []
    for periodo, indice in [("validacion", validacion), ("prueba", prueba)]:
        real = serie.reindex(indice)
        candidatos_periodo = pronosticos(serie, indice, candidatos)
        candidatos_periodo["tasa_verdadera"] = tasa.reindex(indice)
        for metodo, valores in candidatos_periodo.items():
            filas.append({"periodo": periodo, "metodo": metodo, **pr.errores(real, valores)})
    errores = pd.DataFrame(filas).set_index(["periodo", "metodo"])

    en_validacion = errores.loc["validacion"]
    elegido = media if en_validacion.loc[media, "mae"] <= en_validacion.loc["ingenuo", "mae"] else "ingenuo"
    semanas_elegido = k if elegido == media else 1

    # Prueba: series para revisar y residuos del método elegido.
    tabla_prueba = pd.DataFrame(
        {"real": serie.reindex(prueba), "tasa_verdadera": tasa.reindex(prueba), **pronosticos(serie, prueba, candidatos)}
    )
    residuos = tabla_prueba["real"] - tabla_prueba[elegido]

    siguiente = pr.intervalo_empirico(
        pr.pronosticar_semana(serie, semanas_elegido), residuos, cfg["nivel_intervalo"]
    )

    RESULTADOS.mkdir(exist_ok=True)
    errores.to_csv(RESULTADOS / "pronostico_errores.csv")
    tabla_prueba.rename_axis("hora").to_csv(RESULTADOS / "pronostico_prueba.csv")
    siguiente.rename_axis("hora").to_csv(RESULTADOS / "pronostico_semana_siguiente.csv")

    en_prueba = errores.loc["prueba"].loc[["ingenuo", media, "tasa_verdadera"]]
    TABLAS.mkdir(parents=True, exist_ok=True)
    FIGURAS.mkdir(parents=True, exist_ok=True)
    (TABLAS / "pronostico_errores.tex").write_text(tabla_latex(en_prueba))
    figura(tabla_prueba, ["ingenuo", media], FIGURAS / "pronostico_prueba.pdf")

    indicadores = resumen(errores.loc["prueba"], tabla_prueba, elegido, residuos, siguiente, cfg["nivel_intervalo"])
    indicadores = pd.concat(
        [
            pd.Series(
                {
                    "inicio_validacion": f"{validacion.min():%Y-%m-%d}",
                    "inicio_prueba": f"{prueba.min():%Y-%m-%d}",
                    "fin_prueba": f"{prueba.max():%Y-%m-%d}",
                    "k_elegido": k,
                    "metodo_elegido": elegido,
                }
            ),
            indicadores,
        ]
    )
    indicadores.rename("valor").rename_axis("indicador").to_csv(RESULTADOS / "pronostico_resumen.csv")

    print(errores.round(3).to_string())
    print("\n" + indicadores.to_string())
    return 0


def resumen(
    errores_prueba: pd.DataFrame,
    tabla_prueba: pd.DataFrame,
    elegido: str,
    residuos: pd.Series,
    siguiente: pd.DataFrame,
    nivel: float,
) -> pd.Series:
    """Cifras derivadas que cita el informe, para no calcularlas a mano."""
    mae = errores_prueba["mae"]
    dias_prueba = tabla_prueba.index.normalize().nunique()
    demanda_diaria = tabla_prueba["real"].sum() / dias_prueba
    sesgo_diario = (tabla_prueba[elegido] - tabla_prueba["real"]).sum() / dias_prueba
    alfa = (1 - nivel) / 2
    por_dia = siguiente.groupby(siguiente.index.normalize())["pronostico"].sum()
    pico = siguiente["pronostico"].idxmax()

    valores = {
        "reduccion_mae_vs_ingenuo": 1 - mae[elegido] / mae["ingenuo"],
        "distancia_mae_al_piso": mae[elegido] - mae["tasa_verdadera"],
        "demanda_diaria_prueba": demanda_diaria,
        "sesgo_diario_prueba": sesgo_diario,
        "sesgo_relativo_prueba": sesgo_diario / demanda_diaria,
        f"residuo_cuantil_{alfa:.2f}": residuos.quantile(alfa),
        f"residuo_cuantil_{1 - alfa:.2f}": residuos.quantile(1 - alfa),
        "pico_semana_siguiente": siguiente.loc[pico, "pronostico"],
        "hora_pico_semana_siguiente": f"{pico:%Y-%m-%d %H:%M}",
    }
    for dia, total in por_dia.items():
        valores[f"pedidos_{dia:%Y-%m-%d}"] = total
    return pd.Series(valores).map(lambda v: round(v, 4) if isinstance(v, float) else v)


if __name__ == "__main__":
    sys.exit(main())
