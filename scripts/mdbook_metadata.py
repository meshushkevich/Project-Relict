#!/usr/bin/env python3
"""Подготовить метаданные и ссылки книги, не публикуя черновые дела."""

import json
from pathlib import PurePosixPath
import posixpath
import re
import sys
from urllib.parse import unquote, urlsplit


FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---(?:\n|$)", re.DOTALL)
CANON_STATUS = re.compile(r"^status:[ \t]*(?:canon|'canon'|\"canon\")[ \t]*(?:#.*)?$", re.MULTILINE)
DOCUMENT_DIRS = {"Incidents", "Creatures", "Anomalies"}


def chapters(items):
    for item in items:
        chapter = item.get("Chapter")
        if chapter is not None:
            yield chapter
            yield from chapters(chapter.get("sub_items", []))


def appendix_links(content, path, published):
    def replace(match):
        label, target = match.groups()
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path.endswith(".md"):
            return match[0]
        destination = posixpath.normpath((path.parent / unquote(url.path)).as_posix())
        return match[0] if destination in published else label

    return re.sub(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)", replace, content)


def process_items(items, published):
    for item in items:
        chapter = item.get("Chapter")
        if chapter is None:
            continue
        path = PurePosixPath(chapter.get("source_path") or chapter.get("path") or "")
        document = bool(path.parts) and path.parts[0] in DOCUMENT_DIRS and path.name != "index.md"
        content = chapter["content"].replace("\r\n", "\n")
        metadata = FRONT_MATTER.match(content)
        if document and metadata is None:
            raise ValueError(f"{path}: у документа отсутствуют YAML-метаданные")
        if metadata:
            if not CANON_STATUS.search(metadata[1]):
                raise ValueError(f"{path}: в читательскую книгу допускается только status: canon")
            chapter["content"] = content[metadata.end():].lstrip("\n")
        if path.parts and path.parts[0] == "Spoilers":
            chapter["content"] = appendix_links(chapter["content"], path, published)
        process_items(chapter.get("sub_items", []), published)


def main():
    if len(sys.argv) > 1:
        return 0 if sys.argv[1:] == ["supports", "html"] else 1
    try:
        _context, book = json.load(sys.stdin)
        published = {
            path
            for chapter in chapters(book["items"])
            for path in (chapter.get("source_path"), chapter.get("path"))
            if path
        }
        process_items(book["items"], published)
    except (ValueError, KeyError, TypeError) as error:
        print(f"relict-metadata: {error}", file=sys.stderr)
        return 1
    json.dump(book, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
