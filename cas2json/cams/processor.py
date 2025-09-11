import io
import re
from decimal import Decimal

from dateutil import parser as date_parser

from cas2json import patterns
from cas2json.cams.helpers import detect_cas_type, get_parsed_scheme_name, parse_transaction
from cas2json.enums import CASFileType
from cas2json.exceptions import CASParseError
from cas2json.flags import MULTI_TEXT_FLAGS, TEXT_FLAGS
from cas2json.parser import cas_pdf_to_text
from cas2json.types import (
    CASData,
    FileType,
    ProcessedCASData,
    Scheme,
    SchemeValuation,
    StatementPeriod,
)
from cas2json.utils import formatINR, get_statement_dates


def process_detailed_text(parsed_lines: list[str]) -> ProcessedCASData:
    """
    Process the text version of a CAS pdf and return the detailed processed data.
    """

    def finalize_current_scheme():
        """Append current scheme to the schemes list and reset"""
        nonlocal current_scheme
        if current_scheme:
            schemes.append(current_scheme)
            current_scheme = None

    from_date, to_date, *_ = get_statement_dates(parsed_lines, patterns.DETAILED_DATE)
    statement_period = StatementPeriod(from_=from_date, to=to_date)

    schemes: list[Scheme] = []
    current_folio: str | None = None
    current_pan: str | None = None
    current_amc: str | None = None
    current_scheme: Scheme | None = None
    current_registrar: str | None = None
    for idx, line in enumerate(parsed_lines):
        if amc_match := re.search(patterns.AMC, line, TEXT_FLAGS):
            current_amc = amc_match.group(0)
            continue

        if folio_match := re.search(patterns.FOLIO, line):
            folio = folio_match.group(1).strip()
            if current_folio != folio:
                finalize_current_scheme()
                current_folio = folio
                pan_match = re.search(patterns.PAN, line)
                current_pan = pan_match.group(1) if pan_match else None
            continue
        # Long scheme names are sometimes split into multiple lines (usually 2).
        # Thus, we need to join the split lines.
        scheme_line = line
        if idx + 1 < len(parsed_lines) and not re.search(patterns.NOMINEE, line, TEXT_FLAGS):
            scheme_line = f"{scheme_line} {parsed_lines[idx + 1]}"
        if scheme_match := re.search(patterns.SCHEME, scheme_line, MULTI_TEXT_FLAGS):
            if current_folio is None:
                raise CASParseError("Layout Error! Scheme found before folio entry.")

            scheme_name = get_parsed_scheme_name(scheme_match.group("name"))
            if current_scheme and current_scheme.scheme_name != scheme_name:
                finalize_current_scheme()
            # Split Scheme details becomes a bit malformed having "Registrar : CAMS" in between, hence
            # we have to re-parse the line
            formatted_line = re.sub(r"Registrar\s*:\s*CAMS", "", scheme_line).strip()
            metadata = {
                key.strip().lower(): re.sub(r"\s+", "", value)
                for key, value in re.findall(patterns.SCHEME_METADATA, formatted_line, MULTI_TEXT_FLAGS)
            }

            isin_match = re.search(f"({patterns.ISIN})", metadata.get("isin") or "")
            isin = isin_match.group(1) if isin_match else metadata.get("isin")
            current_scheme = Scheme(
                scheme_name=scheme_name,
                amc=current_amc,
                pan=current_pan,
                folio=current_folio,
                advisor=metadata.get("advisor"),
                rta=None,
                rta_code=scheme_match.group("code").strip(),
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
        if registrar_match := re.search(patterns.REGISTRAR, line, TEXT_FLAGS):
            if current_scheme:
                current_scheme.rta = registrar_match.group(1).strip()
            else:
                current_registrar = registrar_match.group(1).strip()
            continue

        if not current_scheme:
            continue

        if nominee_match := re.findall(patterns.NOMINEE, line, TEXT_FLAGS):
            current_scheme.nominees.extend([x.strip() for x in nominee_match if x.strip()])
            continue

        if open_units_match := re.search(patterns.OPEN_UNITS, line):
            current_scheme.open = formatINR(open_units_match.group(1))
            current_scheme.close_calculated = current_scheme.open
            continue

        # All the following details are in one line (generally :))
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
            continue

        if parsed_txns := parse_transaction(line):
            for txn in parsed_txns:
                if txn.units is not None:
                    current_scheme.close_calculated += txn.units
            current_scheme.transactions.extend(parsed_txns)

    finalize_current_scheme()

    return ProcessedCASData(cas_type=CASFileType.DETAILED, statement_period=statement_period, schemes=schemes)


def process_summary_text(parsed_lines: list[str]) -> ProcessedCASData:
    """
    Process the text version of a CAS pdf and return the summarized processed data.
    """
    date, *_ = get_statement_dates(parsed_lines, patterns.SUMMARY_DATE)
    statement_period = StatementPeriod(from_=date, to=date)

    schemes: list[Scheme] = []
    current_folio: str | None = None
    current_scheme = None

    for line in parsed_lines:
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

    return ProcessedCASData(cas_type=CASFileType.SUMMARY, statement_period=statement_period, schemes=schemes)


def parse_cams_pdf(filename: str | io.IOBase, password: str, sort_transactions=True) -> CASData:
    """
    Parse CAMS or KFintech CAS pdf and returns processed data.

    Parameters
    ----------
    filename : str | io.IOBase
        The path to the PDF file or a file-like object.
    password : str
        The password to unlock the PDF file.
    sort_transactions : bool
        Whether to sort transactions by date and re-compute balances.

    Returns
    -------
    Parsed CAMS or KFintech CAS data
    """

    partial_cas_data = cas_pdf_to_text(filename, password)
    if partial_cas_data.file_type not in [FileType.CAMS, FileType.KFINTECH]:
        raise CASParseError("Not a valid CAMS file")

    cas_statement_type = detect_cas_type(partial_cas_data.lines)
    if cas_statement_type == CASFileType.DETAILED:
        processed_data = process_detailed_text(partial_cas_data.lines)
    elif cas_statement_type == CASFileType.SUMMARY:
        processed_data = process_summary_text(partial_cas_data.lines)
    else:
        raise CASParseError("Unknown CAS file type")

    if sort_transactions:
        for scheme in processed_data.schemes:
            transactions = scheme.transactions
            sorted_transactions = sorted(transactions, key=lambda x: x.date)
            if transactions != sorted_transactions:
                balance = scheme.open
                for transaction in sorted_transactions:
                    balance += transaction.units or 0
                    transaction.balance = balance
                scheme.transactions = sorted_transactions

    return CASData(
        statement_period=processed_data.statement_period,
        schemes=processed_data.schemes,
        cas_type=processed_data.cas_type,
        investor_info=partial_cas_data.investor_info,
        file_type=partial_cas_data.file_type,
    )
