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

"""
Row extraction from CDSL holdings tables, on the text lines the processor reconstructs.

The lines below mirror both known templates: the 2025 folio table carries ARN, expense-ratio and
commission columns (nine values), the 2026 one does not (six values). Demat rows print "--" for an
empty balance, including every balance of a holding that was transferred out.
"""

from decimal import Decimal

import pytest

from cas2json.cdsl.processor import CDSLProcessor
from cas2json.enums import SchemeType


def test_demat_row_with_balances():
    line = "ALPHA SHARES BRAVO LIMITED - EQUITY"  # the wrapped security name is a separate line
    assert CDSLProcessor.extract_cdsl_scheme(line, SchemeType.STOCK) is None
    scheme = CDSLProcessor.extract_cdsl_scheme(
        "INE000000101 160.000 -- -- -- 160.000 91.420 14,627.20", SchemeType.STOCK
    )
    assert scheme is not None
    assert (scheme.units, scheme.nav, scheme.market_value) == (
        Decimal("160.000"),
        Decimal("91.420"),
        Decimal("14627.20"),
    )


def test_demat_row_transferred_out_keeps_zero_units():
    scheme = CDSLProcessor.extract_cdsl_scheme("INE000000101 -- -- -- -- -- 239.0000 0.00", SchemeType.STOCK)
    assert scheme is not None
    assert scheme.units == Decimal(0)
    assert scheme.nav == Decimal("239.0000")
    assert scheme.market_value == Decimal("0.00")


def test_demat_row_with_too_few_values_is_ignored():
    assert CDSLProcessor.extract_cdsl_scheme("INE000000101 239.0000 0.00", SchemeType.STOCK) is None


def test_bond_row_with_and_without_balances():
    line = "INE000000101 BRAVO NCD 9.45% 2027 10.000 -- -- -- 10.000 1,000.00 1,012.50 10,125.00"
    scheme = CDSLProcessor.extract_cdsl_scheme(line, SchemeType.CORPORATE_BOND)
    assert scheme is not None
    assert (scheme.units, scheme.nav, scheme.market_value) == (
        Decimal("10.000"),
        Decimal("1012.50"),
        Decimal("10125.00"),
    )
    assert scheme.invested_value == Decimal("10000.000")
    empty = CDSLProcessor.extract_cdsl_scheme(
        "INE000000101 BRAVO NCD -- -- -- -- -- -- 1,012.50 0.00", SchemeType.CORPORATE_BOND
    )
    assert empty is not None
    assert empty.units == Decimal(0)
    assert empty.invested_value is None


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            # 2025 template: folio, distributor code, then nine values
            "ALPHA BRAVO - Direct INE000000101 91015676301/0 DIRECT 19140.18 12.8918 2,00,000.00 2,46,751.37 0 .09 0 46,751.37 23.38",
            {"folio": "91015676301/0", "broker": "DIRECT", "units": "19140.18", "nav": "12.8918", "invested_value": "200000.00",
             "market_value": "246751.37", "expense_regular_pct": "0", "expense_direct_pct": ".09", "commission": "0",
             "gain": "46751.37", "gain_pct": "23.38"},
        ),
        (
            # 2026 template: folio, then six values
            "ALPHA BRAVO - Direct INE000000101 8101201945/0 91752.842 11.1281 10,00,000.00 10,21,034.80 21,034.80 2.10",
            {"folio": "8101201945/0", "broker": None, "units": "91752.842", "nav": "11.1281", "invested_value": "1000000.00",
             "market_value": "1021034.80", "expense_regular_pct": None, "expense_direct_pct": None, "commission": None,
             "gain": "21034.80", "gain_pct": "2.10"},
        ),
        (
            # folio without a sub-folio suffix
            "ALPHA INE000000101 10580108 697.579 90.7827 30,000.00 63,328.11 33,328.11 111.09",
            {"folio": "10580108", "broker": None, "units": "697.579", "nav": "90.7827", "invested_value": "30000.00",
             "market_value": "63328.11", "expense_regular_pct": None, "expense_direct_pct": None, "commission": None,
             "gain": "33328.11", "gain_pct": "111.09"},
        ),
    ],
)  # fmt: skip
def test_folio_rows_of_both_templates(line, expected):
    scheme = CDSLProcessor.extract_cdsl_scheme(line, SchemeType.MUTUAL_FUND)
    assert scheme is not None
    for field, value in expected.items():
        got = getattr(scheme, field)
        assert got == (Decimal(value) if value is not None and field not in ("folio", "broker") else value), field
