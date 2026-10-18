import pathlib
import unittest

from scripts.hw_validation_build import plan_build


ROOT = pathlib.Path(__file__).resolve().parents[1]


class HardwareBuildPlanTests(unittest.TestCase):
    def test_dirty_tree_uses_a_distinct_build_directory(self):
        clean_command, clean = plan_build(ROOT, 'abcdef0', False)
        dirty_command, dirty = plan_build(ROOT, 'abcdef0', True)
        self.assertNotEqual(clean, dirty)
        self.assertNotIn('upload', ' '.join(clean_command))
        self.assertNotIn('upload', ' '.join(dirty_command))
        self.assertIn('VALIDATION_GIT_SHA', ' '.join(clean_command))
        self.assertIn('VALIDATION_DIRTY_TREE=0', ' '.join(clean_command))
        self.assertIn('VALIDATION_DIRTY_TREE=1', ' '.join(dirty_command))


if __name__ == '__main__':
    unittest.main()
