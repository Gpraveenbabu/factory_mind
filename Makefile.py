.PHONY: install test lint run train evaluate docker-up demo clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=factorymind --cov-report=term-missing

lint:
	ruff check factorymind/ tests/
	ruff format --check factorymind/ tests/

format:
	ruff format factorymind/ tests/

typecheck:
	mypy factorymind/

run:
	uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

train:
	python scripts/train_models.py --config configs/default.yaml

evaluate:
	python scripts/run_evaluation.py --config configs/default.yaml

docker-up:
	docker compose up --build

demo:
	python demo.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache data/synthetic/*.csv