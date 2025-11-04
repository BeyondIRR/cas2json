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

import re
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from cas2json.exceptions import HeaderParseError
from cas2json.flags import MULTI_TEXT_FLAGS


def get_statement_dates(parsed_lines: list[str], reg_exp: str) -> tuple[str | Any, ...]:
    """
    Helper to get dates for which the statement is applicable.
    """
    text = "\u2029".join(parsed_lines)
    if m := re.search(reg_exp, text, MULTI_TEXT_FLAGS):
        return m.groups()
    raise HeaderParseError("Error parsing CAS header")


def formatINR(value: str | None) -> Decimal | None:
    """Helper to format amount related strings to Decimal."""
    if isinstance(value, str):
        return Decimal(value.replace(",", "_").replace("(", "-").replace(")", ""))
    return None


def format_values(values: Iterable[str | None]) -> list[Decimal | None]:
    return [formatINR(value) for value in values]
