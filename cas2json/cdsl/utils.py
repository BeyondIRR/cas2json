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

from cas2json import patterns
from cas2json.types import SchemeType


def resolve_scheme_type_from_heading(line: str) -> SchemeType | None:
    if re.search(patterns.CDSL_EQUITY_HEADER, line):
        return SchemeType.STOCK
    elif re.search(patterns.CDSL_BOND_HEADER, line):
        return SchemeType.CORPORATE_BOND
    elif re.search(patterns.CDSL_MF_FOLIOS_HEADER, line):
        return SchemeType.MUTUAL_FUND
    return None
