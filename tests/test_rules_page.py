"""docs/index.html (the GitHub Pages rules page) is generated from the bot's
rules. Fail if a rule changed without regenerating the page."""
import importlib.util
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_rules_page", _ROOT / "scripts" / "build_rules_page.py")
build_rules_page = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_rules_page)


class TestRulesPage(unittest.TestCase):
    def test_page_matches_the_rules(self):
        committed = (_ROOT / "docs" / "index.html").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(
            committed, build_rules_page.render(),
            "docs/index.html is out of date with the rules. Run: python scripts/build_rules_page.py",
        )

    def test_every_qualifier_appears_on_the_page(self):
        page = build_rules_page.render()
        for qualifier in build_rules_page.rules.QUALIFIERS:
            with self.subTest(qualifier=qualifier.label):
                self.assertIn(build_rules_page._e(qualifier.events.name), page)
                for _, url in qualifier.events.links:
                    self.assertIn(url, page)


if __name__ == "__main__":
    unittest.main()
