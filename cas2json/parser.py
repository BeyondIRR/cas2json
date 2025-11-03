import io
import re

from pymupdf import TEXTFLAGS_TEXT, Document, Page, Rect

from cas2json.enums import FileType
from cas2json.exceptions import CASParseError, IncorrectPasswordError
from cas2json.types import BasePageData, CASMetaData, CASParsedData, DocumentData, InvestorInfo, LineData, WordData


class BaseCASParser:
    __slots__ = ("document",)

    def __init__(self, filename: str | io.IOBase, password: str | None = None) -> None:
        self.document: Document = self._get_document(filename, password)

    @staticmethod
    def _get_document(filename: str | io.IOBase, password: str | None) -> Document:
        """Open and return pymupdf Document instance."""
        if isinstance(filename, str):
            with open(filename, "rb") as f:
                data = f.read()
        elif hasattr(filename, "read") and hasattr(filename, "close"):  # file-like object
            filename.seek(0)
            data = filename.read()
        else:
            raise CASParseError("Invalid input. filename should be a string or a file like object")

        try:
            doc = Document(stream=data, filetype="pdf")
        except Exception as e:
            raise CASParseError(f"Unhandled error while opening file :: {e!s}") from e

        if doc.needs_pass and not doc.authenticate(password):
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
    def parse_investor_info(page: Page) -> InvestorInfo:
        """To be implemented for investor info parsing by respective subclasses."""
        ...

    def extract_statement_metadata(self) -> CASMetaData:
        """To be implemented for statement metadata extraction by respective subclasses."""
        ...

    def find_in_doc_page(self, text: str, page_no: int = 0) -> bool:
        """Check if the given text is present in the document's page."""
        page = self.document.load_page(page_no)
        return page.search_for(text) != []

    def parse_pdf(self) -> CASParsedData:
        """
        Parse CAS pdf and returns line data.

        Returns
        -------
        CASParsedData which includes investor info, file type, version and parsed text lines (as much as close to original layout)
        """

        metadata: CASMetaData = self.extract_statement_metadata()
        document_data: DocumentData[BasePageData] = []
        for page_num, page in enumerate(self.document):
            if metadata.file_type == FileType.NSDL and page_num == 0:
                # No useful data in first page of NSDL doc
                continue
            words = [(Rect(w[:4]), w[4]) for w in page.get_text("words", sort=True, flags=TEXTFLAGS_TEXT)]
            if not words:
                continue

            document_data.append(BasePageData(lines_data=self.recover_lines(words)))

        return CASParsedData(document_data=document_data, metadata=metadata)
