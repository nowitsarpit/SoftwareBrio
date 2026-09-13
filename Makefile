.PHONY: install test dry-run run docker-build docker-run lint clean

PYTHON ?= python

install:
	$(PYTHON) -m pip install --upgrade pip
	pip install -r requirements.txt
	playwright install chromium

test:
	OPENAI_API_KEY=sk-test-dummy-key pytest tests/ -v --tb=short

dry-run:
	$(PYTHON) -m app.main --input data/input.json --dry-run

run:
	$(PYTHON) -m app.main --input data/input.json --output data/output.json --output-format all

docker-build:
	docker build -t lead-enrichment:latest .

docker-run:
	docker compose up --build

lint:
	ruff check app/ tests/ || true

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
