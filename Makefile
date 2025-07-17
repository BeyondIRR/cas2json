UV_EXISTS := $(shell command -v uv 2> /dev/null)

install:
	@echo "-> Configuring uv package manager"
ifndef UV_EXISTS
	curl -LsSf https://astral.sh/uv/install.sh | sh
endif
	uv venv --python 3.12

dev: install
	@echo "-> Installing Developer Dependencies"
	uv sync
	uvx pre-commit install

format:
	@echo "Formatting code..."
	uvx ruff format .
	uvx ruff check --fix . || true

clean: format
	@echo "Clearing python cache"
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	@echo "Clearing build files"
	rm -rf build dist *.egg-info .*_cache

package: clean
	@echo "Packaging code..."
	uv build

remove-hooks:
	@echo "-> Removing the pre-commit hooks"
	uv run pre-commit uninstall
