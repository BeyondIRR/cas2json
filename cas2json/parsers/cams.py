import io
import re

from cas2json.enums import CASFileType, FileType
from cas2json.exceptions import CASParseError
from cas2json.flags import MULTI_TEXT_FLAGS
from cas2json.parsers.common import cas_pdf_to_text
from cas2json.patterns import CAS_TYPE
from cas2json.processors.cams import process_detailed_text, process_summary_text
from cas2json.types import CASData


def detect_cas_type(parsed_lines: list[str]) -> CASFileType:
    """Detect the type of CAS statement (detailed or summary) from the parsed lines."""
    text = "\u2029".join(parsed_lines)
    if m := re.search(CAS_TYPE, text, MULTI_TEXT_FLAGS):
        match = m.group(1).lower().strip()
        if match == "statement":
            return CASFileType.DETAILED
        elif match == "summary":
            return CASFileType.SUMMARY
    return CASFileType.UNKNOWN


def parse_cams_pdf(filename: str | io.IOBase, password: str, sort_transactions=True):
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
