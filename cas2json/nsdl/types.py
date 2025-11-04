from dataclasses import dataclass, field
from decimal import Decimal

from cas2json.types import CASMetaData, Scheme


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
    metadata: CASMetaData | None = None
