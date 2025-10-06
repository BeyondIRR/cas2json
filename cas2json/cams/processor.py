import re
from decimal import Decimal

from dateutil import parser as date_parser
from pymupdf import Rect

from cas2json import patterns
from cas2json.cams.helpers import get_parsed_scheme_name, get_transaction_type
from cas2json.exceptions import CASParseError
from cas2json.flags import MULTI_TEXT_FLAGS, TEXT_FLAGS
from cas2json.types import (
    CAMSScheme,
    CASData,
    DocumentData,
    StatementPeriod,
    TransactionData,
    WordData,
)
from cas2json.utils import formatINR, get_statement_dates


class CASProcessor:
    __slots__ = ()

    @staticmethod
    def extract_amc(line: str) -> str | None:
        """
        Extract amc name from the line if present.

        Supported line formats
        ----------------------
        - "Franklin Templeton Mutual Fund"
        - "HDFC Mutual Fund"
        """
        if amc_match := re.search(patterns.AMC, line, TEXT_FLAGS):
            return amc_match.group(0)
        return None

    @staticmethod
    def extract_folio_pan(line: str, current_folio: str | None) -> tuple[str | None, str | None]:
        """
        Extract folio and PAN from the line if present.

        Supported line formats
        ----------------------
        - "Folio No: 1122334455 / 12 PAN: ABCDE1234F KYC: OK PAN: OK"
        """
        if folio_match := re.search(patterns.FOLIO, line):
            folio = folio_match.group(1).strip()
            pan_match = re.search(patterns.PAN, line)
            pan = pan_match.group(1) if pan_match else None
            return folio, pan
        return current_folio, None

    @staticmethod
    def extract_scheme_details(line: str) -> tuple[str, str, str, str] | None:
        """
        Extract scheme details from the line if present in order of <scheme_name>, <isin>, <rta_code>, <advisor>.

        Supported line formats
        ----------------------
        - "HINFG-HDFC Infrastructure Fund - Regular Plan - Growth (Non-Demat) - ISIN: INF179K01GF8(Advisor: ARN-0845) Registrar : CAMS"

        - "FTI219-Franklin India Small Cap Fund - Growth (erstwhile Franklin India Smaller Companies Fund - Growth) (Non-Demat) -
          ISIN: INF090I01569 Registrar : CAMS (Advisor: ARN-0845)"
        """
        if scheme_match := re.search(patterns.SCHEME, line, MULTI_TEXT_FLAGS):
            scheme_name = get_parsed_scheme_name(scheme_match.group("name"))
            # Split Scheme details becomes a bit malformed having "Registrar : CAMS" in between, hence
            # we have to remove it.
            formatted_line = re.sub(r"Registrar\s*:\s*CAMS", "", line).strip()
            metadata = {
                key.strip().lower(): re.sub(r"\s+", "", value)
                for key, value in re.findall(patterns.SCHEME_METADATA, formatted_line, MULTI_TEXT_FLAGS)
            }
            isin_match = re.search(f"({patterns.ISIN})", metadata.get("isin") or "")
            isin = isin_match.group(1) if isin_match else metadata.get("isin")
            rta_code = scheme_match.group("code").strip()
            advisor = metadata.get("advisor")
            return scheme_name, isin, rta_code, advisor
        return None

    @staticmethod
    def extract_registrar(line: str) -> str | None:
        """
        Extract registrar name from the line if present.

        Supported line formats
        ----------------------
        - The following statement can be present as part of any line or can be independent line:

          "Registrar : CAMS"
        """
        if registrar_match := re.search(patterns.REGISTRAR, line, TEXT_FLAGS):
            return registrar_match.group(1).strip()
        return None

    @staticmethod
    def extract_nominees(line: str) -> list[str]:
        """
        Extract nominee names from the line if present.

        Supported line formats
        ----------------------
        - "Nominee 1: Joe Doe Nominee 2: Jane Doe Nominee 3: John Doe"
        """
        nominee_match = re.findall(patterns.NOMINEE, line, MULTI_TEXT_FLAGS)
        return [nominee.strip() for nominee in nominee_match if nominee.strip()]

    @staticmethod
    def extract_open_units(line: str) -> Decimal | None:
        """
        Extract opening unit balance from the line if present.

        Supported line formats
        ----------------------
        - "Opening Unit Balance: 50.166"
        """
        if open_units_match := re.search(patterns.OPEN_UNITS, line, MULTI_TEXT_FLAGS):
            return formatINR(open_units_match.group(1))
        return None

    @staticmethod
    def extract_scheme_valuation(line: str, current_scheme: CAMSScheme) -> CAMSScheme:
        """
        Extract and update scheme valuation details from the line if present.

        Supported line formats
        ----------------------
        - "Closing Unit Balance: 50.166 NAV on 20-Sep-2001: INR 112.1222 Total Cost Value: 123.12 Market Value on 20-Sep-2001: INR 110.24"
        """
        if close_units_match := re.search(patterns.CLOSE_UNITS, line):
            current_scheme.units = formatINR(close_units_match.group(1))

        if cost_match := re.search(patterns.COST, line, re.I):
            current_scheme.cost = formatINR(cost_match.group(1))
            current_scheme.invested_value = current_scheme.cost * current_scheme.units if current_scheme.units else None

        if valuation_match := re.search(patterns.VALUATION, line, re.I):
            current_scheme.market_value = formatINR(valuation_match.group(2))

        if nav_match := re.search(patterns.NAV, line, re.I):
            current_scheme.nav = formatINR(nav_match.group(2))

        return current_scheme

    @staticmethod
    def extract_transactions(
        line: str, word_rects: list[WordData], headers: dict[str, Rect], value_tolerance: tuple[float, float] = (20, 5)
    ) -> list[TransactionData]:
        """
        Parse a transaction line and return a list of TransactionData objects.

        Parameters
        ----------
        line : str
            Line of text to parse.
        word_rects : list[WordData]
            Data of words for the line.
        headers : dict[str, Rect]
            Data of header positions on the page of given line
        value_tolerance : tuple[float, float]
            Tolerance thresholds that establish the range for transaction identification.

        Returns
        -------
        list[TransactionData]
            A list of parsed transaction data (generally one, but can be more in case of multiple transactions on same line).

        Supported line formats
        ----------------------
        - Regular transaction with all 4 values:

          "25-Nov-2001 Systematic Investment Purchase -BSE Instalment No 1 9,999.50 50.166 116.6680 50.166"

        - Multiple transactions on same line:

          "26-Feb-2024 *** Stamp Duty *** 0.50 25-Nov-2001 Systematic Investment Purchase -BSE Instalment No 1 9,999.50 50.166 116.6680 50.166"

        - Transaction with missing values (e.g. amount) (uses header positions and word positions to identify values):

          "25-Nov-2001 Redemption 50.166 116.6680 50.166"
        """

        def normalize(s: str) -> str:
            return s.replace("(", "").replace(")", "").strip()

        transactions: list[TransactionData] = []
        parsed_transactions = re.findall(patterns.TRANSACTIONS, line, MULTI_TEXT_FLAGS)
        left_tol, right_tol = value_tolerance
        if not parsed_transactions:
            return transactions

        for txn in parsed_transactions:
            date, details, *_ = txn
            if not details or not details.strip() or not date:
                continue
            description_match = re.match(patterns.DESCRIPTION, details.strip(), MULTI_TEXT_FLAGS)
            if not description_match:
                continue
            description, values, *_ = description_match.groups()
            values = re.findall(patterns.AMT, values.strip())
            txn_values = {"amount": None, "units": None, "nav": None, "balance": None}
            if len(values) >= 4:
                # Normal entry
                txn_values["amount"], txn_values["units"], txn_values["nav"], txn_values["balance"], *_ = values
            else:
                for val in values:
                    val_rects = [(w[0], idx) for idx, w in enumerate(word_rects) if normalize(w[1]) == normalize(val)]
                    if not val_rects:
                        continue
                    val_rect, idx = val_rects[0]
                    # Remove to avoid matching again
                    word_rects.pop(idx)
                    for header, rect in headers.items():
                        if rect and val_rect.x0 >= rect.x0 - left_tol and val_rect.x1 <= rect.x1 + right_tol:
                            txn_values[header] = val
                            break

            description = description.strip()
            units = formatINR(txn_values["units"])
            transaction_type, dividend_rate = get_transaction_type(description, units)
            # Consider positive and handle inflow/outflow based on units/transaction type
            amount = abs(formatINR(txn_values["amount"])) if txn_values["amount"] else None
            transactions.append(
                TransactionData(
                    date=date_parser.parse(date).date(),
                    description=description,
                    type=transaction_type.name,
                    amount=amount,
                    units=units,
                    nav=formatINR(txn_values["nav"]),
                    balance=formatINR(txn_values["balance"]),
                    dividend_rate=dividend_rate,
                )
            )
        return transactions

    def process_detailed_version(self, document_data: DocumentData) -> CASData:
        """Process the parsed data of CAMS pdf and return the detailed processed data."""

        def finalize_current_scheme():
            """Append current scheme to the schemes list and reset"""
            nonlocal current_scheme
            if current_scheme:
                schemes.append(current_scheme)
                current_scheme = None

        schemes: list[CAMSScheme] = []
        statement_period: StatementPeriod | None = None
        current_folio: str | None = None
        current_scheme: CAMSScheme | None = None
        current_pan: str | None = None
        current_amc: str | None = None
        current_registrar: str | None = None
        for page_data in document_data:
            page_lines_data = list(page_data.lines_data)

            if not statement_period:
                from_date, to_date, *_ = get_statement_dates([i for i, _ in page_lines_data], patterns.DETAILED_DATE)
                statement_period = StatementPeriod(from_=from_date, to=to_date)

            for idx, (line, word_rects) in enumerate(page_lines_data):
                if amc := self.extract_amc(line):
                    current_amc = amc
                    continue

                if (folio_pan := self.extract_folio_pan(line, current_folio)) and current_folio != folio_pan[0]:
                    finalize_current_scheme()
                    current_folio, current_pan = folio_pan
                    continue
                # Long scheme names are sometimes split into multiple lines (usually 2).
                # Thus, we need to join the split lines.
                scheme_line = line
                if idx + 1 < len(page_lines_data) and not re.search(patterns.NOMINEE, line, TEXT_FLAGS):
                    scheme_line = f"{scheme_line} {page_lines_data[idx + 1][0]}".strip()

                if scheme_details := self.extract_scheme_details(scheme_line):
                    if current_folio is None:
                        raise CASParseError("Layout Error! Scheme found before folio entry.")
                    scheme_name, isin, rta_code, advisor = scheme_details
                    if current_scheme and current_scheme.scheme_name != scheme_name:
                        finalize_current_scheme()
                    current_scheme = CAMSScheme(
                        scheme_name=scheme_name,
                        isin=isin,
                        pan=current_pan,
                        folio=current_folio,
                        units=Decimal("0.0"),
                        nav=Decimal("0.0"),
                        cost=None,
                        amc=current_amc,
                        advisor=advisor,
                        rta_code=rta_code,
                        opening_units=Decimal("0.0"),
                        closing_units=Decimal("0.0"),
                    )
                    if current_registrar:
                        current_scheme.rta = current_registrar
                        current_registrar = None

                # Registrar can be on the same line as scheme description or on the next/previous line
                if registrar := self.extract_registrar(line):
                    if current_scheme:
                        current_scheme.rta = registrar
                    else:
                        current_registrar = registrar
                    continue

                if current_scheme is None:
                    continue

                if nominees := self.extract_nominees(line):
                    current_scheme.nominees.extend(nominees)
                    continue

                if (open_units := self.extract_open_units(line)) is not None:
                    current_scheme.opening_units = current_scheme.closing_units = open_units
                    continue

                if parsed_txns := self.extract_transactions(line, word_rects, headers=page_data.headers_data):
                    for txn in parsed_txns:
                        if txn.units is not None:
                            current_scheme.closing_units += txn.units
                    current_scheme.transactions.extend(parsed_txns)

                current_scheme = self.extract_scheme_valuation(line, current_scheme)

        finalize_current_scheme()

        return CASData(statement_period=statement_period, schemes=schemes)

    def process_summary_version(self, document_data: DocumentData) -> CASData:
        """Process the text version of a CAS pdf and return the summarized processed data."""

        schemes: list[CAMSScheme] = []
        current_folio: str | None = None
        current_scheme: CAMSScheme | None = None
        statement_period: StatementPeriod | None = None

        for page_data in document_data:
            page_lines = [line for line, _ in page_data.lines_data]

            if not statement_period:
                date, *_ = get_statement_dates(page_lines, patterns.SUMMARY_DATE)
                statement_period = StatementPeriod(from_=date, to=date)

            for line in page_lines:
                if schemes and re.search("Total", line, re.I):
                    break

                if summary_row_match := re.search(patterns.SUMMARY_ROW, line, MULTI_TEXT_FLAGS):
                    if current_scheme:
                        schemes.append(current_scheme)
                        current_scheme = None

                    folio = summary_row_match.group("folio").strip()
                    if current_folio is None or current_folio != folio:
                        current_folio = folio

                    scheme_name = summary_row_match.group("name")
                    scheme_name = re.sub(r"\(formerly.+?\)", "", scheme_name, flags=TEXT_FLAGS).strip()

                    current_scheme = CAMSScheme(
                        isin=summary_row_match.group("isin"),
                        scheme_name=scheme_name,
                        folio=current_folio,
                        units=formatINR(summary_row_match.group("balance")),
                        nav=formatINR(summary_row_match.group("nav")),
                        market_value=formatINR(summary_row_match.group("value")),
                        cost=formatINR(summary_row_match.group("cost")),
                        rta=summary_row_match.group("rta").strip(),
                        rta_code=summary_row_match.group("code").strip(),
                    )
                    continue

                # Append any remaining scheme tails to the current scheme name
                if current_scheme:
                    current_scheme.scheme_name = f"{current_scheme.scheme_name} {line.strip()}"

        return CASData(statement_period=statement_period, schemes=schemes)
