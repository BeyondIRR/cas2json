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
