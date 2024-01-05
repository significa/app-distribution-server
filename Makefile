help: ## Show this help
	@egrep -h '\s##\s' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-21s\033[0m %s\n", $$1, $$2}'

setup-venv: ## Setup a local venv
	python3 -m venv env

install-deps: ## Install python dependencies for development
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

dev: ## Setup a local venv
	uvicorn src.app:app --reload

lint: ## Ensure code properly formatted
	pycodestyle .
	flake8 .
	isort . --check

format: ## Format the code according to the standards
	autopep8 --recursive --in-place .
	flake8 --format .
	isort .

lock-deps: ## Lock dependencies to requirements.txt
	pip-compile requirements-dev.in
	pip-compile requirements.in
