import io
import re
from typing import Any

from pymupdf import TEXTFLAGS_TEXT, Document, Page, Rect

from cas2json.enums import FileType
from cas2json.exceptions import CASParseError, IncorrectPasswordError
from cas2json.flags import MULTI_TEXT_FLAGS
from cas2json.patterns import (
    CAS_ID,
    CAS_TYPE,
    DEMAT_STATEMENT_PERIOD,
    DETAILED_DATE,
    INVESTOR_MAIL,
    INVESTOR_STATEMENT,
    INVESTOR_STATEMENT_DP,
    SUMMARY_DATE,
)
from cas2json.types import (
    DocumentData,
    FileVersion,
    InvestorInfo,
    LineData,
    PageData,
    PartialCASData,
    StatementPeriod,
    WordData,
)


class CASParser:
    __slots__ = ("document",)

    def __init__(self, filename: str | io.IOBase, password: str | None = None) -> None:
        self.document: Document = self._get_document(filename, password)

    @staticmethod
    def _get_document(filename: str | io.IOBase, password: str | None) -> Document:
        """
        Open and return pymupdf Document instance.

        Parameters
        ----------
        filename : str | io.IOBase
            The path to the PDF file or a file-like object.
        password : str
            The password to unlock the PDF file.

        Returns
        -------
        Document instance of provided file
        """
        if isinstance(filename, str):
            fp = open(filename, "rb")  # NOQA
        elif hasattr(filename, "read") and hasattr(filename, "close"):  # file-like object
            fp = filename
        else:
            raise CASParseError("Invalid input. filename should be a string or a file like object")

        with fp:
            try:
                doc = Document(stream=fp.read(), filetype="pdf")
            except Exception as e:
                raise CASParseError(f"Unhandled error while opening file :: {e!s}") from e

            if doc.needs_pass:
                rc = doc.authenticate(password)
                if not rc:
                    raise IncorrectPasswordError("Incorrect PDF password!")
            return doc

    @staticmethod
    def parse_file_type(page_blocks: list[tuple]) -> FileType:
        """Parse file type using text of blocks. First page of File is preferred"""
        for block in page_blocks:
            block_text = block[4].strip()
            if re.search("CAMSCASWS", block_text):
                return FileType.CAMS
            elif re.search("KFINCASWS", block_text):
                return FileType.KFINTECH
            elif "NSDL Consolidated Account Statement" in block_text or "About NSDL" in block_text:
                return FileType.NSDL
            elif "Central Depository Services (India) Limited" in block_text:
                return FileType.CDSL
        return FileType.UNKNOWN

    @staticmethod
    def parse_file_version(page_blocks: list[tuple]) -> FileVersion:
        """Detect the type of CAS statement (detailed or summary) from the parsed lines."""
        for block in page_blocks:
            if m := re.search(CAS_TYPE, block[4].strip(), MULTI_TEXT_FLAGS):
                match = m.group(1).lower().strip()
                if match == "statement":
                    return FileVersion.DETAILED
                elif match == "summary":
                    return FileVersion.SUMMARY
        return FileVersion.UNKNOWN

    @staticmethod
    def parse_cams_investor_info(page: Page) -> InvestorInfo:
        """
        Parse investor info using pymupdf tables.

        Parameters
        ----------
        page : Page
            The pymupdf page object to extract information from.

        Returns
        -------
        InvestorInfo
            The extracted investor information.
        """
        email_found = False
        address_lines = []
        email = mobile = name = None

        tables = page.find_tables(strategy="lines")
        first_table = tables.tables[0] if tables.tables else None
        # getting text of first row
        row_text = first_table.extract()[0]

        for cell_text in row_text:
            if not cell_text:
                continue
            for text in cell_text.strip().split("\n"):
                text = text.strip()
                if not email_found:
                    if email_match := re.search(INVESTOR_MAIL, text, re.I):
                        email = email_match.group(1).strip()
                        email_found = True
                    continue

                if name is None:
                    name = text
                    continue

                if re.search(INVESTOR_STATEMENT, text, re.I | re.MULTILINE) or mobile is not None:
                    return InvestorInfo(email=email, name=name, mobile=mobile or "", address="\n".join(address_lines))
                if mobile_match := re.search(r"mobile\s*:\s*([+\d]+)(?:s|$)", text, re.I):
                    mobile = mobile_match.group(1).strip()
                address_lines.append(text)

        raise CASParseError("Unable to parse investor data")

    @staticmethod
    def parse_nsdl_investor_info(page: Page) -> InvestorInfo:
        """
        Parse investor info from NSDL statement using pymupdf tables.

        Parameters
        ----------
        page : Page
            The pymupdf page object to extract information from.

        Returns
        -------
        InvestorInfo
            The extracted investor information.
        """
        statement_regex = INVESTOR_STATEMENT_DP
        start_index = end_index = None
        words = [(Rect(w[:4]), w[4]) for w in page.get_text("words", sort=True, flags=TEXTFLAGS_TEXT)]
        page_lines = [line for line, _ in CASParser.recover_lines(words)]
        for idx, line in enumerate(page_lines):
            if re.search(CAS_ID, line, re.I):
                start_index = idx
            if re.search(statement_regex, line, re.I):
                end_index = idx
                break
        if start_index is not None and end_index is not None and start_index < end_index:
            return InvestorInfo(
                name=page_lines[start_index + 1].strip(),
                address="\n".join([i.strip() for i in page_lines[start_index + 2 : end_index]]),
                email="",
                mobile="",
            )

        raise CASParseError("Unable to parse investor data")

    @staticmethod
    def recover_lines(words: list[WordData], tolerance: int = 3, vertical_factor: int = 4) -> LineData:
        """
        Reconstitute text lines on the page by using the coordinates of the single words.

        Based on `get_sorted_text` of pymupdf.

        Parameters
        ----------
        page : Page
            The pymupdf page object to extract information from.
        tolerance : int
            The tolerance level for line reconstitution (should words be joined)
        vertical_factor : int
            Factor for detecting words aligned vertically.

        Returns
        -------
        LineData
            Generator of reconstituted text lines along with their word positions.
        """
        # flags are important as they control the extraction behavior like keep "hidden text" or not
        lines: list[tuple[str, Rect, list[WordData]]] = []
        line: list[WordData] = [words[0]]  # current line
        lrect: Rect = words[0][0]  # the line's rectangle

        for wr, text in words[1:]:
            # ignore vertical elements
            if abs(wr.x1 - wr.x0) * vertical_factor < abs(wr.y1 - wr.y0):
                continue
            # if this word matches top or bottom of the line, append it
            if abs(lrect.y0 - wr.y0) <= tolerance or abs(lrect.y1 - wr.y1) <= tolerance:
                line.append((wr, text))
                lrect |= wr
            else:
                # output current line and re-initialize
                # note that we sort the words in current line first
                word_pos = sorted(line, key=lambda w: w[0].x0)
                ltext = " ".join(w[1] for w in word_pos)
                lines.append((ltext, lrect, word_pos))
                line = [(wr, text)]
                lrect = wr

        # also append last unfinished line
        word_pos = sorted(line, key=lambda w: w[0].x0)
        ltext = " ".join(w[1] for w in word_pos)
        lines.append((ltext, lrect, word_pos))

        for ltext, _, word_pos in sorted(lines, key=lambda x: (x[1].y1)):
            yield ltext, word_pos

    @staticmethod
    def get_header_positions(words: list[WordData]) -> dict[str, Rect]:
        """Get the positions of the header elements on the page."""
        positions = {}
        header_patterns = ("amount", r"Amount$"), ("units", r"Units$"), ("nav", r"NAV$"), ("balance", r"Balance$")
        for header, header_regex in header_patterns:
            matches = [w for w in words if re.search(header_regex, w[1], re.I)]
            if not matches:
                continue
            positions[header] = min(matches, key=lambda x: x[0].y0)[0]
        return positions

    def extract_statement_metadata(self) -> dict[str, Any]:
        """Extract statement metadata like file type, version, statement period and investor info."""
        page_options = {"flags": TEXTFLAGS_TEXT, "sort": True, "option": "blocks"}
        first_page_blocks = self.document.get_page_text(pno=0, **page_options)
        file_type = self.parse_file_type(first_page_blocks)
        file_version = self.parse_file_version(first_page_blocks)

        investor_info = None
        statement_regexp = DETAILED_DATE
        if file_type in (FileType.CAMS, FileType.KFINTECH):
            statement_regexp = SUMMARY_DATE if file_version == FileVersion.SUMMARY else DETAILED_DATE
            investor_info = self.parse_cams_investor_info(self.document.load_page(0))
        elif file_type in (FileType.NSDL, FileType.CDSL):
            # NSDL has no information on first page
            statement_regexp = DEMAT_STATEMENT_PERIOD
            investor_info = self.parse_nsdl_investor_info(self.document.load_page(1))
            first_page_blocks = self.document.get_page_text(pno=1, **page_options)

        statement_period = None
        for block in first_page_blocks:
            block_text = block[4].strip()
            if m := re.search(statement_regexp, block_text, MULTI_TEXT_FLAGS):
                from_date, to_date = m.groups()
                statement_period = StatementPeriod(from_=from_date, to=to_date)
                break

        return {
            "file_type": file_type,
            "file_version": file_version,
            "statement_period": statement_period,
            "investor_info": investor_info,
        }

    def parse_pdf(self) -> PartialCASData:
        """
        Parse CAS pdf and returns line data.

        Returns
        -------
        PartialCasData which includes investor info, file type, version and parsed text lines (as much as close to original layout)
        """

        metadata = self.extract_statement_metadata()
        document_data: DocumentData = []
        for page_num, page in enumerate(self.document):
            if metadata["file_type"] == FileType.NSDL and page_num == 0:
                # No useful data in first page of NSDL doc
                continue
            words = [(Rect(w[:4]), w[4]) for w in page.get_text("words", sort=True, flags=TEXTFLAGS_TEXT)]
            if not words:
                continue

            document_data.append(
                PageData(lines_data=self.recover_lines(words), headers_data=self.get_header_positions(words))
            )

        return PartialCASData(document_data=document_data, **metadata)
