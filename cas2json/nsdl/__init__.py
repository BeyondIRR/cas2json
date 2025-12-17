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

import io
from enum import Enum

from cas2json.nsdl.line_parser.parser import NSDLLineParser
from cas2json.nsdl.line_parser.processor import NSDLLineProcessor
from cas2json.nsdl.types import NSDLCASData


class ParseMethod(Enum):
    LINE_BASED = "line"
    TABLE_BASED = "table"


def parse_nsdl_pdf(
    filename: str | io.IOBase, password: str, method: ParseMethod = ParseMethod.LINE_BASED
) -> NSDLCASData:
    """
    Parse NSDL pdf and returns processed data.

    Parameters
    ----------
    filename : str | io.IOBase
        The path to the PDF file or a file-like object.
    password : str
        The password to unlock the PDF file.
    method : str
        The method to be used for parsing the pdf (right now we have only implemented one)
    """
    if method == ParseMethod.LINE_BASED:
        parser = NSDLLineParser(filename, password)
        processor = NSDLLineProcessor()
    else:
        raise NotImplementedError("Incorrect parsing method input")
    partial_cas_data = parser.parse_pdf()
    processed_data = processor.process_statement(partial_cas_data.document_data)
    processed_data.metadata = partial_cas_data.metadata
    return processed_data
