help: ## Show this help
	@egrep -h '\s##\s' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-21s\033[0m %s\n", $$1, $$2}'

setup-venv: ## Setup a local venv
	python3 -m venv venv

install-deps: ## Install python dependencies for development
	pip install -r requirements.txt -r requirements-dev.txt

start: ## Start a production like server
	uvicorn --host=0.0.0.0 --port=8000 ipa_app_distribution_server.app:app

dev: ## Start the local developent server
	uvicorn --host=0.0.0.0 --port=8000 ipa_app_distribution_server.app:app --reload

lint: ## Ensure code properly formatted
	pycodestyle .
	flake8 .
	isort . --check
	pyright .

format: ## Format the code according to the standards
	find . -name '*.py' -not -path "./venv/*" -exec add-trailing-comma {} +
	autopep8 --recursive --in-place .
	isort .
	flake8 --show-source --format .

lock-deps: ## Lock dependencies to requirements.txt
	pip-compile --strip-extras requirements-dev.in > requirements-dev.txt
	pip-compile --strip-extras requirements.in > requirements.txt
