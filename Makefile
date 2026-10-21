# Topic 43 — reproduce the offline pipeline from the committed ground truth + API cache ($THS_DATASETS)
PY ?= python

.PHONY: reproduce figures
reproduce:
	$(PY) code/reproduce.py

figures:
	$(PY) code/p2_figures.py --seed 42
