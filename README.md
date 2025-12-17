<!--
SPDX-License-Identifier: GPL-3.0-or-later
Copyright (C) 2025 BeyondIRR <https://beyondirr.com/>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
-->

# Cas2JSON

[![code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A library to parse CAS (Consolidated Account Statement) from providers like CAMS, KFINTECH, NSDL (BETA) and get related data in JSON format.

## Installation
```bash
pip install -U cas2json
```

## Usage

```python
# For CAMS/KFINTECH
from cas2json import parse_cams_pdf
data = parse_cams_pdf("/path/to/cams/file.pdf", "password")

# For NSDL
from cas2json import parse_nsdl_pdf
data = parse_nsdl_pdf("/path/to/nsdl/file.pdf", "password")

# To get data in form of Python dict
from dataclasses import asdict
python_dict = asdict(data)

# To convert the data from python dict to JSON
from msgspec import json
json_data = json.encode(python_dict)


```

Notes:
- All used types like transaction types can be found under `cas2json/enums.py`.
- NSDL currently supports only parsing of holdings since the transactions history is not complete.
- Adding multiple parsing methods for better control and accuracy is currently a work in progress and is NOT STABLE.
## License

Cas2JSON is distributed under GNU GPL v3 license. - _IANAL_

## Credits

This library is inspired by [CASParser](https://github.com/codereverser/casparser), but it is an independent reimplementation with significant changes in both design and processing logic. In particular, it introduces a revised method for parsing textual data and for accurately identifying transaction values, even in cases where one or more trailing values may be missing from the record.

This project is not affiliated with or endorsed by the original CASParser author

## Resources
1. [CAS from CAMS](https://www.camsonline.com/Investors/Statements/Consolidated-Account-Statement)
2. [CAS from Karvy/Kfintech](https://mfs.kfintech.com/investor/General/ConsolidatedAccountStatement)
