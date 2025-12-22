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

from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TypeVar

from pymupdf import Rect

from cas2json.constants import HOLDINGS_CASHFLOW
from cas2json.enums import FileType, FileVersion, SchemeType, TransactionType

T = TypeVar("T", bound="BasePageData")

WordData = tuple[Rect, str]
DocumentData = list[T]
LineData = Generator[tuple[str, list[WordData]]]


@dataclass(slots=True, frozen=True)
class BasePageData:
    """Data Type for a single page in the CAS document."""

    lines_data: LineData
    width: float
    height: float


@dataclass(slots=True)
class StatementPeriod:
    """Statement Period Data Type"""

    to: str | None
    from_: str | None


@dataclass(slots=True)
class InvestorInfo:
    """Investor Information Data Type"""

    name: str
    email: str | None
    address: str
    mobile: str


@dataclass(slots=True)
class TransactionData:
    """Transaction Data Type for CAMS"""

    date: date | str
    description: str
    type: TransactionType
    amount: Decimal | float | None = None
    units: Decimal | float | None = None
    nav: Decimal | float | None = None
    balance: Decimal | float | None = None
    dividend_rate: Decimal | float | None = None

    def __post_init__(self):
        if isinstance(self.amount, Decimal | float):
            if self.units is None:
                self.amount = HOLDINGS_CASHFLOW[self.type].value * self.amount
            else:
                self.amount = (1 if self.units > 0 else -1) * abs(self.amount)


@dataclass(slots=True)
class Scheme:
    """Base Scheme Data Type."""

    isin: str | None
    nav: Decimal | float | None
    units: Decimal | float | None
    scheme_name: str | None = None
    folio: str | None = None
    cost: Decimal | float | None = None
    market_value: Decimal | float | None = None
    invested_value: Decimal | float | None = None
    scheme_type: SchemeType = SchemeType.OTHER

    def __post_init__(self):
        if not self.invested_value and self.cost and self.units:
            self.invested_value = self.cost * self.units
        if not self.market_value and self.nav and self.units:
            self.market_value = self.nav * self.units


@dataclass(slots=True, frozen=True)
class CASMetaData:
    """CAS Parser Metadata Type."""

    file_type: FileType
    file_version: FileVersion
    statement_period: StatementPeriod | None
    investor_info: InvestorInfo | None


@dataclass(slots=True)
class CASParsedData:
    """CAS Parser return data type for partial data."""

    metadata: CASMetaData
    document_data: DocumentData


@dataclass(slots=True)
class DematOwner:
    """Demat Account Owner Data Type for NSDL."""

    name: str
    pan: str


@dataclass(slots=True)
class DematAccount:
    """Demat Account Data Type for NSDL."""

    name: str
    ac_type: str | None
    units: Decimal | None
    schemes_count: int
    dp_id: str | None = ""
    folios: int = 0
    client_id: str | None = ""
    holders: list[DematOwner] = field(default_factory=list)


@dataclass(slots=True)
class DepositoryScheme(Scheme):
    """CDSL Scheme Data Type."""

    dp_id: str | None = ""
    client_id: str | None = ""


@dataclass(slots=True)
class DepositoryCASData:
    """CDSL CAS Parser return data type."""

    accounts: list[DematAccount]
    schemes: list[DepositoryScheme]
    metadata: CASMetaData | None = None
