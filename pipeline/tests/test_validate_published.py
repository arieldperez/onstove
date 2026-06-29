"""Tests for the Phase 2 published-summary comparator. Stdlib only."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline" / "scripts"))
sys.path.insert(0, str(REPO / "pipeline" / "src"))

import validate_against_published as vap  # noqa: E402


def _write(text: str) -> str:
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    fh.write(text)
    fh.close()
    return fh.name


class TestPublishedParsing(unittest.TestCase):
    def test_published_metrics_units(self):
        # mirrors OnStove summary() pretty columns (Million / MUSD)
        csv_text = (
            "Max benefit technology,Population (Million),Reduced emissions (Mton CO2eq),"
            "Total deaths avoided (pp/yr),Total net benefit (MUSD)\n"
            "LPG,10.0,2.5,1000,500\n"
            "total,25.0,6.0,3000,1200\n"
        )
        m = vap.published_metrics(_write(csv_text), technology="total")
        self.assertAlmostEqual(m["population_reached"], 25.0e6)
        self.assertAlmostEqual(m["total_tco2_mt_yr"], 6.0)
        self.assertAlmostEqual(m["deaths_avoided"], 3000.0)
        self.assertAlmostEqual(m["total_net_benefit_usd"], 1200e6)

    def test_modelled_metrics_are_contract_native(self):
        # our Phase 4 export already uses contract column names + absolute units
        csv_text = (
            "country,iso3,scenario_id,technology,households_reached,population_reached,"
            "total_tco2_mt_yr,deaths_avoided,total_net_benefit_usd\n"
            "Tanzania,TZA,base,total,5e6,25000000,6.0,3000,1200000000\n"
        )
        m = vap.modelled_metrics(_write(csv_text), technology="total")
        self.assertAlmostEqual(m["population_reached"], 25_000_000)
        self.assertAlmostEqual(m["total_net_benefit_usd"], 1.2e9)

    def test_end_to_end_pass(self):
        published = _write(
            "Max benefit technology,Population (Million),Total net benefit (MUSD)\n"
            "total,25.0,1200\n")
        modelled = _write(
            "technology,population_reached,total_net_benefit_usd\n"
            "total,25500000,1230000000\n")
        pub = vap.published_metrics(published)
        mod = vap.modelled_metrics(modelled)
        from onstove_pipeline import validate
        report = validate.compare(mod, pub, "Tanzania", "TZA", "test", tolerance=0.10)
        self.assertTrue(report.passed)  # 2% and 2.5% within 10%


if __name__ == "__main__":
    unittest.main()
