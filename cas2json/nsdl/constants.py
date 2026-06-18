# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025-2026 BeyondIRR <https://beyondirr.com/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from collections import defaultdict

from cas2json.types import SchemeType

SCHEME_MAP = defaultdict(
    lambda: SchemeType.OTHER,
    {
        "Equities (E)": SchemeType.STOCK,
        "Mutual Funds (M)": SchemeType.MUTUAL_FUND,
        "Corporate Bonds (C)": SchemeType.CORPORATE_BOND,
        "Alternate Investment Fund (A)": SchemeType.ALTERNATE_INVESTMENT_FUND,
        "Preference Shares (P)": SchemeType.PREFERENCE_SHARES,
        "Mutual Fund Folios (F)": SchemeType.MUTUAL_FUND,
    },
)
NSDL_STOCK_HEADERS = (
    ("cost", (230, 280)),
    ("units", (310, 355)),
    ("nav", (405, 440)),
    ("market_value", (505, 555)),
)
NSDL_MF_HEADERS = (("units", (280, 315)), ("nav", (385, 420)), ("market_value", (500, 555)))
CDSL_HEADERS = (
    ("units", (210, 265)),
    ("safekeep", (285, 345)),
    ("pledged", (370, 430)),
    ("nav", (435, 495)),
    ("market_value", (525, 580)),
)
MF_FOLIO_HEADERS_1 = (
    ("folio", (155, 190)),
    ("units", (205, 245)),
    ("cost", (260, 310)),
    ("invested", (315, 360)),
    ("nav", (370, 420)),
    ("market_value", (425, 475)),
    ("gain", (485, 530)),
    ("annualized", (545, 590)),
)
# For cases where annualized returns are not provided
MF_FOLIO_HEADERS_2 = (
    ("folio", (160, 200)),
    ("units", (230, 260)),
    ("cost", (280, 340)),
    ("invested", (350, 400)),
    ("nav", (410, 465)),
    ("market_value", (470, 525)),
    ("gain", (535, 585)),
)
CORPORATE_BOND_HEADERS = (
    ("frequency", (157, 213)),
    ("maturity", (225, 265)),
    ("units", (285, 320)),
    ("cost", (350, 410)),
    ("nav", (425, 480)),
    ("market_value", (515, 555)),
)
# Calculated wrt common NSDL document format
BASE_PAGE_WIDTH = 595
BASE_PAGE_HEIGHT = 842
