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

from collections import defaultdict

from cas2json.enums import CashFlow, TransactionType

HOLDINGS_CASHFLOW = defaultdict(
    lambda: CashFlow.ADD,
    {
        TransactionType.PURCHASE: CashFlow.ADD,
        TransactionType.PURCHASE_SIP: CashFlow.ADD,
        TransactionType.DIVIDEND_REINVEST: CashFlow.ADD,
        TransactionType.SWITCH_IN: CashFlow.ADD,
        TransactionType.SWITCH_IN_MERGER: CashFlow.ADD,
        TransactionType.STT_TAX: CashFlow.ADD,
        TransactionType.STAMP_DUTY_TAX: CashFlow.ADD,
        TransactionType.TDS_TAX: CashFlow.ADD,
        TransactionType.SEGREGATION: CashFlow.ADD,
        TransactionType.MISC: CashFlow.ADD,
        TransactionType.UNKNOWN: CashFlow.ADD,
        TransactionType.REVERSAL: CashFlow.ADD,
        TransactionType.REDEMPTION: CashFlow.SUBTRACT,
        TransactionType.SWITCH_OUT: CashFlow.SUBTRACT,
        TransactionType.DIVIDEND_PAYOUT: CashFlow.SUBTRACT,
        TransactionType.SWITCH_OUT_MERGER: CashFlow.SUBTRACT,
    },
)

MISCELLANEOUS_KEYWORDS = ("mobile", "address", "details", "nominee", "change")
