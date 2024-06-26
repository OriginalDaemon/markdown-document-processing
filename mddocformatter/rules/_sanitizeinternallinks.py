from __future__ import annotations

import re
import logging

from urllib.parse import unquote
from ._base import document_rule
from ._utils import get_next_match, replace_span, format_document_markdown_link
from .._consts import regex_markdown_link, regex_markdown_link_with_subsection, Passes

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .._processing import ProcessingContext
    from .._document import Document


logger = logging.getLogger(__name__)


def _get_document_from_link(context: ProcessingContext, document: Document, link: str) -> Document | None:
    result = context.get_document((document.input_path.parent / link).resolve())
    if not result:
        result = context.get_document((context.settings.root_directory / link).resolve())
    return result


def _get_next_link_match(document: Document, pointer: int) -> Tuple[bool, int, int, str, str, str]:
    match, start, end = get_next_match(document, pointer, regex_markdown_link_with_subsection)
    if match:
        return True, start, end, match.group(1), match.group(2), match.group(3)
    else:
        match, start, end = get_next_match(document, pointer, regex_markdown_link)
        if match:
            return True, start, end, match.group(1), match.group(2), ""
        else:
            return False, 0, 0, "", "", ""


def _process_section_reference(section: str, linked_document: Document):
    if section:
        # find the actual linked section and recreate teh section reference.
        regex_section_part = section.replace("-", "[ -]")
        section_regex = re.compile(r"#+\s*(" + regex_section_part + ")", re.IGNORECASE)
        for line in linked_document.contents.split("\n"):
            result = re.search(section_regex, line)
            if result:
                section = result.group(1)
                break
    return section


@document_rule("*.md", Passes.LINK_UPDATING)
def santize_internal_links(context: ProcessingContext, document: Document):
    """
    Find any "internal" markdown links and make sure they use the form ()[<relative_path to item>]
    :param context: The ProcessingContext.
    :param document: The document being processed.
    """
    pointer = 0
    while pointer < len(document.contents):
        success, start, pointer, text, path, section = _get_next_link_match(document, pointer)
        if not success:
            break
        section, path = unquote(section), unquote(path)
        linked_document = _get_document_from_link(context, document, path)
        if linked_document is not None:
            section = _process_section_reference(section, linked_document)
            reformatted_link = format_document_markdown_link(text, document, linked_document, section)
            document.contents, pointer = replace_span(document, start, pointer, reformatted_link)
