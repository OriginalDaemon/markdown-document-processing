from __future__ import annotations

import logging

from ._consts import Passes, FunctionMacro
from ._document import Document
from .loading import load_document, save_document
from typing import Dict, List, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:  # pragma: no cover
    from .rules import DocumentRule


logger = logging.getLogger(__name__)


class ProcessingSettings(object):
    def __init__(
        self,
        root_directory: Path = Path("./"),
        target_directory: Path = Path("./"),
        version_name: str = "",
        rule_set: List[DocumentRule] | None = None,
        const_macros: Dict[str, str] | None = None,
        function_macros: Dict[str, FunctionMacro] | None = None,
    ):
        """
        Settings to use when processing a document.
        :param root_directory: The root of the documentation tree.
        :param target_directory: The target_path directory under which to put the newly processed documents - can be
                                 the same as the root directory for in-place processing.
        :param version_name: The name of the version of the documentation, mostly used for confluence naming. Usually
                             develop or main.
        :param rule_set: The rules to run on each doc.
        :param const_macros: A table of const value macros.
        :param function_macros: A table of function macros which take 0 or more strings as args and returns a string.
        """
        self.root_directory = root_directory
        self.target_directory = target_directory
        self.rules = rule_set or list()
        self.const_macros: Dict[str, str] = const_macros or dict()
        self.function_macros: Dict[str, FunctionMacro] = function_macros or dict()
        self.version_name = version_name


class ProcessingContext(object):
    def __init__(self, settings: ProcessingSettings):
        """
        A context under which all document processing jobs are ran. This owns the document data throughout out the
        document processing.
        :param settings: The settings used when processing the document.
        """
        self.settings = settings
        self.documents: Dict[Path, Document] = {}

    def add_document(self, document: Document | Path):
        """
        Add a document to be processed.
        :document: The document to add.
        """
        path = document if isinstance(document, Path) else document.input_path
        document = document if isinstance(document, Document) else load_document(document)
        if path.is_relative_to(self.settings.root_directory):
            self.documents[document.input_path] = document
        else:
            raise ValueError(f"All documents must be under the root directory, got: {path}")

    def get_document(self, path: Path) -> Document | None:
        """
        Find a document in the documentation set being processed in this context.
        :return: The document or None if the document can't be found.
        """
        doc = self.documents.get(path, None)
        if doc is None:
            doc = self.documents.get(self.settings.root_directory / path, None)
        return doc

    # noinspection DuplicatedCode
    def get_document_by_name(self, name: str) -> Document | None:
        """
        Find a document by name. Finds the first one, which isn't guaranteed to be unique.
        :param name: The name of the document.
        :return: The document or None if no document with the given name could be found.
        """
        # fullname, case sensitive
        for doc in self.documents.values():
            if name == doc.input_path.name:
                return doc
        # fullname, case insensitive
        for doc in self.documents.values():
            if name == doc.input_path.name.lower():
                return doc
        # sans extension, case sensitive
        for doc in self.documents.values():
            if name == doc.input_path.stem:
                return doc
        # sans extension, case insensitive
        for doc in self.documents.values():
            if name == doc.input_path.stem.lower():
                return doc
        # drop the confluence style prefix, fullname, case sensitive
        for doc in self.documents.values():
            if name == doc.input_path.name.split(" - ")[-1]:
                return doc
        # drop the confluence style prefix, fullname, case insensitive
        for doc in self.documents.values():
            if name == doc.input_path.name.lower().split(" - ")[-1]:
                return doc
        # drop the confluence style prefix, sans extension, case sensitive
        for doc in self.documents.values():
            if name == doc.input_path.stem.split(" - ")[-1]:
                return doc
        # drop the confluence style prefix, sans extension, case insensitive
        for doc in self.documents.values():
            if name == doc.input_path.stem.lower().split(" - ")[-1]:
                return doc
        return None

    def run(self):
        """
        Run the documentation processing.
        """
        for index in Passes:
            for document in self.documents.values():
                for rules in filter(lambda x: x.pass_index == index, self.settings.rules):
                    rules(self, document)

    def save(self):
        """
        Save the current state of the documentation to the target locations - usually called after "run".
        """
        for document in self.documents.values():
            save_document(document)


def _process_docs(
    input_dir: Path,
    output_dir: Path,
    rule_set: list,
    const_macros: Dict[str, str] | None = None,
    function_macros: Dict[str, FunctionMacro] | None = None,
    version_name: str = "",
):
    """Create a context, find and process the docs, and :return: the context."""
    settings = ProcessingSettings(input_dir, output_dir, version_name, rule_set, const_macros, function_macros)
    logging.info("Configuring...")
    context = ProcessingContext(settings)
    logging.info(f"Discovering documentation in {input_dir}...")
    for file_path in input_dir.glob("**/*.*"):
        context.add_document(file_path)
    docs_list = "\n    - ".join([str(x) for x in context.documents.keys()])
    logging.info(f"Files found: \n    - {docs_list}")
    logging.info("Processing...")
    context.run()
    return context


def process_docs(
    input_dir: Path,
    output_dir: Path,
    rule_set: list,
    const_macros: Dict[str, str] | None = None,
    function_macros: Dict[str, FunctionMacro] | None = None,
    version_name: str = "",
) -> bool:
    """
    Process all the documentation in the input_dir and save the results to the output_dir. Make the input & output dirs
    the same to overwrite the documentation in place.
    :param input_dir: The root of the documentation tree.
    :param output_dir: The target_path directory under which to put the newly processed documents - can be
                             the same as the root directory for in-place processing.
    :param version_name: The name of the version of the documentation, mostly used for confluence naming. Usually
                         develop or main.
    :param rule_set: The rules to run on each doc.
    :param const_macros: A table of const value macros.
    :param function_macros: A table of function macros which take 0 or more strings as args and returns a string.
    :return: True if successful.
    """
    context = _process_docs(input_dir, output_dir, rule_set, const_macros, function_macros, version_name)
    logging.info("Saving...")
    docs_list = "\n    - ".join([str(x.target_path) for x in context.documents.values()])
    logging.info(f"Saving documents: \n    - {docs_list}")
    context.save()
    logging.info("Complete.")
    return True


def validate_docs(
    input_dir: Path,
    rule_set: list,
    const_macros: Dict[str, str] | None = None,
    function_macros: Dict[str, FunctionMacro] | None = None,
    version_name: str = "",
) -> bool:
    """
    Process all the documentation in the input_dir and save the results to the output_dir. Make the input & output dirs
    the same to overwrite the documentation in place.
    :param input_dir: The root of the documentation tree.
    :param version_name: The name of the version of the documentation, mostly used for confluence naming. Usually
                         develop or main.
    :param rule_set: The rules to run on each doc.
    :param const_macros: A table of const value macros.
    :param function_macros: A table of function macros which take 0 or more strings as args and returns a string.
    :return: True if successful.
    """
    context = _process_docs(input_dir, input_dir, rule_set, const_macros, function_macros, version_name)
    logging.info("Validating...")
    valid = True
    for doc in context.documents.values():
        if not doc.unchanged:
            valid = False
            s = f"Document {doc.input_path} would require changes to fit the style.\n"
            s += "    " + "\n    ".join(doc.changes().split("\n"))
            logging.warning(s)
    status = "valid" if valid else "invalid"
    logging.info(f"Complete. Documentation is {status}.")
    return valid
