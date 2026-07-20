.PHONY: install lint reformat test-local test-integration test-drift

install:
	uv venv
	uv pip install -U -e ".[dev]"

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run ty check

reformat:
	uv run ruff format src tests
	uv run ruff check --fix src tests

test-local:
	uv run pytest -m "not integration and not drift"

test-integration:
	uv run pytest -m integration

test-drift:
	uv run pytest -m drift
