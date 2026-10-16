"""Include shipped source-only solo regression checks in normal discovery."""
from pathlib import Path
import unittest


def load_tests(loader, tests, pattern):
    root = Path(__file__).resolve().parents[1]
    return unittest.TestLoader().discover(
        str(root / 'apk_revival/meego/regression_tests'),
        pattern='test_*.py', top_level_dir=str(root))
