from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pymupdf import Rect

from cas2json.constants import HOLDINGS_CASHFLOW
from cas2json.enums import FileType, FileVersion, SchemeType, TransactionType

WordData = tuple[Rect, str]
DocumentData = list["PageData"]
LineData = Generator[tuple[str, list[WordData]]]


@dataclass(slots=True, frozen=True)
class PageData:
    lines_data: LineData
    headers_data: dict[str, Rect]


@dataclass(slots=True)
class StatementPeriod:
    to: str
    from_: str = field(default_factory=list)


@dataclass(slots=True)
class InvestorInfo:
    name: str
    email: str
    address: str
    mobile: str


@dataclass(slots=True)
class TransactionData:
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
    isin: str
    scheme_name: str
    nav: Decimal | float
    units: Decimal | float
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


@dataclass(slots=True)
class CAMSScheme(Scheme):
    pan: str | None = None
    nominees: list[str] = field(default_factory=list)
    transactions: list[TransactionData] = field(default_factory=list)
    advisor: str | None = None
    amc: str | None = None
    rta: str | None = None
    rta_code: str | None = None
    opening_units: Decimal | float | None = None
    closing_units: Decimal | float | None = None


@dataclass(slots=True)
class CASData:
    """CAS Parser return data type."""

    statement_period: StatementPeriod | None
    schemes: list[Scheme]
    investor_info: InvestorInfo | None = None
    file_type: FileType = FileType.UNKNOWN
    file_version: FileVersion = FileVersion.UNKNOWN


@dataclass(slots=True)
class PartialCASData:
    """CAS Parser return data type for partial data."""

    investor_info: InvestorInfo
    file_type: FileType
    document_data: DocumentData
    file_version: FileVersion


@dataclass(slots=True)
class DematOwner:
    name: str
    pan: str


@dataclass(slots=True)
class DematAccount:
    name: str
    ac_type: str
    units: Decimal
    schemes_count: int
    dp_id: str | None = ""
    folios: int | None = None
    client_id: str | None = ""
    holders: list[DematOwner] = field(default_factory=list)


@dataclass(slots=True)
class NSDLCASData:
    accounts: list[DematAccount]
    schemes: list[Scheme]
    statement_period: StatementPeriod
    investor_info: InvestorInfo | None = None
    file_type: FileType | None = None


@dataclass(slots=True)
class NSDLScheme(Scheme):
    dp_id: str | None = ""
    client_id: str | None = ""
