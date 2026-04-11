import unittest
from datetime import datetime, timedelta
from server.api.services.evolution_trigger import EvolutionTrigger

class TestEvolutionTrigger(unittest.TestCase):
    def setUp(self):
        self.trigger = EvolutionTrigger()

    def test_check_regime_shift(self):
        # Same regime
        self.assertFalse(self.trigger.check_regime_shift("Bull", "Bull"))
        # Different regime
        self.assertTrue(self.trigger.check_regime_shift("Bull", "Bear"))
        self.assertTrue(self.trigger.check_regime_shift("Sideways", "Bull"))

    def test_check_performance_decay(self):
        # No decay (100% of avg)
        self.assertFalse(self.trigger.check_performance_decay(100, 100))
        # No decay (81% of avg)
        self.assertFalse(self.trigger.check_performance_decay(81, 100))
        # Decay (80% of avg)
        self.assertTrue(self.trigger.check_performance_decay(80, 100))
        # Severe decay (50% of avg)
        self.assertTrue(self.trigger.check_performance_decay(50, 100))

    def test_check_competitive_pressure(self):
        # Rank 1: No pressure regardless of score
        self.assertFalse(self.trigger.check_competitive_pressure(1, 100, 100))

        # Rank 2: Small gap (10% <<  20%)
        self.assertFalse(self.trigger.check_competitive_pressure(2, 100, 90))

        # Rank 2: Significant gap (20% == 20%)
        self.assertTrue(self.trigger.check_competitive_pressure(2, 100, 80))

        # Rank 2: Very large gap (50% > 20%)
        self.assertTrue(self.trigger.check_competitive_pressure(2, 100, 50))

        # Zero top score edge case
        self.assertFalse(self.trigger.check_competitive_pressure(2, 0, 0))

    def test_check_heartbeat(self):
        # Never evolved
        self.assertTrue(self.trigger.check_heartbeat(None))

        # Evolved yesterday (1 day <<  14 days)
        yesterday = datetime.now() - timedelta(days=1)
        self.assertFalse(self.trigger.check_heartbeat(yesterday))

        # Evolved 14 days ago (14 days == 14 days)
        two_weeks_ago = datetime.now() - timedelta(days=14)
        self.assertTrue(self.trigger.check_heartbeat(two_weeks_ago))

        # Evolved 20 days ago (20 days > 14 days)
        long_ago = datetime.now() - timedelta(days=20)
        self.assertTrue(self.trigger.check_heartbeat(long_ago))

    def test_get_intensity(self):
        self.assertEqual(self.trigger.get_intensity("L1"), "HIGH (Pivot)")
        self.assertEqual(self.trigger.get_intensity("L2"), "HIGH (Pivot)")
        self.assertEqual(self.trigger.get_intensity("L3"), "LOW (Tuning)")
        self.assertEqual(self.trigger.get_intensity("L4"), "LOW (Tuning)")
        self.assertEqual(self.trigger.get_intensity("Unknown"), "LOW (Tuning)")

if __name__ == "__main__":
    unittest.main()
