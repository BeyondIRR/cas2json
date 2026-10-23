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
Reading CDSL holdings tables cell by cell.

CDSL draws every holdings table as a ruled grid. The vertical rulings give the column cells and the
header text inside each cell names the field (``CDSL_VOCABULARY``). Rows are banded with
``cas2json.nsdl.layout.band_rows``: from the horizontal rulings of the demat tables, and from the
text geometry of the folio tables, which rule only their header. Each row then yields the ISIN,
the wrapped security or scheme name in reading order, the folio and the values of its cells.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from cas2json.cdsl.types import CDSLMFScheme
from cas2json.nsdl.layout import (
    ISIN_RE,
    LINE_TOLERANCE,
    HorizontalRule,
    TableLayout,
    VerticalRule,
    Vocabulary,
    band_rows,
    build_layout,
    grid_cells,
    isin_of,
    text_lines,
)
from cas2json.types import DepositoryScheme, SchemeType, WordData

EMPTY_VALUE = "--"
"""Placeholder CDSL prints for an empty balance."""

CDSL_VOCABULARY = Vocabulary(
    tokens=frozenset(
        {
            "ISIN",
            "Security",
            "Current",
            "Bal",
            "Frozen",
            "Pledge",
            "Setup",
            "Free",
            "Market",
            "Price",
            "/",
            "Face",
            "Value",
            "(`)",
            "Scheme",
            "Name",
            "Folio",
            "No.",
            "ARN",
            "Code",
            "Closing",
            "(Units)",
            "NAV",
            "Cumulative",
            "Amount",
            "Invested",
            "(in",
            "INR)",
            "Valuation",
            "Average",
            "Total",
            "Expense",
            "Ratio",
            "(TER)",
            "(In",
            "%",
            "Terms)",
            "Gross",
            "Commission",
            "Paid",
            "to",
            "Distributors",
            "absolute",
            "terms",
            "in",
            "Unrealised",
            "Profit/",
            "Loss",
            "Unreal\xad",
            "ised",
            "Unreali\xad",
            "sed",
            "Loss(%)",
            "(%)",
            "Profit/Loss",
            "Regular",
            "Direct",
        }
    ),
    patterns=(
        ("gain_pct", r"\(%\)|loss\(%"),
        ("gain", r"unrealised|unreal|profit"),
        ("expense_regular_pct", r"\bregular\b"),
        ("expense_direct_pct", r"\bdirect\b"),
        ("commission", r"commission"),
        ("invested", r"invested|cumulative"),
        ("units", r"current bal|closing bal|\(units\)"),
        ("frozen", r"frozen"),
        ("pledge_setup", r"setup"),
        ("pledged", r"pledge"),
        ("free", r"free bal"),
        ("nav", r"market price|face value|\bnav\b"),
        ("market_value", r"valuation|\bvalue\b"),
        ("folio", r"folio"),
        ("broker", r"\barn\b"),
        ("name", r"security|scheme name"),
        ("isin", r"^isin"),
    ),
    numeric_fields=frozenset(
        {
            "gain_pct",
            "gain",
            "expense_regular_pct",
            "expense_direct_pct",
            "commission",
            "invested",
            "units",
            "frozen",
            "pledge_setup",
            "pledged",
            "free",
            "nav",
            "market_value",
        }
    ),
    text_fields=frozenset({"folio", "broker", "name", "isin"}),
)

REQUIRED_FIELDS = {
    SchemeType.MUTUAL_FUND: frozenset({"folio", "units", "nav", "market_value"}),
    SchemeType.STOCK: frozenset({"units", "nav", "market_value"}),
    SchemeType.CORPORATE_BOND: frozenset({"units", "nav", "market_value"}),
}


def to_decimal(value: str | None) -> Decimal | None:
    """Decimal of a printed amount; ``None`` for an empty cell or placeholder."""
    if value is None:
        return None
    cleaned = value.replace(",", "").replace(" ", "").strip()
    if cleaned in ("", EMPTY_VALUE, "-", "N/A", "NA"):
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _centre_y(word: WordData) -> float:
    return (word[0].y0 + word[0].y1) / 2


HEADER_TOKEN_SHARE = 0.75
"""Share of a line's words that must be column-title words for the line to count as a header line."""
ROW_REACH = 4.0
"""Lines of a wrapped name lie within this many line heights of their ISIN."""


def split_header(
    words: Sequence[WordData], cells: Sequence[tuple[float, float]]
) -> tuple[list[WordData], list[WordData]]:
    """
    Separate the header words of a table from its body, dropping text that belongs to neither.

    Header lines lie above the first ISIN and are made of column-title words. The lines of a
    wrapped name above the first ISIN sit in one cell close to it. Anything else above the table
    (the page header of a page the table continues on) and anything far below its last row is
    discarded.
    """
    anchors = [w for w in words if ISIN_RE.match(w[1])]
    first, last = min(anchors, key=_centre_y), max(anchors, key=_centre_y)
    reach = ROW_REACH * (first[0].y1 - first[0].y0)
    first_y, last_y = _centre_y(first), _centre_y(last)

    def cell_of(word: WordData) -> int | None:
        centre = (word[0].x0 + word[0].x1) / 2
        return next((i for i, (x0, x1) in enumerate(cells) if x0 <= centre < x1), None)

    header: list[WordData] = []
    body: list[WordData] = []
    for line in text_lines(words):
        y = sum(_centre_y(w) for w in line) / len(line)
        if y >= first_y - LINE_TOLERANCE:
            if y <= last_y + reach:
                body.extend(line)
            continue
        titles = sum(1 for _, text in line if text in CDSL_VOCABULARY.tokens)
        touched = {cell_of(w) for w in line} - {None}
        if titles >= HEADER_TOKEN_SHARE * len(line):
            header.extend(line)
        elif len(touched) == 1 and first_y - y <= reach:
            body.extend(line)  # a line of the first row's wrapped name
    return header, body


def cell_text(words: Sequence[WordData]) -> str:
    """Text of one cell in reading order, with soft hyphens removed."""
    ordered = sorted(words, key=lambda w: (round(_centre_y(w)), w[0].x0))
    return re.sub(r"\xad\s*", "", " ".join(text for _, text in ordered)).strip()


def read_table(
    words: Sequence[WordData],
    scheme_type: SchemeType,
    vertical_rules: Sequence[VerticalRule],
    horizontal_rules: Sequence[HorizontalRule] = (),
) -> list[DepositoryScheme] | None:
    """
    Read every holdings row of a ruled CDSL table.

    Returns an empty list for a table without rows (a header repeated after a page break) and
    ``None`` when the table cannot be read cell by cell (no grid, or a header whose titles do not
    name the required fields), so the caller can fall back to text parsing.
    """
    required = REQUIRED_FIELDS.get(scheme_type)
    anchors = [w for w in words if ISIN_RE.match(w[1])]
    if not anchors:
        return []
    if required is None or not vertical_rules:
        return None
    cells = grid_cells(vertical_rules, min(anchors, key=_centre_y)[0])
    if len(cells) < 3:
        return None

    header, body = split_header(words, cells)
    layout = build_layout(header, band_rows(body, horizontal_rules), required, vertical_rules, CDSL_VOCABULARY)
    if layout is None:
        return None
    name_column = next((c for c in layout.columns if c.field == "name"), None)
    rows = band_rows(body, horizontal_rules, (name_column.x0, name_column.x1) if name_column else None)

    schemes = []
    for row in rows:
        scheme = _read_row(row, layout, scheme_type)
        if scheme is not None:
            schemes.append(scheme)
    return schemes


def _read_row(row: Sequence[WordData], layout: TableLayout, scheme_type: SchemeType) -> DepositoryScheme | None:
    isin = next((isin_of(text) for _, text in row if isin_of(text)), None)
    if isin is None:
        return None
    cells: dict[str, list[WordData]] = {}
    for word in row:
        column = layout.column_at(word[0])
        if column is not None and column.field is not None and isin_of(word[1]) is None:
            cells.setdefault(column.field, []).append(word)
    text = {field: cell_text(words) for field, words in cells.items()}
    units = text.get("units")
    common = {
        "isin": isin,
        "scheme_name": text.get("name") or None,
        # An empty current balance is a holding of zero units, not an unknown quantity.
        "units": Decimal(0) if units == EMPTY_VALUE else to_decimal(units),
        "nav": to_decimal(text.get("nav")),
        "market_value": to_decimal(text.get("market_value")),
        "invested_value": to_decimal(text.get("invested")),
        "scheme_type": scheme_type,
    }
    if scheme_type == SchemeType.MUTUAL_FUND:
        return CDSLMFScheme(
            **common,
            folio=text.get("folio", "").replace(" ", "") or None,
            # Distributor codes wrap at their hyphen ("ARN-" / "DIRECT"): a code has no spaces.
            broker=text.get("broker", "").replace(" ", "") or None,
            gain=to_decimal(text.get("gain")),
            gain_pct=to_decimal(text.get("gain_pct")),
            expense_regular_pct=to_decimal(text.get("expense_regular_pct")),
            expense_direct_pct=to_decimal(text.get("expense_direct_pct")),
            commission=to_decimal(text.get("commission")),
        )
    return DepositoryScheme(**common)
