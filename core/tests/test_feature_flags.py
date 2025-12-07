from django.test import SimpleTestCase

from core.feature_flags import _hit


class FeatureFlagsTest(SimpleTestCase):
    def test_rollout_is_deterministic(self):
        self.assertTrue(_hit("any", 100))
        self.assertFalse(_hit("any", 0))
        first = _hit("user-xyz", 50)
        second = _hit("user-xyz", 50)
        self.assertEqual(first, second)
