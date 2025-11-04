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
from decimal import Decimal

from cas2json.cams.parser import CAMSParser
from cas2json.cams.processor import CAMSProcessor
from cas2json.cams.types import CAMSData
from cas2json.enums import FileVersion
from cas2json.exceptions import CASParseError


def parse_cams_pdf(filename: str | io.IOBase, password: str | None = None, sort_transactions=True) -> CAMSData:
    """
    Parse CAMS or KFintech CAS pdf and returns processed data.

    Parameters
    ----------
    filename : str | io.IOBase
        The path to the PDF file or a file-like object.
    password : str | None
        The password to unlock the PDF file.
    sort_transactions : bool
        Whether to sort transactions by date and re-compute balances.
    """

    partial_cas_data = CAMSParser(filename, password).parse_pdf()

    if partial_cas_data.metadata.file_version == FileVersion.DETAILED:
        schemes = CAMSProcessor().process_detailed_version_schemes(partial_cas_data.document_data)
    elif partial_cas_data.metadata.file_version == FileVersion.SUMMARY:
        schemes = CAMSProcessor().process_summary_version_schemes(partial_cas_data.document_data)
    else:
        raise CASParseError("Unknown CAS file type")

    if sort_transactions:
        for scheme in schemes:
            transactions = scheme.transactions
            sorted_transactions = sorted(transactions, key=lambda x: x.date)
            if transactions != sorted_transactions:
                balance = Decimal(scheme.opening_units or 0)
                for transaction in sorted_transactions:
                    balance += Decimal(transaction.units or 0)
                    transaction.balance = balance
                scheme.transactions = sorted_transactions

    return CAMSData(schemes=schemes, metadata=partial_cas_data.metadata)
