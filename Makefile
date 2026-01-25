.PHONY: install dev test lint clean

install:
	python3 -m pip install .

dev:
	python3 -m pip install -e ".[dev]"

test:
	python3 -m pytest

lint:
	python3 -m ruff check .

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
