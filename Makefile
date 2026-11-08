PY = python

.PHONY: all datos pronostico verificacion experimentos sensibilidad informe test clean

all: datos pronostico verificacion experimentos sensibilidad informe

datos:
	$(PY) scripts/01_preparar_datos.py

pronostico:
	$(PY) scripts/02_pronostico.py

verificacion:
	$(PY) scripts/03_verificacion.py

experimentos:
	$(PY) scripts/04_experimentos.py

sensibilidad:
	$(PY) scripts/05_sensibilidad.py

informe:
	cd informe && latexmk -pdf -interaction=nonstopmode main.tex

test:
	$(PY) -m pytest -q

clean:
	cd informe && latexmk -C
