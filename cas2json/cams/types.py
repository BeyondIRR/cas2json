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

from dataclasses import dataclass, field
from decimal import Decimal

from pymupdf import Rect

from cas2json.types import BasePageData, CASMetaData, Scheme, TransactionData


@dataclass(slots=True, frozen=True)
class CAMSPageData(BasePageData):
    """Data Type for a single page in the CAMS document."""

    headers_data: dict[str, Rect]


@dataclass(slots=True)
class CAMSScheme(Scheme):
    """CAMS Scheme Data Type."""

    pan: str | None = None
    nominees: list[str] = field(default_factory=list)
    transactions: list[TransactionData] = field(default_factory=list)
    advisor: str | None = None
    amc: str | None = None
    rta: str | None = None
    rta_code: str | None = None
    opening_units: Decimal | float | None = None
    calculated_units: Decimal | float | None = None


@dataclass(slots=True)
class CAMSData:
    """CAS Parser return data type."""

    schemes: list[CAMSScheme]
    metadata: CASMetaData
