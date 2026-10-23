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
Header-anchored column detection for NSDL CAS holdings tables.

NSDL re-flows its statement template from time to time and the table columns move by tens of
points. Fixed x-ranges (``cas2json.nsdl.constants``) then assign values to the wrong fields without
any error. This module derives the column cells of every table from the table itself:

1. from the ruled grid (vertical lines drawn around the cells) when the PDF has one,
2. otherwise from the positions of the header words, refined with the positions of the numeric
   values in the data rows (column titles may touch each other, right-aligned values never do).

Each cell is labelled with the header text inside it and the label is mapped to a scheme field
through a vocabulary (``Vocabulary``; the NSDL one is the default, CDSL supplies its own). Callers
fall back to the fixed ranges when no valid layout is found.

``band_rows`` groups the words of a table into rows, one per ISIN, from the horizontal rulings when
the table draws them and from the text geometry otherwise.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise

from pymupdf import Rect

from cas2json import patterns
from cas2json.types import WordData

VerticalRule = tuple[float, float, float]
"""A vertical line drawn on the page as ``(x, y0, y1)``."""
HorizontalRule = tuple[float, float, float]
"""A horizontal line drawn on the page as ``(y, x0, x1)``."""

ISIN_RE = re.compile(rf"^({patterns.ISIN})[^0-9A-Za-z]*$")
"""An ISIN, possibly followed by footnote markers such as ``@`` or ``$$`` that CDSL appends to it."""
NUMERIC_RE = re.compile(r"^[(-]*\d[\d,.]*\)*$")

# Every word that NSDL uses in the column titles of its holdings tables. A text line made only of
# these words is a (possibly wrapped) table header.
HEADER_TOKENS = frozenset(
    {
        "ISIN", "UCC", "SECURITY", "Stock", "Symbol", "Company", "Name", "Description",
        "Folio", "No.", "of", "Units", "Shares", "Average", "Cost", "Per", "Total",
        "Current", "NAV", "per", "unit", "Value", "in", "`", "Unrealised", "Profit/(Loss)",
        "Annualised", "Return(%)", "Face", "Market", "Price", "/", "Bal.", "Free", "Lent",
        "Safekeep", "Locked", "In", "Pledge", "Setup", "Pledged", "Earmarked", "Pledgee",
        "Coupon", "Rate/", "Frequency", "Maturity", "Date", "Bonds", "Bond",
    }
)  # fmt: skip

# Ordered (field, pattern) pairs matched against the lower-cased label of a column; the first match
# wins, so the order matters: "Market Price / Face Value" must become ``nav`` before "face value"
# can become ``cost``, and "ISIN Description" must become ``name`` before "isin" matches.
FIELD_PATTERNS: tuple[tuple[str, str], ...] = (
    ("folio", r"\bfolio\b"),
    ("frequency", r"coupon|frequency"),
    ("maturity", r"maturity"),
    ("units", r"no\.? ?of (units|shares|bonds)|current bal"),
    ("gain", r"unrealised"),
    ("annualized", r"annualised"),
    ("safekeep", r"safekeep"),
    ("pledged", r"pledged bal"),
    ("invested", r"total cost"),
    ("nav", r"market price|current nav|\bnav\b"),
    ("cost", r"face value|average|cost per"),
    ("market_value", r"\bvalue\b"),
    ("symbol", r"stock symbol|\bucc\b"),
    ("name", r"security|company name|isin description"),
    ("isin", r"^isin\b"),
)
NUMERIC_FIELDS = frozenset(
    {"folio", "units", "gain", "annualized", "safekeep", "pledged", "invested", "nav", "cost", "market_value"}
)
TEXT_FIELDS = frozenset({"symbol", "name", "isin", "frequency", "maturity"})

HEADER_GAP = 8.0
"""Header words closer than this (in points) belong to the same column title."""
RIGHT_EDGE_TOLERANCE = 6.0
"""Right-aligned values whose right edges differ by less than this sit in the same column."""
WORD_GAP = 6.0
"""Words further apart than this (in points) are not neighbours in one phrase; a text run starts there."""
RULE_MERGE_TOLERANCE = 2.0
"""Vertical rules closer than this are the same cell border."""
SPARSE_COLUMN_RATIO = 0.2
"""A value cluster with fewer values than this share of the fullest column is an outlier, not a column."""
TEXT_COLUMN_SLACK = 4.0
"""A text column ends this far (in points) after the right edge of its title and contents."""
LINE_TOLERANCE = 2.0
"""Words whose vertical centres differ by less than this sit on the same text line."""


@dataclass(slots=True, frozen=True)
class Vocabulary:
    """The column titles of one depository's tables and how they map to scheme fields."""

    tokens: frozenset[str]
    """Every word used in column titles; a text line made only of these words is a table header."""
    patterns: tuple[tuple[str, str], ...]
    """Ordered ``(field, regex)`` pairs matched against a lower-cased column label; first match wins."""
    numeric_fields: frozenset[str]
    text_fields: frozenset[str]


NSDL_VOCABULARY = Vocabulary(HEADER_TOKENS, FIELD_PATTERNS, NUMERIC_FIELDS, TEXT_FIELDS)


@dataclass(slots=True, frozen=True)
class Column:
    """One table column: the field it holds, its header text and its horizontal cell."""

    field: str | None
    label: str
    x0: float
    x1: float
    lo: float
    hi: float

    def contains(self, rect: Rect) -> bool:
        return self.lo <= (rect.x0 + rect.x1) / 2 < self.hi


@dataclass(slots=True, frozen=True)
class TableLayout:
    """Columns of one holdings table, derived from the table itself."""

    columns: tuple[Column, ...]
    source: str
    """``"grid"`` when taken from ruled lines, ``"header"`` when derived from header and data words."""

    def column_at(self, rect: Rect) -> Column | None:
        for column in self.columns:
            if column.contains(rect):
                return column
        return None

    @property
    def fields(self) -> frozenset[str]:
        return frozenset(column.field for column in self.columns if column.field)


def isin_of(text: str) -> str | None:
    """The ISIN in a table cell, without any footnote marker; ``None`` when the text is not an ISIN."""
    match = ISIN_RE.match(text)
    return match.group(1) if match else None


def field_for(label: str, vocabulary: Vocabulary = NSDL_VOCABULARY) -> str | None:
    """Map a column title to a scheme field, or ``None`` for an unknown title."""
    # The rupee sign is a separate glyph ("`") that may sit between the words of a title.
    normalized = re.sub(r"\s+", " ", label.replace("\xad", "").replace("`", " ")).strip().lower()
    if not normalized:
        return None
    for field, pattern in vocabulary.patterns:
        if re.search(pattern, normalized):
            return field
    return None


def is_header_line(
    word_rects: Sequence[WordData], min_words: int = 2, vocabulary: Vocabulary = NSDL_VOCABULARY
) -> bool:
    """True when the line is made only of column-title words."""
    return len(word_rects) >= min_words and all(text in vocabulary.tokens for _, text in word_rects)


def is_data_row(word_rects: Sequence[WordData]) -> bool:
    """True when the line starts with an ISIN, i.e. it is the first line of a holdings row."""
    return bool(word_rects) and ISIN_RE.match(word_rects[0][1]) is not None


def header_words(word_rects: Iterable[WordData], vocabulary: Vocabulary = NSDL_VOCABULARY) -> list[WordData]:
    """Keep only the column-title words of a line."""
    return [(rect, text) for rect, text in word_rects if text in vocabulary.tokens]


def text_lines(words: Iterable[WordData]) -> list[list[WordData]]:
    """Group words into text lines by their vertical centre; lines are sorted top to bottom, words left to right."""
    lines: list[tuple[float, list[WordData]]] = []
    for rect, text in sorted(words, key=lambda w: (w[0].y0 + w[0].y1) / 2):
        centre = (rect.y0 + rect.y1) / 2
        if lines and abs(centre - lines[-1][0]) <= LINE_TOLERANCE:
            lines[-1][1].append((rect, text))
        else:
            lines.append((centre, [(rect, text)]))
    return [sorted(line, key=lambda w: w[0].x0) for _, line in lines]


def _line_centre(line: Sequence[WordData]) -> float:
    return sum((rect.y0 + rect.y1) / 2 for rect, _ in line) / len(line)


def band_rows(
    words: Sequence[WordData],
    horizontal_rules: Sequence[HorizontalRule] = (),
    text_column: tuple[float, float] | None = None,
) -> list[list[WordData]]:
    """
    Group the words of a table into rows, one per ISIN.

    Rows are taken from the horizontal rulings when the table draws a border around every row.
    Otherwise the ISIN of a row is vertically centred in it, and the padding between rows is wider
    than the line pitch inside a wrapped name, so between two consecutive ISINs the row boundary is
    the widest gap among the lines of the text column; words of other columns join the nearest ISIN.

    Parameters
    ----------
    words : Sequence[WordData]
        All words of the table body (header words are harmless, they end up in no row).
    horizontal_rules : Sequence[HorizontalRule]
        Horizontal lines drawn on the page.
    text_column : tuple[float, float] | None
        Horizontal extent of the column whose cells wrap over several lines (the security name).
    """
    anchors = sorted((w for w in words if ISIN_RE.match(w[1])), key=lambda w: w[0].y0)
    if not anchors:
        return []
    centres = [(a[0].y0 + a[0].y1) / 2 for a in anchors]

    bands = _bands_from_rules(centres, horizontal_rules)
    if bands is not None:
        rows: list[list[WordData]] = [[] for _ in anchors]
        for word in words:
            centre = (word[0].y0 + word[0].y1) / 2
            for i, (lo, hi) in enumerate(bands):
                if lo <= centre < hi:
                    rows[i].append(word)
                    break
        return [sorted(row, key=lambda w: (round(w[0].y0), w[0].x0)) for row in rows]

    rows = [[] for _ in anchors]
    nearest = lambda y: min(range(len(centres)), key=lambda i: abs(centres[i] - y))  # noqa: E731
    in_text_column = lambda w: text_column is not None and text_column[0] <= (w[0].x0 + w[0].x1) / 2 < text_column[1]  # noqa: E731
    for word in words:
        if not in_text_column(word):
            rows[nearest((word[0].y0 + word[0].y1) / 2)].append(word)
    lines = text_lines(w for w in words if in_text_column(w))
    line_centres = [_line_centre(line) for line in lines]
    # Lines above the first ISIN belong to the first row, lines below the last ISIN to the last row;
    # between two ISINs, the widest gap of the sequence ISIN, lines..., ISIN separates the rows.
    row_of_line = [0] * len(lines)
    for i in range(len(centres) - 1):
        between = [k for k, y in enumerate(line_centres) if centres[i] < y < centres[i + 1]]
        sequence = [centres[i], *[line_centres[k] for k in between], centres[i + 1]]
        gaps = [b - a for a, b in pairwise(sequence)]
        split = max(range(len(gaps)), key=lambda g: gaps[g])  # lines before the split stay in row i
        for position, k in enumerate(between):
            row_of_line[k] = i if position < split else i + 1
        for k, y in enumerate(line_centres):
            if y >= centres[i + 1]:
                row_of_line[k] = i + 1
    for line, row in zip(lines, row_of_line, strict=True):
        rows[row].extend(line)
    return [sorted(row, key=lambda w: (round(w[0].y0), w[0].x0)) for row in rows]


def _bands_from_rules(centres: Sequence[float], rules: Sequence[HorizontalRule]) -> list[tuple[float, float]] | None:
    """Row bands from consecutive horizontal rulings, when exactly one ISIN lies between each pair."""
    ys: list[float] = []
    for y, _, _ in sorted(rules):
        if not ys or y - ys[-1] > RULE_MERGE_TOLERANCE:
            ys.append(y)
    bands = []
    for lo, hi in pairwise(ys):
        inside = [c for c in centres if lo <= c < hi]
        if len(inside) == 1:
            bands.append((lo, hi))
        elif len(inside) > 1:
            return None
    return bands if len(bands) == len(centres) else None


def required_fields(ac_type: str | None) -> frozenset[str]:
    """Fields a layout must label before it is trusted for the given account type."""
    if ac_type == "MF":
        return frozenset({"folio", "units", "nav", "market_value"})
    return frozenset({"units", "nav", "market_value"})


def build_layout(
    header: Sequence[WordData],
    rows: Sequence[Sequence[WordData]],
    required: Iterable[str],
    vertical_rules: Sequence[VerticalRule] = (),
    vocabulary: Vocabulary = NSDL_VOCABULARY,
) -> TableLayout | None:
    """
    Derive the column layout of a table.

    Parameters
    ----------
    header : Sequence[WordData]
        Words of the header lines (anything that is not a column-title word is ignored).
    rows : Sequence[Sequence[WordData]]
        Words of the data rows that follow the header (first word of each row is the ISIN).
    required : Iterable[str]
        Fields the layout must label to be accepted.
    vertical_rules : Sequence[VerticalRule]
        Vertical lines drawn on the page, used to read the cells of a ruled table.
    vocabulary : Vocabulary
        Column titles of the depository and their mapping to fields.

    Returns
    -------
    TableLayout | None
        The layout, or ``None`` when neither the grid nor the header words give a trustworthy one.
    """
    header = header_words(header, vocabulary)
    numeric = [(rect, text) for row in rows for rect, text in row if NUMERIC_RE.match(text)]
    required = frozenset(required)
    anchor = next((rect for row in rows for rect, text in row if ISIN_RE.match(text)), None)

    if anchor is not None and vertical_rules:
        layout = _layout_from_grid(header, vertical_rules, anchor, vocabulary)
        if layout and _is_valid(layout, required, numeric, len(rows), vocabulary):
            return layout
    if header:
        layout = _layout_from_header(header, numeric, vocabulary, rows)
        if layout and _is_valid(layout, required, numeric, len(rows), vocabulary):
            return layout
    return None


def _center(rect: Rect) -> float:
    return (rect.x0 + rect.x1) / 2


def _label(words: Iterable[WordData]) -> str:
    return " ".join(text for _, text in sorted(words, key=lambda w: (round(w[0].y0), w[0].x0)))


def _cells(extents: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Cell boundaries as midpoints between neighbouring extents; outer cells are open-ended."""
    cells = []
    for i, (x0, x1) in enumerate(extents):
        lo = float("-inf") if i == 0 else (extents[i - 1][1] + x0) / 2
        hi = float("inf") if i == len(extents) - 1 else (x1 + extents[i + 1][0]) / 2
        cells.append((lo, hi))
    return cells


def grid_cells(rules: Sequence[VerticalRule], anchor: Rect) -> list[tuple[float, float]]:
    """Horizontal cell extents of a ruled table, from the vertical rules that cross ``anchor``."""
    anchor_y = (anchor.y0 + anchor.y1) / 2
    xs: list[float] = []
    for x, y0, y1 in sorted(rules):
        if y0 - 1 <= anchor_y <= y1 + 1 and (not xs or x - xs[-1] > RULE_MERGE_TOLERANCE):
            xs.append(x)
    return list(pairwise(xs))


def _layout_from_grid(
    header: Sequence[WordData], rules: Sequence[VerticalRule], anchor: Rect, vocabulary: Vocabulary
) -> TableLayout | None:
    """Cells from the vertical rules that cross the first data row."""
    cells = grid_cells(rules, anchor)
    if len(cells) < 2:
        return None

    columns = []
    last = len(cells) - 1
    for i, (x0, x1) in enumerate(cells):
        label = _label(w for w in header if x0 <= _center(w[0]) < x1)
        lo = float("-inf") if i == 0 else x0
        hi = float("inf") if i == last else x1
        columns.append(Column(field_for(label, vocabulary), label, x0, x1, lo, hi))
    return TableLayout(tuple(columns), "grid")


def _cluster_header(header: Sequence[WordData]) -> list[list[WordData]]:
    """Group header words into column titles: words closer than HEADER_GAP share a title."""
    clusters: list[list[WordData]] = []
    right = float("-inf")
    for word in sorted(header, key=lambda w: w[0].x0):
        if clusters and word[0].x0 <= right + HEADER_GAP:
            clusters[-1].append(word)
            right = max(right, word[0].x1)
        else:
            clusters.append([word])
            right = word[0].x1
    return clusters


def _cluster_values(numeric: Sequence[WordData]) -> list[tuple[float, float]]:
    """
    Group numeric words by right edge (values are right-aligned) into column extents.

    Sparse clusters are dropped: a value that overflows its cell (an unformatted number such as
    ``21212347.99``) must not pass for a column of its own.
    """
    clusters: list[list[float]] = []  # [x0_min, x1_sum, count]
    for rect, _ in sorted(numeric, key=lambda w: w[0].x1):
        if clusters and abs(rect.x1 - clusters[-1][1] / clusters[-1][2]) <= RIGHT_EDGE_TOLERANCE:
            cluster = clusters[-1]
            cluster[0] = min(cluster[0], rect.x0)
            cluster[1] += rect.x1
            cluster[2] += 1
        else:
            clusters.append([rect.x0, rect.x1, 1])
    min_count = max(c[2] for c in clusters) * SPARSE_COLUMN_RATIO if clusters else 0
    extents = [(x0, x1_sum / count) for x0, x1_sum, count in clusters if count >= min_count]
    # Columns never overlap horizontally: an overlapping cluster is an overflowing value of its neighbour.
    merged: list[tuple[float, float]] = []
    for x0, x1 in sorted(extents):
        if merged and x0 < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], x1))
        else:
            merged.append((x0, x1))
    return merged


def _text_starts(rows: Sequence[Sequence[WordData]]) -> list[float]:
    """
    Left edges where text runs start in the rows (text cells are left-aligned), one per text column.

    A run starts at a word that is neither a value nor an ISIN and does not follow its neighbour
    closely. Only starts seen in at least half of the rows count, so a wide gap inside one name
    does not pass for a column.
    """
    starts: list[list[float]] = []  # [x0_sum, count]
    for row in rows:
        previous: Rect | None = None
        for rect, text in sorted(row, key=lambda w: w[0].x0):
            is_run_start = (
                not NUMERIC_RE.match(text)
                and not ISIN_RE.match(text)
                and (previous is None or rect.x0 - previous.x1 > WORD_GAP)
            )
            if is_run_start:
                for start in starts:
                    if abs(rect.x0 - start[0] / start[1]) <= RIGHT_EDGE_TOLERANCE:
                        start[0] += rect.x0
                        start[1] += 1
                        break
                else:
                    starts.append([rect.x0, 1])
            previous = rect
    return sorted(x0_sum / count for x0_sum, count in starts if count * 2 >= len(rows))


def _layout_from_header(
    header: Sequence[WordData],
    numeric: Sequence[WordData],
    vocabulary: Vocabulary,
    rows: Sequence[Sequence[WordData]] = (),
) -> TableLayout | None:
    """
    Cells from the header titles, split wherever the data shows two columns under one title.

    Titles may touch each other; values never do (they are right-aligned) and text runs start at
    distinct left edges, so both give reliable split points.
    """
    titles = _cluster_header(header)
    values = _cluster_values(numeric)
    starts = _text_starts(rows)
    extents = [(min(w[0].x0 for w in t), max(w[0].x1 for w in t)) for t in titles]

    refined: list[tuple[list[WordData], list[tuple[float, float]]]] = []
    for (lo, hi), words in zip(_cells(extents), titles, strict=True):
        inside = [v for v in values if lo <= (v[0] + v[1]) / 2 < hi]
        inside_starts = [x for x in starts if lo <= x < hi]
        splits = [(a[1] + b[0]) / 2 for a, b in pairwise(inside)] + [x - 2 for x in inside_starts[1:]]
        if not splits:
            refined.append((words, inside))
            continue
        splits.sort()
        parts: list[list[WordData]] = [[] for _ in range(len(splits) + 1)]
        for word in words:
            parts[sum(1 for s in splits if _center(word[0]) >= s)].append(word)
        for part in parts:
            part_lo = min((w[0].x0 for w in part), default=None)
            part_hi = max((w[0].x1 for w in part), default=None)
            part_values = [v for v in inside if part_lo is not None and part_lo - 1 <= (v[0] + v[1]) / 2 <= part_hi + 1]
            if part:
                refined.append((part, part_values))
        for value in inside:
            if not any(value in part_values for _, part_values in refined):
                refined.append(([], [value]))

    spans = []
    for words, inside in refined:
        x0 = min([w[0].x0 for w in words] + [v[0] for v in inside])
        x1 = max([w[0].x1 for w in words] + [v[1] for v in inside])
        spans.append((x0, x1, _label(words)))
    spans.sort(key=lambda s: s[0])
    fields = [field_for(label, vocabulary) for _, _, label in spans]
    cells = _cells([(s[0], s[1]) for s in spans])
    for i in range(1, len(spans)):
        # The name of a security starts right after the ISIN (or symbol) column, well before its
        # own, centred, "Company Name" title; other text columns keep the midpoint boundary.
        if fields[i - 1] in ("isin", "symbol") and fields[i] in vocabulary.text_fields:
            boundary = spans[i - 1][1] + TEXT_COLUMN_SLACK
            cells[i - 1] = (cells[i - 1][0], boundary)
            cells[i] = (boundary, cells[i][1])
    columns = tuple(
        Column(field, label, x0, x1, lo, hi)
        for (x0, x1, label), field, (lo, hi) in zip(spans, fields, cells, strict=True)
    )
    return TableLayout(columns, "header")


def _is_valid(
    layout: TableLayout,
    required: frozenset[str],
    numeric: Sequence[WordData],
    rows: int,
    vocabulary: Vocabulary = NSDL_VOCABULARY,
) -> bool:
    """
    A layout is trusted when it labels every required field exactly once and the values of the rows
    sit in value cells. Security names may contain a number ("360 ONE WAM"), so one stray number
    per row is tolerated.
    """
    numeric_columns = [c.field for c in layout.columns if c.field in vocabulary.numeric_fields]
    if len(numeric_columns) != len(set(numeric_columns)):
        return False
    if not required <= layout.fields:
        return False
    strays = 0
    for rect, _ in numeric:
        column = layout.column_at(rect)
        if column is not None and column.field in vocabulary.text_fields:
            strays += 1
    return strays <= max(1, rows)
