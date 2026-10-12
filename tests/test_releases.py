import importlib.util,pathlib,tempfile,unittest
from unittest.mock import patch
root=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_assets',root/'scripts/release_assets.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
class ReleaseTests(unittest.TestCase):
    def test_versions_and_notes_are_consistent(self):
        self.assertRegex(release.version(),r'^\d+\.\d+\.\d+$')
        for value in ['0.1.0',release.version()]:self.assertIn('Verification scope',release.notes(value));self.assertIn('Android',release.notes(value))
    def test_missing_notes_fail_before_publication(self):
        with self.assertRaisesRegex(ValueError,'Missing release notes'):release.notes('9.9.9')
    def test_mismatched_engine_version_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t);(p/'apk_revival').mkdir();(p/'pyproject.toml').write_text('[project]\nversion="0.2.0"\n');(p/'apk_revival/__init__.py').write_text('__version__="0.1.0"')
            with self.assertRaisesRegex(ValueError,'versions differ'):release.version(p)
