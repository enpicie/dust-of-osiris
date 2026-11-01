.PHONY: test venv lint build dev

# Ensure venv exists
venv:
	@test -d .venv || python3 -m venv .venv

# Single command to do everything: venv, install, run tests
test: venv
	@.venv/bin/pip install -q -r requirements-dev.txt
	@.venv/bin/pip install -q -r jobs/deferred_worker/requirements.txt
	@PYTHONPATH="$$PYTHONPATH:$(CURDIR)/src" .venv/bin/pytest tests/

# Lint all Python source with ruff (installs dev requirements into the venv first)
lint: venv
	@.venv/bin/pip install -q -r requirements-dev.txt
	@.venv/bin/ruff check .

# Zip each Lambda's source into dist/, mirroring CI's upload action
build:
	@mkdir -p dist
	@cd src && zip -qr ../dist/bot.zip .
	@cd jobs/deferred_worker && zip -qr ../../dist/deferred-worker.zip .
	@echo "Built Lambda zips in dist/"

# There is no local Discord stack — the bot only runs deployed behind API Gateway.
dev:
	@echo "There is no local development stack for this project."
	@echo "Discord interactions require a deployed endpoint (API Gateway -> Lambda)."
	@echo "Push to any non-main branch to deploy to dev via the 'Dev Pipeline' GitHub Actions workflow,"
	@echo "or trigger it manually with workflow_dispatch. Use 'make test' for local verification."
