import io

from cas2json.enums import FileType
from cas2json.exceptions import CASParseError
from cas2json.nsdl.processor import NSDLProcessor
from cas2json.parser import CASParser
from cas2json.types import NSDLCASData


def parse_nsdl_pdf(filename: str | io.IOBase, password: str) -> NSDLCASData:
    """
    Parse NSDL pdf and returns processed data.

    Parameters
    ----------
    filename : str | io.IOBase
        The path to the PDF file or a file-like object.
    password : str
        The password to unlock the PDF file.
    """
    partial_cas_data = CASParser(filename, password).parse_pdf()
    if partial_cas_data.file_type != FileType.NSDL:
        raise CASParseError("Not a valid NSDL file")
    processed_data = NSDLProcessor().process_statement(partial_cas_data.document_data)
    processed_data.file_type = partial_cas_data.file_type
    processed_data.investor_info = partial_cas_data.investor_info
    processed_data.statement_period = partial_cas_data.statement_period
    return processed_data
