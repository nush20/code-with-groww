import unittest

from backend.app.sector_metadata import sector_for


class SectorMetadataTests(unittest.TestCase):
    def test_provider_metadata_takes_precedence(self):
        self.assertEqual(sector_for("INFY", "Information Technology"), "Information Technology")

    def test_known_symbol_uses_central_fallback(self):
        self.assertEqual(sector_for("TATASTEEL"), "Metals")

    def test_unknown_symbol_is_honest(self):
        self.assertEqual(sector_for("UNKNOWN"), "Other")


if __name__ == "__main__":
    unittest.main()
