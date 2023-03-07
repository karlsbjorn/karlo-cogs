PYTHON ?= python3.9

# Python Code Style
reformat:
	$(PYTHON) -m ruff check . --line-length 99 --ignore E501 --fix
	$(PYTHON) -m isort . --profile black
	$(PYTHON) -m black . --line-length 99
stylecheck:
	$(PYTHON) -m ruff check . --line-length 99 --ignore E501
	$(PYTHON) -m isort --check . --profile black
	$(PYTHON) -m black --check . --line-length 99
stylediff:
	$(PYTHON) -m ruff check . --line-length 99 --ignore E501 --diff
	$(PYTHON) -m isort --check --diff . --profile black
	$(PYTHON) -m black --check --diff . --line-length 99