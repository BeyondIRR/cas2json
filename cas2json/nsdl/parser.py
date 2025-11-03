import re

from pymupdf import TEXTFLAGS_TEXT, Page, Rect

from cas2json.exceptions import CASParseError
from cas2json.flags import MULTI_TEXT_FLAGS
from cas2json.parser import BaseCASParser
from cas2json.patterns import CAS_ID, DEMAT_STATEMENT_PERIOD, INVESTOR_STATEMENT_DP
from cas2json.types import CASMetaData, FileType, FileVersion, InvestorInfo, StatementPeriod


class NSDLParser(BaseCASParser):
    @staticmethod
    def parse_investor_info(page: Page) -> InvestorInfo:
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
        page_lines = [line for line, _ in BaseCASParser.recover_lines(words)]
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

    def extract_statement_metadata(self) -> CASMetaData:
        """Extract statement metadata like file type, version, statement period and investor info."""
        page_options = {"flags": TEXTFLAGS_TEXT, "sort": True, "option": "blocks"}
        first_page_blocks = self.document.get_page_text(pno=0, **page_options)
        file_type = self.parse_file_type(first_page_blocks)
        if file_type != FileType.NSDL:
            raise CASParseError("Not a valid NSDL file")

        statement_period = None
        for block in self.document.get_page_text(pno=1, **page_options):
            block_text = block[4].strip()
            if m := re.search(DEMAT_STATEMENT_PERIOD, block_text, MULTI_TEXT_FLAGS):
                from_date, to_date = m.groups()
                statement_period = StatementPeriod(from_=from_date, to=to_date)
                break

        investor_info = self.parse_investor_info(self.document.load_page(1))
        return CASMetaData(
            file_type=file_type,
            file_version=FileVersion.DETAILED,
            statement_period=statement_period,
            investor_info=investor_info,
        )
