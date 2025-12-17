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

from enum import Enum, StrEnum, auto


class CustomStrEnum(StrEnum):
    """Custom string enum that auto-generates values in uppercase."""

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """
        Return the upper-cased version of the member name.
        """
        return name.upper()


class FileType(CustomStrEnum):
    """Enum for CAS file source."""

    UNKNOWN = auto()
    CAMS = auto()
    KFINTECH = auto()
    CDSL = auto()
    NSDL = auto()


class FileVersion(CustomStrEnum):
    """Enum for CAS file type"""

    UNKNOWN = auto()
    SUMMARY = auto()
    DETAILED = auto()


class TransactionType(CustomStrEnum):
    """Enum for different types of transactions."""

    PURCHASE = auto()
    PURCHASE_SIP = auto()
    REDEMPTION = auto()
    DIVIDEND_PAYOUT = auto()
    DIVIDEND_REINVEST = auto()
    TRANSFER_IN = auto()
    TRANSFER_OUT = auto()
    SWITCH_IN = auto()
    SWITCH_IN_MERGER = auto()
    SWITCH_OUT = auto()
    SWITCH_OUT_MERGER = auto()
    STT_TAX = auto()
    STAMP_DUTY_TAX = auto()
    TDS_TAX = auto()
    SEGREGATION = auto()
    MISC = auto()
    UNKNOWN = auto()
    REVERSAL = auto()


class CashFlow(Enum):
    """Specify type of flow to consider in calculations. Signs are in reference to holdings."""

    ADD = 1
    SUBTRACT = -1


class SchemeType(CustomStrEnum):
    """Enum for different types of schemes."""

    STOCK = auto()
    MUTUAL_FUND = auto()
    CORPORATE_BOND = auto()
    PREFERENCE_SHARES = auto()
    UNLISTED_SHARES = auto()
    OTHER = auto()
