PYTHON ?= python3.9

# Python Code Style
reformat:
	$(PYTHON) -m ruff check . --line-length 99 --ignore E501 --fix
stylecheck:
	$(PYTHON) -m ruff check . --line-length 99 --ignore E501
stylediff:
	$(PYTHON) -m ruff check . --line-length 99 --ignore E501 --diff
