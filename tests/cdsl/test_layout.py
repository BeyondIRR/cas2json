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
Cell-by-cell reading of CDSL holdings tables, checked against anonymised table geometry taken from
real statements of both known templates (``tests/fixtures/cdsl``).

Each fixture holds every word of one table (header and body), the rulings drawn around it and the
rows it must yield: ISIN, the wrapped name in reading order, folio, distributor code and values.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pymupdf import Rect

from cas2json.cdsl.layout import CDSL_VOCABULARY, read_table
from cas2json.enums import SchemeType
from cas2json.nsdl.layout import field_for

FIXTURES = sorted((Path(__file__).parent.parent / "fixtures" / "cdsl").glob("*.json"))


def load(path: Path) -> dict:
    data = json.loads(path.read_text())
    data["word_rects"] = [(Rect(*w[:4]), w[4]) for w in data["words"]]
    data["vertical"] = [tuple(r) for r in data["vertical_rules"]]
    data["horizontal"] = [tuple(r) for r in data["horizontal_rules"]]
    return data


def as_comparable(value):
    return str(value) if isinstance(value, Decimal) else value


@pytest.fixture(params=FIXTURES, ids=[path.stem for path in FIXTURES])
def table(request) -> dict:
    return load(request.param)


def test_every_row_is_read_with_its_name_and_values(table):
    schemes = read_table(table["word_rects"], SchemeType[table["scheme_type"]], table["vertical"], table["horizontal"])
    assert schemes is not None, table["description"]
    assert len(schemes) == len(table["expected"])
    for scheme, expected in zip(schemes, table["expected"], strict=True):
        got = {field: as_comparable(getattr(scheme, field)) for field in expected}
        assert got == expected, scheme.isin


def test_rows_band_without_horizontal_rulings(table):
    """Demat rows are ruled; folio rows are not. Both must read the same from the text geometry alone."""
    with_rules = read_table(
        table["word_rects"], SchemeType[table["scheme_type"]], table["vertical"], table["horizontal"]
    )
    without = read_table(table["word_rects"], SchemeType[table["scheme_type"]], table["vertical"], ())
    assert [s.scheme_name for s in without] == [s.scheme_name for s in with_rules]
    assert [s.units for s in without] == [s.units for s in with_rules]


def test_table_without_grid_falls_back(table):
    assert read_table(table["word_rects"], SchemeType[table["scheme_type"]], (), table["horizontal"]) is None


def test_table_without_rows_is_empty(table):
    header_only = [
        w
        for w in table["word_rects"]
        if w[0].y0 < min(r.y0 for r, t in table["word_rects"] if t.startswith("INE")) - 20
    ]
    assert read_table(header_only, SchemeType[table["scheme_type"]], table["vertical"], table["horizontal"]) == []


@pytest.mark.parametrize(
    ("label", "field"),
    [
        ("ISIN", "isin"),
        ("Security", "name"),
        ("Scheme Name", "name"),
        ("Current Bal", "units"),
        ("Closing Bal (Units)", "units"),
        ("Frozen Bal", "frozen"),
        ("Pledge Bal", "pledged"),
        ("Pledge Setup Bal", "pledge_setup"),
        ("Free Bal", "free"),
        ("Market Price / Face Value", "nav"),
        ("NAV (`)", "nav"),
        ("Value (`)", "market_value"),
        ("Valuation (`)", "market_value"),
        ("Folio No.", "folio"),
        ("ARN Code", "broker"),
        ("Cumulative Amount Invested (in INR)", "invested"),
        ("Average Expense (TER) (In Regular", "expense_regular_pct"),
        ("Total Ratio % Terms) Direct", "expense_direct_pct"),
        ("Gross Commission Paid to Distributors (in absolute terms - in INR)", "commission"),
        ("Unrealised Profit/ Loss", "gain"),
        ("Unreal\xad ised Profit/ Loss (%)", "gain_pct"),
        ("Unreali\xad sed Profit/ Loss(%)", "gain_pct"),
        ("Transaction Particulars", None),
    ],
)
def test_column_title_vocabulary(label, field):
    assert field_for(label, CDSL_VOCABULARY) == field
