PYTHON := .venv/bin/python

.PHONY: setup
setup:
	bash scripts/setup_workshop.sh
	git init
	test -d .venv || uv venv .venv
	uv pip install rich httpx

.PHONY: module_1 module_2 module_3 module_4 module_5 module_7
module_1:
	bash scripts/setup_modules.sh 1

module_2:
	bash scripts/setup_modules.sh 2

module_3:
	bash scripts/setup_modules.sh 3

module_4:
	bash scripts/setup_modules.sh 4

module_5:
	bash scripts/setup_modules.sh 5

module_7:
	bash scripts/setup_modules.sh 7

.PHONY: test_module_1
test_module_1:
	$(PYTHON) tests/test_module_1.py

.PHONY: test_module_2
test_module_2:
	$(PYTHON) tests/test_module_2.py
