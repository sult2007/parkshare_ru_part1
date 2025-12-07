PYTHON=python
MANAGE=backend/manage.py

lint:
\truff check .

typecheck:
\tmypy ai parking

test:
\t$(PYTHON) $(MANAGE) test

.PHONY: lint typecheck test
