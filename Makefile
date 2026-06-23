.PHONY: test experiments notebooks

test:
	pytest

experiments:
	python scripts/run_all_experiments.py

notebooks:
	python scripts/build_notebooks.py
