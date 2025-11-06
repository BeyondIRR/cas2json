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

from importlib.metadata import version

from cas2json.cams import parse_cams_pdf
from cas2json.cams.parser import CAMSParser
from cas2json.nsdl import parse_nsdl_pdf
from cas2json.nsdl.parser import NSDLParser
from cas2json.parser import BaseCASParser

__version__ = version("cas2json")

__all__ = ["BaseCASParser", "CAMSParser", "NSDLParser", "parse_cams_pdf", "parse_nsdl_pdf"]
