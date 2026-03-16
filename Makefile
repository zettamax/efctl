.PHONY: run setup clean scan help

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help:
	@echo "efctl - EcoFlow BLE CLI monitor"
	@echo ""
	@echo "  make setup   - create venv and install"
	@echo "  make run     - launch TUI"
	@echo "  make scan    - quick BLE scan"
	@echo "  make clean   - remove venv"
	@echo ""
	@echo "First run:  make setup && make run"

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

setup: $(VENV)/bin/activate
	$(PIP) install -e .
	@echo ""
	@echo "Setup complete. Run:  make run"

run: $(VENV)/bin/activate
	@$(PYTHON) -m efctl $(ARGS)

scan: $(VENV)/bin/activate
	@$(PYTHON) -m efctl --scan

clean:
	rm -rf $(VENV) __pycache__ efctl/__pycache__ *.egg-info
