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
End-to-end checks on real depository statements of every known template.

The statements are personal documents and are not part of the repository. Point these variables at
local copies to run the checks (a template whose variable is unset is skipped):

    CAS2JSON_NSDL_SAMPLE_<tag>    an NSDL statement (any tag, e.g. 2024, 2026, ECAS)
    CAS2JSON_CDSL_SAMPLE_<tag>    a CDSL statement
    <variable>_PASSWORD           the password of that statement, if any
"""

import os
import re
from collections import Counter

import pytest

from cas2json.cdsl import parse_cdsl_pdf
from cas2json.enums import SchemeType
from cas2json.nsdl import parse_nsdl_pdf
from cas2json.nsdl.processor import NSDLProcessor
from cas2json.types import DepositoryCASData

PARSERS = {"NSDL": parse_nsdl_pdf, "CDSL": parse_cdsl_pdf}
SAMPLES = {
    name.removeprefix("CAS2JSON_"): (path, os.environ.get(f"{name}_PASSWORD"))
    for name, path in sorted(os.environ.items())
    if re.fullmatch(r"CAS2JSON_(NSDL|CDSL)_SAMPLE_\w+", name) and not name.endswith("_PASSWORD") and path
}
AVAILABLE = [key for key, (path, _) in SAMPLES.items() if path]
SWALLOWED_VALUE = re.compile(r"\d[\d,]*\.\d{2}$")


@pytest.fixture(
    scope="module", params=AVAILABLE or [pytest.param(None, marks=pytest.mark.skip(reason="no sample set"))]
)
def statement(request) -> tuple[str, DepositoryCASData]:
    path, password = SAMPLES[request.param]
    depository = request.param.split("_")[0]
    return depository, PARSERS[depository](path, password)


def rows_of(data: DepositoryCASData, account):
    return [
        scheme
        for scheme in data.schemes
        if (scheme.dp_id or "") == (account.dp_id or "") and (scheme.client_id or "") == (account.client_id or "")
    ]


def test_holdings_values_reconcile_with_the_summary(statement):
    _, data = statement
    issues = NSDLProcessor.reconcile(data)
    assert [issue for issue in issues if "holdings value" in issue] == []


def test_scheme_counts_reconcile_with_the_summary(statement):
    depository, data = statement
    for account in data.accounts:
        parsed = len(rows_of(data, account))
        if depository == "NSDL" and account.ac_type == "MF":
            # NSDL lists unclaimed redemption amounts in the folio table under the pseudo ISIN
            # "UNCLAIMDISIN" and counts them in the summary; they are not parsed as holdings.
            assert account.schemes_count - 1 <= parsed <= account.schemes_count, account.name
        else:
            assert parsed == account.schemes_count, account.name


def test_every_row_has_units_and_value(statement):
    _, data = statement
    for scheme in data.schemes:
        assert scheme.units is not None, scheme.isin
        assert scheme.market_value is not None, scheme.isin


def test_folio_rows_carry_their_folio_number(statement):
    _, data = statement
    folio_rows = [scheme for scheme in data.schemes if not scheme.dp_id]
    assert folio_rows
    assert all(scheme.folio for scheme in folio_rows)


def test_nsdl_stock_rows_carry_face_value_and_price(statement):
    depository, data = statement
    if depository != "NSDL":
        pytest.skip("NSDL demat tables only")
    for account in (account for account in data.accounts if account.ac_type == "NSDL"):
        for scheme in rows_of(data, account):
            if scheme.scheme_type == SchemeType.STOCK:
                assert scheme.cost is not None, scheme.isin
                # A suspended ISIN prints "See Note" instead of a price and is valued at face value.
                assert scheme.nav is not None or scheme.market_value == scheme.cost * scheme.units, scheme.isin


def test_scheme_names_do_not_swallow_values(statement):
    _, data = statement
    assert [scheme.scheme_name for scheme in data.schemes if SWALLOWED_VALUE.search(scheme.scheme_name or "")] == []


def test_no_duplicate_holdings(statement):
    _, data = statement
    keys = Counter((scheme.dp_id, scheme.client_id, scheme.isin, scheme.folio) for scheme in data.schemes)
    assert [key for key, count in keys.items() if count > 1] == []
