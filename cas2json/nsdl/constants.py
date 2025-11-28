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

from cas2json.types import SchemeType

SCHEME_MAP = defaultdict(
    lambda: SchemeType.OTHER,
    {
        "Equities (E)": SchemeType.STOCK,
        "Mutual Funds (M)": SchemeType.MUTUAL_FUND,
        "Corporate Bonds (C)": SchemeType.CORPORATE_BOND,
        "Preference Shares (P)": SchemeType.PREFERENCE_SHARES,
        "Mutual Fund Folios (F)": SchemeType.MUTUAL_FUND,
    },
)
NSDL_STOCK_HEADERS = [("cost", (230, 280)), ("units", (310, 350)), ("nav", (405, 440)), ("market_value", (505, 550))]
NSDL_MF_HEADERS = [("units", (285, 310)), ("nav", (390, 415)), ("market_value", (505, 550))]
CDSL_HEADERS = [
    ("units", (210, 265)),
    ("safekeep", (285, 345)),
    ("pledged", (370, 430)),
    ("nav", (435, 485)),
    ("market_value", (530, 555)),
]
MF_FOLIO_HEADERS = [
    ("folio", (155, 190)),
    ("units", (210, 235)),
    ("cost", (265, 305)),
    ("invested", (315, 360)),
    ("nav", (370, 420)),
    ("market_value", (425, 475)),
    ("gain", (485, 530)),
    ("annualized", (545, 590)),
]
BASE_PAGE_WIDTH = 595
BASE_PAGE_HEIGHT = 842
