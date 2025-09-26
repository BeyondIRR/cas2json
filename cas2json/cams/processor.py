import re
from decimal import Decimal

from dateutil import parser as date_parser
from pymupdf import Rect

from cas2json import patterns
from cas2json.cams.helpers import get_parsed_scheme_name, get_transaction_type
from cas2json.exceptions import CASParseError
from cas2json.flags import MULTI_TEXT_FLAGS, TEXT_FLAGS
from cas2json.types import (
    DocumentData,
    ProcessedCASData,
    Scheme,
    SchemeValuation,
    StatementPeriod,
    TransactionData,
    WordData,
)
from cas2json.utils import formatINR, get_statement_dates


class CASProcessor:
    __slots__ = ()

    @staticmethod
    def extract_amc(line: str) -> str | None:
        if amc_match := re.search(patterns.AMC, line, TEXT_FLAGS):
            return amc_match.group(0)
        return None

    @staticmethod
    def extract_folio_pan(line: str, current_folio: str | None) -> tuple[str | None, str | None]:
        if folio_match := re.search(patterns.FOLIO, line):
            folio = folio_match.group(1).strip()
            pan_match = re.search(patterns.PAN, line)
            pan = pan_match.group(1) if pan_match else None
            return folio, pan
        return current_folio, None

    @staticmethod
    def extract_scheme_details(line: str) -> tuple[str, str, str, str] | None:
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
        if registrar_match := re.search(patterns.REGISTRAR, line, TEXT_FLAGS):
            return registrar_match.group(1).strip()
        return None

    @staticmethod
    def extract_nominees(line: str) -> list[str]:
        nominee_match = re.findall(patterns.NOMINEE, line, MULTI_TEXT_FLAGS)
        return [nominee.strip() for nominee in nominee_match if nominee.strip()]

    @staticmethod
    def extract_open_units(line: str) -> Decimal | None:
        if open_units_match := re.search(patterns.OPEN_UNITS, line, MULTI_TEXT_FLAGS):
            return formatINR(open_units_match.group(1))
        return None

    @staticmethod
    def extract_scheme_valuation(line: str, current_scheme: Scheme) -> Scheme:
        if close_units_match := re.search(patterns.CLOSE_UNITS, line):
            current_scheme.close = formatINR(close_units_match.group(1))

        if cost_match := re.search(patterns.COST, line, re.I):
            current_scheme.valuation.cost = formatINR(cost_match.group(1))

        if valuation_match := re.search(patterns.VALUATION, line, re.I):
            current_scheme.valuation.date = date_parser.parse(valuation_match.group(1)).date()
            current_scheme.valuation.value = formatINR(valuation_match.group(2))

        if nav_match := re.search(patterns.NAV, line, re.I):
            current_scheme.valuation.date = date_parser.parse(nav_match.group(1)).date()
            current_scheme.valuation.nav = formatINR(nav_match.group(2))

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
            txn_type, dividend_rate = get_transaction_type(description, units)
            transactions.append(
                TransactionData(
                    date=date_parser.parse(date).date(),
                    description=description,
                    type=txn_type.name,
                    amount=formatINR(
                        txn_values["amount"], negative=False
                    ),  # Always consider positive and handle via type
                    units=units,
                    nav=formatINR(txn_values["nav"]),
                    balance=formatINR(txn_values["balance"]),
                    dividend_rate=dividend_rate,
                )
            )
        return transactions

    def process_detailed_version(self, document_data: DocumentData) -> ProcessedCASData:
        """
        Process the parsed data of CAMS pdf and return the detailed processed data.
        """

        def finalize_current_scheme():
            """Append current scheme to the schemes list and reset"""
            nonlocal current_scheme
            if current_scheme:
                schemes.append(current_scheme)
                current_scheme = None

        schemes: list[Scheme] = []
        statement_period: StatementPeriod | None = None
        current_folio: str | None = None
        current_scheme: Scheme | None = None
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
                    current_scheme = Scheme(
                        scheme_name=scheme_name,
                        amc=current_amc,
                        pan=current_pan,
                        folio=current_folio,
                        advisor=advisor,
                        rta=None,
                        rta_code=rta_code,
                        isin=isin,
                        open=Decimal("0.0"),
                        close=Decimal("0.0"),
                        close_calculated=Decimal("0.0"),
                        valuation=SchemeValuation(date=statement_period.to, value=Decimal("0.0"), nav=Decimal("0.0")),
                        transactions=[],
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

                if open_units := self.extract_open_units(line):
                    current_scheme.open = open_units
                    current_scheme.close_calculated = open_units
                    continue

                if parsed_txns := self.extract_transactions(line, word_rects, headers=page_data.headers_data):
                    for txn in parsed_txns:
                        if txn.units is not None:
                            current_scheme.close_calculated += txn.units
                    current_scheme.transactions.extend(parsed_txns)

                current_scheme = self.extract_scheme_valuation(line, current_scheme)

        finalize_current_scheme()

        return ProcessedCASData(statement_period=statement_period, schemes=schemes)

    def process_summary_version(self, document_data: DocumentData) -> ProcessedCASData:
        """
        Process the text version of a CAS pdf and return the summarized processed data.
        """

        schemes: list[Scheme] = []
        current_folio: str | None = None
        current_scheme: Scheme | None = None
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

                    current_scheme = Scheme(
                        scheme_name=scheme_name,
                        advisor="N/A",
                        pan="N/A",
                        folio=current_folio,
                        amc="N/A",
                        rta_code=summary_row_match.group("code").strip(),
                        rta=summary_row_match.group("rta").strip(),
                        isin=summary_row_match.group("isin"),
                        open=formatINR(summary_row_match.group("balance")),
                        close=formatINR(summary_row_match.group("balance")),
                        close_calculated=formatINR(summary_row_match.group("balance")),
                        valuation=SchemeValuation(
                            date=date_parser.parse(summary_row_match.group("date")).date(),
                            nav=formatINR(summary_row_match.group("nav")),
                            value=formatINR(summary_row_match.group("value")),
                            cost=formatINR(summary_row_match.group("cost")),
                        ),
                        transactions=[],
                    )
                    continue

                # Append any remaining scheme tails to the current scheme name
                if current_scheme:
                    current_scheme.scheme_name = f"{current_scheme.scheme_name} {line.strip()}"

        return ProcessedCASData(statement_period=statement_period, schemes=schemes)
