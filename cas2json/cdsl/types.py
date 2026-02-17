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

from dataclasses import dataclass
from decimal import Decimal

from cas2json.types import DepositoryScheme


@dataclass(slots=True)
class CDSLMFScheme(DepositoryScheme):
    """Scheme Data Type for CDSL types"""

    broker: str | None = None
    gain: Decimal | None = None
    gain_pct: Decimal | None = None
    expense_regular_pct: Decimal | None = None
    expense_direct_pct: Decimal | None = None
    commission: Decimal | None = None
