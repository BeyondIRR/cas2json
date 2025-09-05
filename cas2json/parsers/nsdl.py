import io

from cas2json.enums import FileType
from cas2json.exceptions import CASParseError
from cas2json.parsers.common import cas_pdf_to_text
from cas2json.processors.nsdl import process_nsdl_text
from cas2json.types import NSDLCASData


def parse_nsdl_pdf(filename: str | io.IOBase, password: str) -> NSDLCASData:
    partial_cas_data = cas_pdf_to_text(filename, password)
    if partial_cas_data.file_type != FileType.NSDL:
        raise CASParseError("Not a valid NSDL file")
    processed_data = process_nsdl_text("\u2029".join(partial_cas_data.lines))
    return NSDLCASData(
        statement_period=processed_data.statement_period,
        accounts=processed_data.accounts,
        investor_info=partial_cas_data.investor_info,
        file_type=partial_cas_data.file_type,
    )
