import io

from cas2json.cams.processor import CASProcessor
from cas2json.enums import FileType, FileVersion
from cas2json.exceptions import CASParseError
from cas2json.parser import cas_pdf_to_text
from cas2json.types import CASData


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
    """

    partial_cas_data = cas_pdf_to_text(filename, password)
    if partial_cas_data.file_type not in [FileType.CAMS, FileType.KFINTECH]:
        raise CASParseError("Not a valid CAMS file")

    if partial_cas_data.file_version == FileVersion.DETAILED:
        processed_data = CASProcessor().process_detailed_version(partial_cas_data.document_data)
    elif partial_cas_data.file_version == FileVersion.SUMMARY:
        processed_data = CASProcessor().process_summary_version(partial_cas_data.document_data)
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

    processed_data.investor_info = partial_cas_data.investor_info
    processed_data.file_type = partial_cas_data.file_type
    processed_data.file_version = partial_cas_data.file_version
    return processed_data
