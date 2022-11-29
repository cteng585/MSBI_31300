import os
import re

from enum import Enum
from typing import Optional

import docx

from charset_normalizer import from_bytes
from tika import parser

os.environ["TIKA_CLIENT_ONLY"] = "False"
os.environ["TIKA_LOG_PATH"] = "resources/tika/logs/"
os.environ["TIKA_SERVER_ENDPOINT"] = "localhost"
os.environ["TIKA_SERVER_JAR"] = "file:////tika-server.jar"
os.environ["TIKA_VERSION"] = "1.24"


class FileType(Enum):
    DOC = "doc"
    DOCX = "docx"
    PDF = "pdf"
    TXT = "txt"
    UNSUPPORTED = "unsupported"


def decode_text(encoded_text: bytes) -> str:
    """Detect the encoding of a string and decode to default str encoding

    :param encoded_text: byte encoded text
    :return: decoded text
    """
    return str(from_bytes(encoded_text).best())


def get_file_type(file_path: str) -> FileType:
    """Get the file format of the resume based on the file extension

    :param file_path: file path to resume
    :return: a FileType object corresponding to the resume's file format
    """
    if re.search(r".doc$", file_path):
        return FileType.DOC
    elif re.search(r".docx$", file_path):
        return FileType.DOCX
    elif re.search(r".pdf$", file_path):
        return FileType.PDF
    elif re.search(r".txt$", file_path):
        return FileType.TXT
    else:
        return FileType.UNSUPPORTED


def resume_parser(file_path: str) -> Optional[str]:
    """Get the raw text of the input resume

    :param file_path: file path to resume
    :return: detected strings/words in the resume
    """

    # detect the file type based on the extension
    file_type = get_file_type(file_path)

    # parse word doc files
    if file_type is FileType.DOC or file_type is FileType.DOCX:
        word_doc = docx.Document(file_path)
        return "\n".join([paragraph.text for paragraph in word_doc.paragraphs])

    # parse pdf files
    elif file_type is FileType.PDF:
        parsed = parser.from_file(file_path)
        return parsed["content"]

    # parse txt files
    elif file_type is FileType.TXT:
        with open(file_path, "rb") as infile:
            byte_text = infile.read()
        return decode_text(byte_text)

    # return None if file type isn't supported
    elif file_type is FileType.UNSUPPORTED:
        return None
