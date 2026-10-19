import socket
import unittest
from decimal import Decimal
from unittest.mock import patch

from portfolio_bot.demo import OfflineBot


class CycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_filled_primary_hedges_opposite_side(self):
        bot = OfflineBot()
        with patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')):
            self.assertTrue(await bot.executeHedgeCycle('buy'))
        self.assertEqual(bot.hedgeClient.calls, [('hedge', 'sell', Decimal('0.01'))])

    async def test_partial_fill_hedges_actual_quantity(self):
        bot = OfflineBot(fill='PARTIALLY_FILLED', filled_size=Decimal('0.004'))
        self.assertTrue(await bot.executeHedgeCycle('sell'))
        self.assertEqual(bot.hedgeClient.calls, [('hedge', 'buy', Decimal('0.004'))])

    async def test_timeout_cancels_without_hedging(self):
        bot = OfflineBot(fill=None)
        self.assertFalse(await bot.executeHedgeCycle('buy'))
        self.assertIn(('cancel', 'mock-1'), bot.primaryClient.calls)
        self.assertEqual(bot.hedgeClient.calls, [])
        self.assertEqual(bot.fillRateStats['timeout'], 1)

    async def test_failed_hedge_records_signed_imbalance(self):
        for direction, expected in [('buy', Decimal('0.01')), ('sell', Decimal('-0.01'))]:
            bot = OfflineBot(hedge_fail=True)
            self.assertFalse(await bot.executeHedgeCycle(direction))
            self.assertEqual(bot.positionImbalance, expected)

    async def test_primary_rejection_does_not_hedge(self):
        bot = OfflineBot(primary_fail=True)
        self.assertFalse(await bot.executeHedgeCycle('buy'))
        self.assertEqual(bot.hedgeClient.calls, [])

    async def test_zero_fill_does_not_hedge(self):
        bot = OfflineBot(filled_size=Decimal('0'))
        self.assertFalse(await bot.executeHedgeCycle('buy'))
        self.assertEqual(bot.hedgeClient.calls, [])


if __name__ == '__main__':
    unittest.main()
