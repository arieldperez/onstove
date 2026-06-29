"""Config-loader tests. Stdlib unittest + PyYAML only — no geospatial stack."""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline" / "src"))

# PyYAML is a pipeline dependency but may be absent in the repo's onstove-only
# CI env. Skip cleanly there rather than erroring at collection.
try:
    import yaml  # noqa: F401
    from onstove_pipeline import config  # noqa: E402
    _HAVE_YAML = True
except ImportError:  # pragma: no cover
    _HAVE_YAML = False


def base_cfg():
    return {
        "country": {"name": "Tanzania", "iso3": "TZA"},
        "provenance": {"validation_status": "provisional", "validated_against": None},
        "paths": {},
        "spatial": {"project_crs": 3395, "cell_size_m": 1000},
        "technologies": ["LPG", "Electricity"],
        "assumptions": {
            "discount_rate": 0.10,
            "fnrb": 0.51,
            "fnrb_source": "TOOL33_national",
            "vsl_usd": 308100,
            "carbon_price_usd_per_tco2": 30,
            "crediting_period_years": 7,
        },
    }


@unittest.skipUnless(_HAVE_YAML, "PyYAML not installed (pipeline dependency)")
class TestConfigValidation(unittest.TestCase):
    def test_base_cfg_is_valid(self):
        self.assertEqual(config.validate(base_cfg()), [])

    def test_real_tanzania_yaml_validates(self):
        cfg = config.load(REPO / "pipeline" / "config" / "tanzania.yaml")
        self.assertEqual(config.validate(cfg), [])

    def test_template_has_placeholders(self):
        # the template is a TEMPLATE; it should fail until filled in
        cfg = config.load(REPO / "pipeline" / "config" / "config.template.yaml")
        self.assertTrue(config.validate(cfg))

    def test_missing_top_level_key(self):
        cfg = base_cfg()
        del cfg["assumptions"]
        problems = config.validate(cfg)
        self.assertTrue(any("assumptions" in p for p in problems))

    def test_bad_iso3(self):
        cfg = base_cfg()
        cfg["country"]["iso3"] = "TZ"
        self.assertTrue(any("iso3" in p for p in config.validate(cfg)))

    def test_validated_requires_citation(self):
        cfg = base_cfg()
        cfg["provenance"]["validation_status"] = "validated"
        cfg["provenance"]["validated_against"] = None
        self.assertTrue(any("validated_against" in p for p in config.validate(cfg)))
        cfg["provenance"]["validated_against"] = "Khavari et al. 2023, doi:..."
        self.assertEqual(config.validate(cfg), [])

    def test_discount_rate_range(self):
        cfg = base_cfg()
        cfg["assumptions"]["discount_rate"] = 1.5
        self.assertTrue(any("discount_rate" in p for p in config.validate(cfg)))

    def test_bad_fnrb_source(self):
        cfg = base_cfg()
        cfg["assumptions"]["fnrb_source"] = "made_up"
        self.assertTrue(any("fnrb_source" in p for p in config.validate(cfg)))

    def test_load_and_validate_raises_on_invalid_file(self):
        import tempfile

        import yaml
        cfg = base_cfg()
        cfg["country"]["iso3"] = "BAD1"  # 4 chars -> invalid
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            yaml.safe_dump(cfg, fh)
            path = fh.name
        with self.assertRaises(config.ConfigError):
            config.load_and_validate(path)

    def test_load_and_validate_ok(self):
        path = REPO / "pipeline" / "config" / "tanzania.yaml"
        cfg = config.load_and_validate(path)
        self.assertEqual(cfg["country"]["iso3"], "TZA")


if __name__ == "__main__":
    unittest.main()
