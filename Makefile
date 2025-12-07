PYTHON=python
MANAGE=backend/manage.py

lint:
\truff check .

typecheck:
\tmypy ai parking

test:
\t$(PYTHON) $(MANAGE) test

migrate_safe:
\t$(PYTHON) $(MANAGE) migrate_safe --apply

.PHONY: lint typecheck test migrate_safe
