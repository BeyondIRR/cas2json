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

from cas2json.cdsl.parser import CDSLParser
from cas2json.cdsl.processor import CDSLProcessor
from cas2json.types import DepositoryCASData


def parse_cdsl_pdf(filename: str | io.IOBase, password: str) -> DepositoryCASData:
    """
    Parse CDSL pdf and returns processed data.

    Parameters
    ----------
    filename : str | io.IOBase
        The path to the PDF file or a file-like object.
    password : str
        The password to unlock the PDF file.
    """
    partial_cas_data = CDSLParser(filename, password).parse_pdf()
    processed_data = CDSLProcessor().process_statement(partial_cas_data.document_data)
    processed_data.metadata = partial_cas_data.metadata
    return processed_data
