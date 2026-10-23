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
Column detection for NSDL holdings tables, checked against anonymised table geometry taken from
real statements of both known templates (``tests/fixtures/nsdl``).

Each fixture holds the header words, a few data rows, the vertical rules drawn on the page (empty for
the 2024 template) and the values every row must yield. Values are checked twice: with the ruled grid
and from the header words alone, so both detection paths must agree.
"""

import json
from pathlib import Path

import pytest
from pymupdf import Rect

from cas2json.nsdl.layout import build_layout, field_for, is_data_row, is_header_line, required_fields
from cas2json.nsdl.processor import NSDLProcessor
from cas2json.types import WordData

FIXTURES = sorted((Path(__file__).parent.parent / "fixtures" / "nsdl").glob("*.json"))


def words(*texts: str) -> list[WordData]:
    return [(Rect(i * 20, 0, i * 20 + 15, 8), text) for i, text in enumerate(texts)]


def load(path: Path) -> dict:
    data = json.loads(path.read_text())
    data["header_words"] = [(Rect(*w[:4]), w[4]) for w in data["header"]]
    data["row_words"] = [[(Rect(*w[:4]), w[4]) for w in row["words"]] for row in data["rows"]]
    data["rules"] = [tuple(rule) for rule in data["vertical_rules"]]
    return data


@pytest.fixture(params=FIXTURES, ids=[path.stem for path in FIXTURES])
def table(request) -> dict:
    return load(request.param)


@pytest.mark.parametrize("use_rules", [True, False], ids=["ruled-grid", "header-only"])
def test_every_value_lands_in_its_field(table, use_rules):
    layout = build_layout(
        table["header_words"], table["row_words"], table["required"], table["rules"] if use_rules else ()
    )
    assert layout is not None, table["description"]
    assert set(table["required"]) <= layout.fields
    for row_words, row in zip(table["row_words"], table["rows"], strict=True):
        values, name = NSDLProcessor.identify_values_by_layout(row_words, layout, row["isin"])
        assert values == row["expected"], row["isin"]
        assert name == row["name"], row["isin"]


def test_ruled_grid_is_used_when_present(table):
    layout = build_layout(table["header_words"], table["row_words"], table["required"], table["rules"])
    assert layout is not None
    assert layout.source == ("grid" if table["rules"] else "header")


def test_layout_is_rejected_when_a_required_column_cannot_be_named(table):
    header = [(rect, text) for rect, text in table["header_words"] if text != "Value"]
    assert build_layout(header, table["row_words"], table["required"], ()) is None


def test_number_in_a_security_name_does_not_invalidate_the_layout():
    table = load(next(path for path in FIXTURES if path.stem == "2024_nsdl_stock"))
    first = table["row_words"][0]
    name_index = next(i for i, (_, text) in enumerate(first) if text.isalpha())
    first[name_index] = (first[name_index][0], "360")
    layout = build_layout(table["header_words"], table["row_words"], table["required"], ())
    assert layout is not None
    values, name = NSDLProcessor.identify_values_by_layout(first, layout, table["rows"][0]["isin"])
    assert values == table["rows"][0]["expected"]
    assert name.startswith("360 ")


@pytest.mark.parametrize(
    ("label", "field"),
    [
        ("Face Value in `", "cost"),
        ("Market Price in `", "nav"),
        ("Market Price / Face Value in `", "nav"),
        ("Value in `", "market_value"),
        ("No. of Shares", "units"),
        ("Current Bal. Free Bal. Lent Bal.", "units"),
        ("Safekeep Bal. Locked In Bal. Pledge Setup Bal.", "safekeep"),
        ("Pledged Bal. Earmarked Bal. Pledgee Bal.", "pledged"),
        ("Folio No.", "folio"),
        ("No. of Units", "units"),
        ("Average Cost Per Units `", "cost"),
        ("Total Cost `", "invested"),
        ("Current NAV per unit in `", "nav"),
        ("Current Value in `", "market_value"),
        ("Unrealised Profit/(Loss) `", "gain"),
        ("Annualised Return(%)", "annualized"),
        ("ISIN Stock Symbol", "symbol"),
        ("ISIN UCC", "symbol"),
        ("ISIN", "isin"),
        ("ISIN Description", "name"),
        ("Company Name", "name"),
        ("SECURITY", "name"),
        ("Type", None),
        ("", None),
    ],
)
def test_column_title_vocabulary(label, field):
    assert field_for(label) == field


def test_header_and_data_row_detection():
    assert is_header_line(words("ISIN", "SECURITY", "Current", "Bal."))
    assert is_header_line(words("Average", "Current", "Unrealised"))
    assert not is_header_line(words("Total", "1,234.00"))
    assert not is_header_line(words("Total"))
    assert is_header_line(words("`"), min_words=1)
    assert is_data_row(words("INE166C01025", "BELLARY", "STEELS"))
    assert not is_data_row(words("UNCLAIMDISIN", "SBIMF"))
    assert not is_data_row(words("Sub", "Total", "3,237.48"))


def test_required_fields_by_account_type():
    assert required_fields("MF") == {"folio", "units", "nav", "market_value"}
    assert required_fields("NSDL") == {"units", "nav", "market_value"}
    assert required_fields("CDSL") == {"units", "nav", "market_value"}
