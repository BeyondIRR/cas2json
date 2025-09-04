from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from cas2json.enums import CASFileType, FileType, TransactionType


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


@dataclass(slots=True)
class SchemeValuation:
    date: date | str
    nav: Decimal | float
    value: Decimal | float
    cost: Decimal | float | None = None


@dataclass(slots=True)
class Scheme:
    scheme_name: str
    rta_code: str
    rta: str
    open: Decimal | float
    close: Decimal | float
    close_calculated: Decimal | float
    valuation: SchemeValuation
    transactions: list[TransactionData]
    folio: str
    amc: str
    pan: str | None = None
    isin: str | None = None
    advisor: str | None = None
    nominees: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CASData:
    """CAS Parser return data type."""

    statement_period: StatementPeriod
    schemes: list[Scheme]
    investor_info: InvestorInfo
    cas_type: CASFileType
    file_type: FileType


@dataclass(slots=True)
class PartialCASData:
    """CAS Parser return data type for partial data."""

    investor_info: InvestorInfo
    file_type: FileType
    lines: list[str]


@dataclass(slots=True)
class ProcessedCASData:
    cas_type: CASFileType
    schemes: list[Scheme]
    statement_period: StatementPeriod


@dataclass(slots=True)
class DematOwner:
    name: str
    pan: str


@dataclass(slots=True)
class Equity:
    isin: str
    num_shares: Decimal
    price: Decimal
    value: Decimal
    name: str | None = None

    def __post_init__(self):
        if isinstance(self.num_shares, str):
            self.num_shares = Decimal(self.num_shares.replace(",", ""))
        if isinstance(self.price, str):
            self.price = Decimal(self.price.replace(",", ""))
        if isinstance(self.value, str):
            self.value = Decimal(self.value.replace(",", ""))


@dataclass(slots=True)
class MutualFund:
    isin: str
    balance: Decimal
    nav: Decimal
    value: Decimal
    name: str | None = None

    def __post_init__(self):
        if isinstance(self.balance, str):
            self.balance = Decimal(self.balance.replace(",", ""))
        if isinstance(self.nav, str):
            self.nav = Decimal(self.nav.replace(",", ""))
        if isinstance(self.value, str):
            self.value = Decimal(self.value.replace(",", ""))


@dataclass(slots=True)
class DematAccount:
    name: str
    type: str
    folios: int
    balance: Decimal
    owners: list[DematOwner]
    equities: list[Equity]
    mutual_funds: list[MutualFund]
    dp_id: str | None = ""
    client_id: str | None = ""

    def __post_init__(self):
        if isinstance(self.balance, str):
            self.balance = Decimal(self.balance.replace(",", ""))


@dataclass(slots=True)
class NSDLCASData:
    accounts: list[DematAccount]
    statement_period: StatementPeriod
    investor_info: InvestorInfo | None = None
    file_type: FileType | None = None
