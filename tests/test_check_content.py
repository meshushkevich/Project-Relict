"""Проверки ошибок, которые могут попасть в PR с дополнением истории."""

from pathlib import Path
import tempfile
import unittest

from scripts.check_content import check


class ContentChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.write("src/index.md", "# История\n")
        self.write("src/SUMMARY.md", "[История](index.md)\n")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def incident(self, name="007-case.md", status="draft", identifier="REL-INC-007", when="TBD"):
        self.write("src/Incidents/" + name, f'---\nid: {identifier}\ntitle: "Дело"\ndate: {when}\nlocation: "Озёрск-9"\nstatus: {status}\n---\n\n# Дело\n')

    def test_unpublished_draft_is_valid(self):
        self.incident()
        self.assertEqual(check(self.root), [])

    def test_published_draft_is_rejected(self):
        self.incident()
        self.write("src/SUMMARY.md", "- [Дело](Incidents/007-case.md)\n")
        self.assertTrue(any("черновик" in error for error in check(self.root)))

    def test_canon_can_be_included(self):
        self.incident(status="canon", when="2005-03-01")
        self.write("src/SUMMARY.md", "- [Дело](Incidents/007-case.md)\n")
        self.assertEqual(check(self.root), [])

    def test_duplicate_identifier_is_rejected(self):
        self.incident()
        self.incident("008-case.md")
        self.assertTrue(any("уже занят" in error for error in check(self.root)))

    def test_invalid_date_is_rejected(self):
        self.incident(when="2005-XX-XX")
        self.assertTrue(check(self.root))

    def test_duplicate_status_is_rejected(self):
        self.write("src/Creatures/case.md", '---\ntitle: Существо\nstatus: canon\nstatus: draft\n---\n')
        self.assertTrue(any("повторяющиеся ключи" in error for error in check(self.root)))

    def test_missing_link_is_rejected(self):
        self.write("src/index.md", "[Дело](Incidents/absent.md)\n")
        self.assertTrue(any("нет цели ссылки" in error for error in check(self.root)))

    def test_missing_html_anchor_is_rejected(self):
        self.write("book/index.html", '<a href="case.html#missing">Дело</a>')
        self.write("book/case.html", '<h1 id="case">Дело</h1>')
        self.assertTrue(any("нет якоря" in error for error in check(self.root, Path("book"))))

    def test_valid_html_anchor_is_accepted(self):
        self.write("book/index.html", '<a href="case.html#case">Дело</a>')
        self.write("book/case.html", '<h1 id="case">Дело</h1>')
        self.assertEqual(check(self.root, Path("book")), [])


if __name__ == "__main__":
    unittest.main()
