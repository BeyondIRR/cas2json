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
    """Data Type for a single page in the CAMS document."""

    lines_data: LineData
    headers_data: dict[str, Rect]


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
    statement_period: StatementPeriod | None = None
    investor_info: InvestorInfo | None = None
    file_type: FileType = FileType.UNKNOWN
    file_version: FileVersion = FileVersion.UNKNOWN


@dataclass(slots=True)
class PartialCASData:
    """CAS Parser return data type for partial data."""

    investor_info: InvestorInfo | None
    file_type: FileType
    document_data: DocumentData
    file_version: FileVersion
    statement_period: StatementPeriod | None


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
class NSDLScheme(Scheme):
    """NSDL Scheme Data Type."""

    dp_id: str | None = ""
    client_id: str | None = ""


@dataclass(slots=True)
class NSDLCASData:
    """NSDL CAS Parser return data type."""

    accounts: list[DematAccount]
    schemes: list[NSDLScheme]
    statement_period: StatementPeriod | None = None
    investor_info: InvestorInfo | None = None
    file_type: FileType | None = None
