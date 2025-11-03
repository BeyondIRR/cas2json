from collections.abc import Generator
from dataclasses import dataclass
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
    scheme_name: str
    nav: Decimal | float | None
    units: Decimal | float | None
    cost: Decimal | float | None
    folio: str | None = None
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
