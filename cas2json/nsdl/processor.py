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

import re
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from cas2json import patterns
from cas2json.flags import MULTI_TEXT_FLAGS
from cas2json.nsdl.constants import (
    BASE_PAGE_WIDTH,
    CDSL_HEADERS,
    CORPORATE_BOND_HEADERS,
    MF_FOLIO_HEADERS_1,
    MF_FOLIO_HEADERS_2,
    NSDL_MF_HEADERS,
    NSDL_STOCK_HEADERS,
    SCHEME_MAP,
)
from cas2json.types import (
    DematAccount,
    DematOwner,
    DepositoryCASData,
    DepositoryScheme,
    DocumentData,
    SchemeType,
    WordData,
)
from cas2json.utils import format_values, formatINR


class NSDLProcessor:
    __slots__ = ()

    @staticmethod
    def identify_values(
        word_rects: list[WordData],
        headers: Sequence[tuple[str, tuple[int, int]]],
        isin: str,
        width_scale: float = 1.0,
        value_tolerance: tuple[float, float] = (5, 5),
    ) -> tuple[dict[str, str | None], str]:
        """
        Identify values by matching word positions against known header columns.
        Returns the holding dict and the derived scheme name.
        """
        left_tol, right_tol = value_tolerance
        holding: dict[str, str | None] = {}
        name_words: list[str] = []
        for rect, word in word_rects:
            if word == isin:
                continue
            matched = False
            if re.match(r"^[(-]*\d[\d,.]*\)*$", word):
                for header_name, (h_left, h_right) in headers:
                    if rect.x0 >= (h_left * width_scale) - left_tol and rect.x1 <= (h_right * width_scale) + right_tol:
                        holding[header_name] = word
                        matched = True
                        break
            if not matched:
                name_words.append(word)

        name = " ".join(name_words)
        return holding, name

    @staticmethod
    def identify_mf_folio_headers(line: str) -> tuple[tuple[str, tuple[int, int]], ...] | None:
        """
        Identify the MF folio table layout from its header line.

        NSDL MF folio tables can omit the Annualised Return column. Rows in a full table can also have
        blank values, so the layout must be detected from table headers instead of row value count.
        """
        normalized_line = re.sub(r"\s+", " ", line).strip().lower()
        if "annualised" in normalized_line:
            return MF_FOLIO_HEADERS_1
        if (
            "folio no." in normalized_line
            and "no. of" in normalized_line
            and ("current value" in normalized_line or "current nav" in normalized_line)
            and ("unrealised" in normalized_line)
        ):
            return MF_FOLIO_HEADERS_2
        return None

    @staticmethod
    def extract_holders(line: str) -> DematOwner | None:
        """
        Extract holder details from the line if present.

        Supported line formats
        ----------------------
        - "DEEPESH BHARGAVA (PAN:ALXXXXXX3E)"
        """
        if holder_match := re.search(patterns.DEMAT_HOLDER, line, MULTI_TEXT_FLAGS):
            name, pan = holder_match.groups()
            return DematOwner(name=name.strip(), pan=pan.strip())
        return None

    @staticmethod
    def extract_dp_client_id(line: str) -> tuple[str | Any, ...] | None:
        """
        Extract DP ID and Client ID from the line if present.

        Supported line formats
        ----------------------
        - "DP ID:12345678 Client ID:12345678"
        """
        if dp_client_match := re.search(patterns.DP_CLIENT_ID, line, MULTI_TEXT_FLAGS):
            return dp_client_match.groups()
        return None

    @staticmethod
    def extract_nsdl_cdsl_demat(line: str) -> tuple[str | None, int, Decimal | None] | None:
        """
        Extract NSDL or CDSL demat account details from the line if present.

        Supported line formats
        ----------------------
        - "NSDL Demat Account 1 1,234.50"   (1 is number of schemes and 1,234.50 is market value)
        - "CDSL Demat Account 2 1,234.50"   (2 is number of schemes and 1,234.50 is market value)
        """
        if demat_match := re.search(patterns.DEMAT, line, MULTI_TEXT_FLAGS):
            ac_type, schemes_count, ac_balance = demat_match.groups()
            schemes_count, ac_balance = format_values((schemes_count, ac_balance))
            return ac_type, int(schemes_count or 0), ac_balance
        return None

    @staticmethod
    def extract_mf_demat(line: str) -> tuple[int, int, Decimal | None] | None:
        """
        Extract Mutual Fund demat account details from the line if present.

        Supported line formats
        ----------------------
        - "Mutual Fund Folios 10 Folios 10 1234.38"   (10 is number of folios, 10 is number of schemes and 1,234.38 is market value)
        """
        if demat_mf_match := re.search(patterns.DEMAT_MF_HEADER, line, MULTI_TEXT_FLAGS):
            folios, schemes_count, ac_balance = format_values(demat_mf_match.groups())
            return int(folios or 0), int(schemes_count or 0), ac_balance
        return None

    @staticmethod
    def extract_scheme_details(
        line: str,
        word_rects: list[WordData],
        scheme_type: SchemeType,
        ac_type: str | None,
        page_width: float,
        mf_folio_headers: tuple[tuple[str, tuple[int, int]], ...] = MF_FOLIO_HEADERS_1,
    ) -> DepositoryScheme | None:
        """
        Extract Scheme details for NSDL demat account from the line if present.

        Supported line formats
        ----------------------
        - "INE758E01017 JIO FINANCIAL SERVICES 5 311.70 1,558.50" (NSDL MFs)
        - "INE758E01017 JIO FINANCIAL SERVICES 10.00 5 311.70 1,558.50" (NSDL Stocks)
        - "INE883F01010 AADHAR HOUSING FINANCE 0.000 0.000 0.000 502.75 0.00" (CDSL)
        - "INF179KC1BM8 ICICI Prudential 123456 1234.793 12.3891 12345.00 12.6220 12345.39 1,354.39 5.42" (MF Folios)

        Order of details (in above):

        - ISIN, Scheme Name (incomplete), Units, NAV, Market Value (NSDL MFs)
        - ISIN, Scheme Name (incomplete), Cost per Unit, Units, NAV, Market Value (NSDL Stocks)
        - ISIN, Scheme Name (incomplete), Units, SafeKeep Balance, Pledged Balance, NAV, Market Value (CDSL)
        - ISIN, Scheme Name (incomplete), Folio, Units, Cost Per Unit, Total Cost, NAV, Market Value, Unrealized Profit/Loss, Annualised Return (MF Folios)
        """
        if scheme_match := re.search(patterns.SCHEME_DESCRIPTION, line, MULTI_TEXT_FLAGS):
            isin = scheme_match.group(1)
            width_scale = page_width / BASE_PAGE_WIDTH
            match ac_type:
                case "NSDL" if scheme_type in (SchemeType.MUTUAL_FUND, SchemeType.ALTERNATE_INVESTMENT_FUND):
                    headers = NSDL_MF_HEADERS
                    value_tolerance = (5, 5)
                case "NSDL" if scheme_type == SchemeType.STOCK:
                    headers = NSDL_STOCK_HEADERS
                    value_tolerance = (5, 5)
                case "NSDL" if scheme_type == SchemeType.CORPORATE_BOND:
                    headers = CORPORATE_BOND_HEADERS
                    value_tolerance = (5, 5)
                case "CDSL":
                    headers = CDSL_HEADERS
                    value_tolerance = (5, 5)
                case "MF":
                    headers = mf_folio_headers
                    value_tolerance = (10, 10)
                case _:
                    return None

            details, name = NSDLProcessor.identify_values(word_rects, headers, isin, width_scale, value_tolerance)

            price, units = format_values((details.get("cost"), details.get("units")))
            invested_value = formatINR(details.get("invested")) or (price * units if price and units else None)
            # TODO: name are mostly split into lines but there are cases of page breaks and thus there
            # will be lots of validations and checks to do to parse correct name
            name = re.sub(r"\s+", " ", name or "").strip()
            return DepositoryScheme(
                isin=isin,
                scheme_name=name,
                units=units,
                cost=price,
                nav=formatINR(details.get("nav")),
                market_value=formatINR(details.get("market_value")),
                invested_value=invested_value,
                scheme_type=scheme_type,
                folio=details.get("folio"),
            )
        return None

    def process_statement(self, document_data: DocumentData) -> DepositoryCASData:
        """
        Process the text version of a NSDL pdf and return the processed data.
        """
        current_demat: DematAccount | None = None
        schemes: list[DepositoryScheme] = []
        scheme_type: SchemeType = SchemeType.OTHER
        holders: list[DematOwner] = []
        demats: dict[str, DematAccount] = {}
        process_demats: bool = True
        mf_folio_headers = MF_FOLIO_HEADERS_1
        for page_data in document_data:
            page_lines_data = list(page_data.lines_data)
            for idx, (line, words_rect) in enumerate(page_lines_data):
                # Do not parse transactions
                if "Summary of Transaction" in line:
                    break

                if process_demats:
                    if holder := self.extract_holders(line):
                        if current_demat:
                            holders = []
                            current_demat = None
                        holders.append(holder)
                        continue

                    if demat_details := self.extract_nsdl_cdsl_demat(line):
                        ac_type, schemes_count, ac_balance = demat_details
                        dp_id, client_id = "", ""
                        if dp_details := self.extract_dp_client_id(
                            page_lines_data[idx + 1][0] if idx + 1 < len(page_lines_data) else ""
                        ):
                            dp_id, client_id = dp_details
                        current_demat = DematAccount(
                            name=page_lines_data[idx - 1][0].strip(),
                            ac_type=ac_type,
                            units=ac_balance,
                            dp_id=dp_id,
                            client_id=client_id,
                            schemes_count=schemes_count,
                            holders=holders,
                        )
                        demats[dp_id + client_id] = current_demat
                        continue

                    if mf_demat_details := self.extract_mf_demat(line):
                        folios, schemes_count, ac_balance = mf_demat_details
                        if "MF Folios" not in demats:
                            current_demat = DematAccount(
                                name="Mutual Fund Folios",
                                ac_type="MF",
                                units=ac_balance,
                                folios=folios,
                                schemes_count=schemes_count,
                            )
                            demats["MF Folios"] = current_demat
                        else:
                            current_demat = demats["MF Folios"]
                            current_demat.folios += folios or 0
                            current_demat.schemes_count += schemes_count
                            current_demat.units = (current_demat.units or Decimal(0)) + (ac_balance or Decimal(0))
                        continue

                if "portfolio value trend" in line.lower():
                    process_demats = False
                    current_demat = None
                    continue

                if "NSDL Demat Account" in line or "CDSL Demat Account" in line:
                    current_demat = None

                elif "Mutual Fund Folios (F)" in line:
                    current_demat = demats.get("MF Folios")

                elif dp_client_ids := self.extract_dp_client_id(line):
                    current_demat = demats.get(dp_client_ids[0] + dp_client_ids[1])

                if current_demat is None:
                    continue

                if (
                    current_demat.ac_type == "MF"
                    and not process_demats
                    and (headers := self.identify_mf_folio_headers(line))
                ):
                    mf_folio_headers = headers or mf_folio_headers

                if any(i in line for i in SCHEME_MAP):
                    scheme_type = SCHEME_MAP[line.strip()]

                elif scheme := (
                    self.extract_scheme_details(
                        line, words_rect, scheme_type, current_demat.ac_type, page_data.width, mf_folio_headers
                    )
                ):
                    scheme.dp_id = current_demat.dp_id
                    scheme.client_id = current_demat.client_id
                    schemes.append(scheme)

        return DepositoryCASData(accounts=list(demats.values()), schemes=schemes)
