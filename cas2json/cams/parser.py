import re

from pymupdf import TEXTFLAGS_TEXT, Page, Rect

from cas2json.cams.types import CAMSPageData
from cas2json.exceptions import CASParseError
from cas2json.flags import MULTI_TEXT_FLAGS
from cas2json.parser import BaseCASParser
from cas2json.patterns import CAS_TYPE, DETAILED_DATE, INVESTOR_MAIL, INVESTOR_STATEMENT, SUMMARY_DATE
from cas2json.types import (
    CASMetaData,
    CASParsedData,
    DocumentData,
    FileType,
    FileVersion,
    InvestorInfo,
    StatementPeriod,
    WordData,
)


class CAMSParser(BaseCASParser):
    @staticmethod
    def parse_investor_info(page: Page) -> InvestorInfo:
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
    def parse_file_version(page_blocks: list[tuple]) -> FileVersion:
        """Detect the type of CAMS statement (detailed or summary) from the parsed lines."""
        for block in page_blocks:
            if m := re.search(CAS_TYPE, block[4].strip(), MULTI_TEXT_FLAGS):
                match = m.group(1).lower().strip()
                if match == "statement":
                    return FileVersion.DETAILED
                elif match == "summary":
                    return FileVersion.SUMMARY
        return FileVersion.UNKNOWN

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

    def extract_statement_metadata(self) -> CASMetaData:
        """Extract statement metadata like file type, version, statement period and investor info."""
        first_page_blocks = self.document.get_page_text(pno=0, flags=TEXTFLAGS_TEXT, sort=True, option="blocks")
        file_type = self.parse_file_type(first_page_blocks)
        if file_type not in [FileType.CAMS, FileType.KFINTECH]:
            raise CASParseError("Not a valid CAMS file")

        file_version = self.parse_file_version(first_page_blocks)
        statement_regexp = SUMMARY_DATE if file_version == FileVersion.SUMMARY else DETAILED_DATE
        investor_info = self.parse_investor_info(self.document.load_page(0))

        statement_period = None
        for block in first_page_blocks:
            block_text = block[4].strip()
            if m := re.search(statement_regexp, block_text, MULTI_TEXT_FLAGS):
                from_date, to_date = m.groups()
                statement_period = StatementPeriod(from_=from_date, to=to_date)
                break

        return CASMetaData(
            file_type=file_type,
            file_version=file_version,
            statement_period=statement_period,
            investor_info=investor_info,
        )

    def parse_pdf(self) -> CASParsedData:
        """
        Parse CAS pdf and returns line data.

        Returns
        -------
        PartialCasData which includes investor info, file type, version and parsed text lines (as much as close to original layout)
        """

        metadata: CASMetaData = self.extract_statement_metadata()
        document_data: DocumentData[CAMSPageData] = []
        for page_num, page in enumerate(self.document):
            if metadata.file_type == FileType.NSDL and page_num == 0:
                # No useful data in first page of NSDL doc
                continue
            words = [(Rect(w[:4]), w[4]) for w in page.get_text("words", sort=True, flags=TEXTFLAGS_TEXT)]
            if not words:
                continue

            document_data.append(
                CAMSPageData(lines_data=self.recover_lines(words), headers_data=self.get_header_positions(words))
            )

        return CASParsedData(document_data=document_data, metadata=metadata)
