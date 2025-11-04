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
