"""Arma el comprimido de entrega a partir de una versión fijada del repositorio.

La consigna exige que el trabajo pueda reproducirse "a partir de los archivos
entregados". Por eso el comprimido no se arma desde la carpeta de trabajo (que
puede tener cambios sin commitear) sino desde una referencia de Git, idealmente
el tag de entrega, y se comprueba la reproducción sobre esa misma copia:

1. Extrae la referencia en dos copias temporales: una limpia, que es la que se
   comprime, y otra de trabajo, donde se ejecuta todo.
2. En la copia de trabajo compila el informe y ejecuta el notebook, que vuelve a
   correr el pipeline completo.
3. Verifica que los resultados numéricos regenerados (CSV de resultados/ y
   tablas del informe) sean idénticos byte a byte a los versionados. Si alguno
   difiere, aborta sin generar el comprimido.
4. Comprime la copia limpia más lo que Git no versiona pero el profesor necesita:
   el PDF del informe, los datos procesados y el notebook con sus salidas.

Salidas:
- entrega/io2-pedidos-<versión>.zip, con todo dentro de la carpeta io2-pedidos/.

Requiere Git, latexmk con biber y el entorno de requirements.txt (Jupyter incluido).
La comprobación completa tarda unos minutos, sobre todo por el análisis de sensibilidad.

Uso: python scripts/entrega.py [--ref v1.0-entrega]
"""

import argparse
import hashlib
import io
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient

RAIZ = Path(__file__).resolve().parents[1]
NOTEBOOK = Path("notebooks/recorrido.ipynb")
PREFIJO = "io2-pedidos"


def git(*argumentos: str) -> bytes:
    return subprocess.run(["git", *argumentos], cwd=RAIZ, check=True, capture_output=True).stdout


def extraer(ref: str, destino: Path) -> None:
    """Copia en destino los archivos versionados en ref, sin historia ni archivos ignorados."""
    with tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", ref))) as tar:
        tar.extractall(destino, filter="data")


def huellas_numericas(raiz: Path) -> dict[str, str]:
    """SHA-256 de los archivos que contienen los números citados en el informe."""
    rutas = sorted((raiz / "resultados").glob("*.csv")) + sorted((raiz / "informe" / "tablas").glob("*.tex"))
    return {r.relative_to(raiz).as_posix(): hashlib.sha256(r.read_bytes()).hexdigest() for r in rutas}


def compilar_informe(raiz: Path) -> Path:
    informe = raiz / "informe"
    corrida = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "main.tex"], cwd=informe, capture_output=True, text=True
    )
    pdf = informe / "main.pdf"
    if corrida.returncode != 0 or not pdf.exists():
        sys.exit(f"falló la compilación del informe:\n{corrida.stdout[-3000:]}")
    return pdf


def ejecutar_notebook(raiz: Path) -> nbformat.NotebookNode:
    ruta = raiz / NOTEBOOK
    notebook = nbformat.read(ruta, as_version=4)
    NotebookClient(notebook, timeout=1800, kernel_name="python3", resources={"metadata": {"path": str(ruta.parent)}}).execute()
    return notebook


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", default="HEAD", help="tag, rama o commit a entregar (por defecto, HEAD)")
    args = parser.parse_args()

    version = git("describe", "--tags", "--always", args.ref).decode().strip()
    salida = RAIZ / "entrega" / f"{PREFIJO}-{version}.zip"

    with tempfile.TemporaryDirectory() as tmp:
        limpia, trabajo = Path(tmp) / "limpia", Path(tmp) / "trabajo"
        extraer(args.ref, limpia)
        extraer(args.ref, trabajo)
        print(f"Versión {version} extraída.")

        pdf = compilar_informe(trabajo)
        print("Informe compilado.")

        versionadas = huellas_numericas(trabajo)
        print("Ejecutando el notebook (corre el pipeline completo)...")
        notebook = ejecutar_notebook(trabajo)
        regeneradas = huellas_numericas(trabajo)
        distintos = sorted(a for a in versionadas.keys() | regeneradas.keys() if versionadas.get(a) != regeneradas.get(a))
        if distintos:
            sys.exit("los resultados regenerados no coinciden con los versionados:\n  " + "\n  ".join(distintos))
        print(f"Reproducción verificada: {len(versionadas)} archivos numéricos idénticos.")

        extras = {
            Path("informe/main.pdf"): pdf.read_bytes(),
            NOTEBOOK: nbformat.writes(notebook).encode(),
        }
        for procesado in sorted((trabajo / "datos" / "procesados").glob("*.csv")):
            extras[procesado.relative_to(trabajo)] = procesado.read_bytes()

        salida.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as zf:
            for archivo in sorted(p for p in limpia.rglob("*") if p.is_file()):
                relativo = archivo.relative_to(limpia)
                if relativo not in extras:
                    zf.write(archivo, f"{PREFIJO}/{relativo.as_posix()}")
            for relativo, contenido in extras.items():
                zf.writestr(f"{PREFIJO}/{relativo.as_posix()}", contenido)

    print(f"Entrega: {salida.relative_to(RAIZ)} ({salida.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
