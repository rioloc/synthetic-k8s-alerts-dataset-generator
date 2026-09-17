.DEFAULT_GOAL := help

PYTHON ?= python3
SCENARIO ?= examples/08-seeded-variation/scenario.yaml
SEED ?= 424242
OUTPUT ?= dataset
PNG ?= timeline.png

.PHONY: help generate validate-scenario validate-dataset visualize test lint typecheck check

help:
	@printf '%s\n' \
	  'Targets:' \
	  '  generate           Generate a new dataset; never overwrite existing output' \
	  '  validate-scenario  Validate SCENARIO without sampling' \
	  '  validate-dataset   Validate the dataset at OUTPUT' \
	  '  visualize          Render OUTPUT as PNG with optional Matplotlib' \
	  '  test               Run the full unittest suite' \
	  '  lint               Check lint and formatting with existing Ruff' \
	  '  typecheck          Check types with existing mypy' \
	  '  check              Run tests, lint, type checks, and compilation' \
	  '' \
	  'Overrides: PYTHON=python3 SCENARIO=path/scenario.yaml SEED=424242 OUTPUT=dataset PNG=timeline.png' \
	  'No targets install dependencies or delete datasets.'

generate:
	"$(PYTHON)" -m generator generate --scenario "$(SCENARIO)" --seed "$(SEED)" --output "$(OUTPUT)"

validate-scenario:
	"$(PYTHON)" -m generator validate --scenario "$(SCENARIO)"

validate-dataset:
	"$(PYTHON)" -m generator validate --dataset "$(OUTPUT)"

visualize:
	"$(PYTHON)" -m tools.visualize --dataset "$(OUTPUT)" --output "$(PNG)"

test:
	"$(PYTHON)" -m unittest discover -s tests -v

lint:
	ruff check --no-cache generator tools tests
	ruff format --no-cache --check generator tools tests

typecheck:
	mypy --python-executable "$(PYTHON)" --no-incremental --cache-dir=/dev/null --check-untyped-defs generator tools tests

check: test lint typecheck
	"$(PYTHON)" -m compileall -q generator tools tests
