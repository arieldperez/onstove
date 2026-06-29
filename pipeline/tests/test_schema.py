"""Schema, sweep-planning and validation tests. Stdlib unittest only."""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline" / "src"))

from onstove_pipeline import schema, sweep, validate  # noqa: E402


class TestSchema(unittest.TestCase):
    def test_tiers_present(self):
        self.assertIn("country_summary", schema.TIERS)
        self.assertIn("cell_allocation", schema.TIERS)

    def test_json_schema_builds(self):
        for tier in schema.TIERS:
            js = schema.to_json_schema(tier)
            self.assertEqual(js["type"], "object")
            self.assertTrue(js["required"])
            self.assertIn("properties", js)

    def test_generated_files_match_module(self):
        # the committed .schema.json must equal what the module generates
        import json
        for tier in schema.TIERS:
            path = REPO / "pipeline" / "schema" / f"{tier}.schema.json"
            on_disk = json.loads(path.read_text())
            self.assertEqual(on_disk, schema.to_json_schema(tier),
                             f"{tier}.schema.json is stale; regenerate it")

    def test_validate_rows_accepts_good_row(self):
        good = {f.name: _dummy(f) for f in schema.CELL_ALLOCATION_FIELDS}
        self.assertEqual(schema.validate_rows("cell_allocation", [good]), [])

    def test_validate_rows_flags_missing_and_bad_type(self):
        bad = {f.name: _dummy(f) for f in schema.CELL_ALLOCATION_FIELDS}
        del bad["lon"]                # missing required
        bad["population"] = "lots"    # wrong type
        errors = schema.validate_rows("cell_allocation", [bad])
        self.assertTrue(any("lon" in e for e in errors))
        self.assertTrue(any("population" in e for e in errors))

    def test_validate_rows_enforces_enum(self):
        good = {f.name: _dummy(f) for f in schema.CELL_ALLOCATION_FIELDS}
        good["settlement_type"] = "suburban"  # not in enum
        errors = schema.validate_rows("cell_allocation", [good])
        self.assertTrue(any("settlement_type" in e for e in errors))

    def test_nullable_respected(self):
        good = {f.name: _dummy(f) for f in schema.COUNTRY_SUMMARY_FIELDS}
        good["mac_usd_per_tco2"] = None       # nullable -> ok
        self.assertEqual(schema.validate_rows("country_summary", [good]), [])
        good["discount_rate"] = None          # not nullable -> error
        self.assertTrue(schema.validate_rows("country_summary", [good]))


class TestSweepPlan(unittest.TestCase):
    def _cfg(self):
        return {
            "country": {"name": "Tanzania", "iso3": "TZA"},
            "provenance": {"validation_status": "validated"},
            "paths": {"output_dir": "outputs/TZA"},
            "technologies": ["LPG"],
            "assumptions": {"discount_rate": 0.10, "carbon_price_usd_per_tco2": 30,
                            "fnrb": 0.51, "fnrb_source": "TOOL33_national"},
            "sensitivity": {
                "axes": {"discount_rate": [0.05, 0.10, 0.15],
                         "carbon_price_usd_per_tco2": [5, 30, 50]},
                "scenarios": [{"id": "high", "label": "High", "overrides": {"carbon_price_usd_per_tco2": 50}}],
            },
        }

    def test_plan_includes_base_first(self):
        runs = sweep.plan(self._cfg())
        self.assertEqual(runs[0].kind, "base")

    def test_plan_dedupes_base_value(self):
        runs = sweep.plan(self._cfg())
        ids = [r.run_id for r in runs]
        # discount_rate=0.10 and carbon=30 equal base -> excluded
        self.assertNotIn("axis__discount_rate__0p1", ids)
        self.assertIn("axis__discount_rate__0p05", ids)
        self.assertIn("scenario__high", ids)

    def test_apply_overrides_is_deep(self):
        cfg = self._cfg()
        new = sweep.apply_overrides(cfg, {"discount_rate": 0.2})
        self.assertEqual(new["assumptions"]["discount_rate"], 0.2)
        self.assertEqual(cfg["assumptions"]["discount_rate"], 0.10)  # original untouched


class TestValidation(unittest.TestCase):
    def test_compare_pass_and_fail(self):
        modelled = {"population_reached": 102.0, "deaths_avoided": 95.0}
        published = {"population_reached": 100.0, "deaths_avoided": 100.0}
        report = validate.compare(modelled, published, "Tanzania", "TZA",
                                  "src", tolerance=0.10)
        self.assertTrue(report.passed)  # both within 10%
        report2 = validate.compare(modelled, published, "Tanzania", "TZA",
                                   "src", tolerance=0.01)
        self.assertFalse(report2.passed)  # 2% and 5% exceed 1%

    def test_report_markdown_renders(self):
        report = validate.compare({"deaths_avoided": 100.0},
                                  {"deaths_avoided": 100.0},
                                  "Tanzania", "TZA", "src")
        md = report.to_markdown()
        self.assertIn("Validation report", md)
        self.assertIn("PASS", md)


def _dummy(f: schema.Field):
    if f.enum:
        return f.enum[0]
    return {"string": "x", "float": 1.0, "int": 1, "bool": True}[f.dtype]


if __name__ == "__main__":
    unittest.main()
