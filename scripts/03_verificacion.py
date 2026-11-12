"""Genera resultados/verificacion_{replicas,mmc}.csv y tablas LaTeX de servicio y verificación."""

from pathlib import Path

import yaml

from pedidos.verificacion import verificar_mmc

RAIZ = Path(__file__).resolve().parents[1]
ETIQUETAS = {
    "espera_media_min": r"$W_q$ (min)", "total_medio_min": r"$W$ (min)",
    "cola_media": r"$L_q$ (pedidos)", "utilizacion": r"$\rho$ (fracción)",
    "sistema_medio": r"$L$ (pedidos)", "diferencia_little": r"$L-\hat\lambda W$ (pedidos)",
}


def main() -> None:
    config = yaml.safe_load((RAIZ / "config/experimento.yaml").read_text(encoding="utf-8"))
    p = config["verificacion"]
    servicio = config["servicio"]
    fijo = str(servicio["minutos_fijos"]).replace(".", ",")
    por_linea = str(servicio["minutos_por_linea"]).replace(".", ",")
    tabla_servicio = [
        r"\begin{table}[htbp]\centering",
        r"\caption{Hipótesis de duración de la preparación para la jornada.}",
        r"\label{tab:servicio}",
        r"\begin{tabular}{lr}\toprule Componente & Minutos \\ \midrule",
        rf"Tiempo fijo por pedido ($b$) & {fijo} \\",
        rf"Tiempo adicional por línea ($m$) & {por_linea} \\",
        r"\bottomrule\end{tabular}\end{table}",
    ]
    (RAIZ / "informe/tablas/servicio.tex").write_text("\n".join(tabla_servicio) + "\n", encoding="utf-8")
    muestras, tabla = verificar_mmc(p)
    muestras.to_csv(RAIZ / "resultados/verificacion_replicas.csv", index=False)
    tabla.to_csv(RAIZ / "resultados/verificacion_mmc.csv")
    porcentaje = p["confianza"] * 100
    filas = [
        r"\begin{table}[htbp]\centering",
        rf"\caption{{Referencia M/M/$c$ y estimaciones con {p['replicas']} réplicas independientes.",
        rf"Se utilizaron $\lambda={p['llegadas_h']}$ pedidos/h, $\mu={p['servicio_h']}$ pedidos/h por preparador",
        rf"y $c={p['dotacion']}$, con {p['calentamiento_h']} h de calentamiento y {p['observacion_h']} h de observación.}}",
        r"\label{tab:verificacion-mmc}",
        r"\begin{tabular}{lrrr}\toprule",
        rf"Indicador & Teoría & Simulación & IC aprox. del {porcentaje:g}\,\% \\ \midrule",
    ]
    for indicador, fila in tabla.iterrows():
        numeros = [f"{fila[c]:.5f}".replace(".", ",") for c in ("teoria", "simulacion", "inferior", "superior")]
        teoria, media, inferior, superior = numeros
        filas.append(rf"{ETIQUETAS[indicador]} & {teoria} & {media} & [{inferior}; {superior}] \\")
    filas.extend([r"\bottomrule\end{tabular}", r"\end{table}"])
    (RAIZ / "informe/tablas/verificacion_mmc.tex").write_text("\n".join(filas) + "\n", encoding="utf-8")
    print(tabla.to_string())


if __name__ == "__main__":
    main()
