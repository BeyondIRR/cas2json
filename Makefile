# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 BeyondIRR <https://beyondirr.com/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
