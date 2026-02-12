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

import re
from collections import defaultdict
from collections.abc import Generator
from decimal import Decimal
from typing import Any

from cas2json import patterns
from cas2json.cdsl.types import CDSLMFScheme
from cas2json.cdsl.utils import resolve_scheme_type_from_heading
from cas2json.flags import MULTI_TEXT_FLAGS
from cas2json.nsdl.processor import NSDLProcessor
from cas2json.types import (
    DematAccount,
    DematOwner,
    DepositoryCASData,
    DepositoryScheme,
    DocumentData,
    SchemeType,
    WordData,
)
from cas2json.utils import format_values


class CDSLProcessor(NSDLProcessor):
    __slots__ = ()

    @staticmethod
    def _clean_decimal(val):
        if not val or val in ("--", "-", "."):
            return None
        return Decimal(val.replace(",", ""))

    @staticmethod
    def extract_dp_client_id(line: str) -> tuple[str | Any, ...] | None:
        """
        Extract DP ID and Client ID from the line if present.

        Supported line formats
        ----------------------
        - "DP ID:12345678 Client ID:12345678"
        - "BO ID:1234567812345678"
        """
        if dp_client_match := re.search(patterns.DP_CLIENT_ID, line, MULTI_TEXT_FLAGS):
            return dp_client_match.groups()
        if bo_match := re.search(patterns.BO_ID, line, MULTI_TEXT_FLAGS):
            bo_id = bo_match.group(1).replace(" ", "").replace("-", "")
            if len(bo_id) == 16:
                dp_id = bo_id[:8]
                client_id = bo_id[8:]
                return (dp_id, client_id)
        if dp_id_match := re.search(patterns.CDSL_DP_ID_FOR_NSDL, line, MULTI_TEXT_FLAGS):
            return dp_id_match.groups()
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
        cleaned_line = re.sub(r"(Account)\s+[A-Z]+\s+(?=\d)", r"\1 ", line)
        if demat_match := re.search(patterns.DEMAT, cleaned_line, MULTI_TEXT_FLAGS):
            ac_type, schemes_count, ac_balance = demat_match.groups()
            schemes_count, ac_balance = format_values((schemes_count, ac_balance))
            return ac_type, int(schemes_count or 0), ac_balance
        return None

    @staticmethod
    def extract_cdsl_scheme(line: str, scheme_type: SchemeType) -> DepositoryScheme | None:
        words = line.split()
        # Find ISIN position
        if scheme_type == SchemeType.MUTUAL_FUND:
            scheme_match = re.search(patterns.CDSL_MF_SCHEME, line, MULTI_TEXT_FLAGS)
            if not scheme_match:
                return None
            folio = broker = None
            if len(scheme_match.groups()) == 2:
                isin, values = scheme_match.groups()
            elif len(scheme_match.groups()) == 3:
                isin, folio, values = scheme_match.groups()
            else:
                isin, folio, broker, values, *_ = scheme_match.groups()
            values = values.split()
            units = nav = invested_value = market_value = gain = gain_pct = exp_regular = exp_direct = commission = None
            if len(values) == 6:
                units, nav, invested_value, market_value, gain, gain_pct = values
            elif len(values) == 9:
                units, nav, invested_value, market_value, exp_regular, exp_direct, commission, gain, gain_pct = values
            return CDSLMFScheme(
                isin=isin,
                folio=folio,
                units=CDSLProcessor._clean_decimal(units),
                nav=CDSLProcessor._clean_decimal(nav),
                invested_value=CDSLProcessor._clean_decimal(invested_value),
                market_value=CDSLProcessor._clean_decimal(market_value),
                scheme_type=scheme_type,
                broker=broker,
                gain=CDSLProcessor._clean_decimal(gain),
                gain_pct=CDSLProcessor._clean_decimal(gain_pct),
                expense_regular_pct=CDSLProcessor._clean_decimal(exp_regular),
                expense_direct_pct=CDSLProcessor._clean_decimal(exp_direct),
                commission=CDSLProcessor._clean_decimal(commission),
            )
        elif scheme_type in [SchemeType.STOCK, SchemeType.CORPORATE_BOND]:
            # Find first decimal number after ISIN
            try:
                isin_index = next(i for i, word in enumerate(words) if re.match(patterns.ISIN, word))
            except StopIteration:
                return None
            try:
                first_decimal_index = next(
                    i for i in range(isin_index + 1, len(words)) if re.search(r"\d+\.\d+", words[i].replace(",", ""))
                )
            except StopIteration:
                return None
            # Keep ISIN + decimals onwards
            words = [words[isin_index], *words[first_decimal_index:]]
            if (len(words) < 5 and scheme_type == SchemeType.STOCK) or (
                len(words) < 7 and scheme_type == SchemeType.CORPORATE_BOND
            ):
                return None
            if scheme_type == SchemeType.STOCK:
                isin, units, _, _, _, _, nav, market_value = words[:8]
            else:
                isin = words[0]
                units, face_value, nav, market_value = words[-4:]
            scheme = DepositoryScheme(
                isin=isin,
                units=CDSLProcessor._clean_decimal(units),
                nav=CDSLProcessor._clean_decimal(nav),
                market_value=CDSLProcessor._clean_decimal(market_value),
                scheme_type=scheme_type,
            )
            if scheme_type == SchemeType.CORPORATE_BOND:
                scheme.invested_value = Decimal(face_value.replace(",", "")) * Decimal(units.replace(",", ""))
            return scheme
        return None

    @staticmethod
    def extract_nsdl_scheme(line: str, scheme_type: SchemeType) -> DepositoryScheme | None:
        words = line.split()
        try:
            isin_index = next(i for i, word in enumerate(words) if re.match(patterns.ISIN, word))
        except StopIteration:
            return None
        if scheme_type == SchemeType.STOCK:
            try:
                first_decimal_index = next(
                    i for i in range(isin_index + 1, len(words)) if words[i].replace(",", "").replace(".", "").isdigit()
                )
            except StopIteration:
                return None
            words = [words[isin_index], *words[first_decimal_index:]]
            if len(words) < 4:
                return None
            isin, _, nav, market_value = words[:4]
            nav = CDSLProcessor._clean_decimal(nav)
            market_value = CDSLProcessor._clean_decimal(market_value)
            units = market_value / nav
            return DepositoryScheme(
                isin=isin,
                units=str(units),
                nav=nav,
                market_value=market_value,
                scheme_type=scheme_type,
            )
        return None

    @staticmethod
    def extract_scheme_details(line: str, scheme_type: SchemeType, ac_type: str | None) -> DepositoryScheme | None:
        if ac_type in ["CDSL", "MF"]:
            return CDSLProcessor.extract_cdsl_scheme(line, scheme_type)
        elif ac_type == "NSDL":
            return CDSLProcessor.extract_nsdl_scheme(line, scheme_type)
        return None

    @staticmethod
    def recover_table_lines(words: list[WordData], tolerance: int = 4) -> Generator[str]:
        lrects = [words[0][0]]
        line_words = [[words[0]]]
        for wr, text in words[1:]:
            if abs(wr.x1 - wr.x0) * 5 < abs(wr.y1 - wr.y0):
                continue
            for idx, lrect in enumerate(lrects):
                if (
                    abs(lrect.y0 - wr.y0) <= tolerance
                    or abs(lrect.y1 - wr.y1) <= tolerance
                    or abs(lrect.y1 - wr.y0) <= tolerance
                    or abs(lrect.y0 - wr.y1) <= tolerance
                ):
                    line_words[idx].append((wr, text))
                    lrects[idx] |= wr
                    break
            else:
                line_words.append([(wr, text)])
                lrects.append(wr)
        for line in line_words:
            word_pos = sorted(line, key=lambda w: w[0].x0)
            ltext = " ".join(w[1] for w in word_pos)
            ltext = re.sub(r"\xad\s*", "", ltext)
            yield ltext

    def process_statement(self, document_data: DocumentData) -> DepositoryCASData:
        """
        Process the text version of a CDSL/NSDL pdf and return the processed data.
        """
        current_demat: DematAccount | None = None
        schemes: list[DepositoryScheme] = []
        scheme_type: SchemeType = SchemeType.OTHER
        holders: list[DematOwner] = []
        demats: dict[str, DematAccount] = {}
        process_demats: bool = True
        process_table: bool = False
        table_data = defaultdict(list)
        page = 0

        for page_data in document_data:
            page_lines_data = list(page_data.lines_data)
            page += 1
            for idx, (line, _words_rect) in enumerate(page_lines_data):
                # Do not parse transactions
                if "STATEMENT OF TRANSACTIONS" in line or "Other Details" in line:
                    process_table = False

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

                if "consolidated portfolio valuation for year" in line.lower():
                    process_demats = False
                    continue

                if "MUTUAL FUND UNITS HELD WITH" in line:
                    current_demat = demats.get("MF Folios")
                    process_table = True
                    continue

                if dp_client_ids := self.extract_dp_client_id(line):
                    current_demat = demats.get(dp_client_ids[0] + dp_client_ids[1])

                if current_demat is None:
                    continue

                elif (resolved := resolve_scheme_type_from_heading(line)) is not None:
                    scheme_type = resolved
                    process_table = True
                    continue

                if process_table and ("portfolio value" in line.lower() or "grand total" in line.lower()):
                    process_table = False

                elif process_table:
                    key = (current_demat.ac_type, scheme_type, current_demat.dp_id, current_demat.client_id, page)
                    table_data[key].extend(_words_rect)

        for (ac_type, scheme_type, dp_id, client_id, _), words_rect in table_data.items():
            for line in self.recover_table_lines(words_rect):
                if scheme := self.extract_scheme_details(line, scheme_type, ac_type):
                    scheme.dp_id = dp_id
                    scheme.client_id = client_id
                    schemes.append(scheme)

        return DepositoryCASData(accounts=list(demats.values()), schemes=schemes)
