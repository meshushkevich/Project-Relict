#!/usr/bin/env python3
"""Проверки формата документов и ссылок; сюжетные решения остаются за автором."""

import argparse
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

import yaml


DOCUMENT_DIRS = ("Chapters", "Incidents", "Creatures", "Anomalies")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---(?:\n|$)", re.DOTALL)


class UniqueKeysLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        if len(keys) != len(set(keys)):
            raise ValueError("повторяющиеся ключи YAML")
        return super().construct_mapping(node, deep=deep)


def metadata(path):
    match = FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("отсутствует YAML front matter")
    result = yaml.load(match[1], Loader=UniqueKeysLoader)
    if not isinstance(result, dict):
        raise ValueError("YAML должен содержать поля документа")
    return result


def local_target(parent, target):
    url = urlsplit(target)
    if url.scheme or url.netloc or not url.path:
        return None
    return parent / unquote(url.path)


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value:
                self.links.append(value)
            if key == "id" and value:
                self.ids.add(value)


def check(root, book_dir=None):
    root = Path(root).resolve()
    source = root / "src"
    errors, documents, identifiers = [], {}, {}
    for section in DOCUMENT_DIRS:
        for path in sorted((source / section).rglob("*.md")):
            if path.name in ("README.md", "index.md"):
                continue
            try:
                fields = metadata(path)
                if not isinstance(fields.get("title"), str) or not fields["title"].strip():
                    raise ValueError("нужно непустое поле title")
                if fields.get("status") not in ("draft", "canon"):
                    raise ValueError("status должен быть draft или canon")
                if section == "Incidents":
                    identifier = fields.get("id")
                    if not isinstance(identifier, str) or not re.fullmatch(r"REL-INC-\d{3,}", identifier):
                        raise ValueError("нужен идентификатор REL-INC-NNN")
                    if identifier in identifiers:
                        raise ValueError(f"номер {identifier} уже занят: {identifiers[identifier]}")
                    identifiers[identifier] = path.relative_to(root)
                    if not isinstance(fields.get("location"), str) or not fields["location"].strip():
                        raise ValueError("нужно непустое поле location")
                    value = fields.get("date")
                    if value != "TBD" and type(value) is not date:
                        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                            raise ValueError("date должна быть YYYY-MM-DD или TBD")
                        date.fromisoformat(value)
                documents[path.resolve()] = fields
            except (ValueError, TypeError, yaml.YAMLError) as error:
                errors.append(f"{path.relative_to(root)}: {error}")

    summary = source / "SUMMARY.md"
    if not summary.is_file():
        errors.append("нет src/SUMMARY.md")
    else:
        for target in LINK.findall(summary.read_text(encoding="utf-8")):
            path = local_target(source, target)
            if path is None:
                continue
            path = path.resolve()
            if not path.is_relative_to(source):
                errors.append(f"SUMMARY.md: глава вне src/: {target}")
            elif path in documents and documents[path]["status"] != "canon":
                errors.append(f"SUMMARY.md: черновик включён в книгу: {target}")

    paths = [*source.rglob("*.md"), *root.glob("templates/*.md")]
    paths += [root / name for name in ("README.md", "AGENTS.md", "CONTRIBUTING.md")]
    paths += list((root / ".github").glob("*.md"))
    paths += list((root / ".agents/skills").glob("relict-*/SKILL.md"))
    for path in paths:
        if not path.is_file():
            continue
        for target in LINK.findall(path.read_text(encoding="utf-8")):
            destination = local_target(path.parent, target)
            if destination is not None and not destination.exists():
                errors.append(f"{path.relative_to(root)}: нет цели ссылки {target}")

    if book_dir is not None:
        book = (root / book_dir).resolve()
        pages = {}
        if not (book / "index.html").is_file():
            errors.append(f"нет собранной книги в {book_dir}")
        for path in book.rglob("*.html"):
            page = HTMLLinks()
            page.feed(path.read_text(encoding="utf-8"))
            pages[path.resolve()] = page
        for path, page in pages.items():
            for target in page.links:
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    continue
                if url.path.startswith("/"):
                    destination = book / unquote(url.path.lstrip("/"))
                else:
                    destination = path.parent / unquote(url.path) if url.path else path
                destination = destination.resolve()
                if not destination.exists():
                    errors.append(f"{path.relative_to(book)}: нет цели ссылки {target}")
                elif url.fragment and destination in pages and unquote(url.fragment) not in pages[destination].ids:
                    errors.append(f"{path.relative_to(book)}: нет якоря {target}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--book-dir", type=Path)
    args = parser.parse_args()
    errors = check(args.root, args.book_dir)
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("Проверки документов и ссылок пройдены.")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
