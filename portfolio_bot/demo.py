"""Offline fixtures for the extracted strategy, never a network exchange adapter."""
import asyncio
import json
import logging
from decimal import Decimal

from .source_core import HedgeBotCore, OrderResult


class MockExchange:
    """In-memory exchange API fixture: accepts no credentials or endpoint."""

    def __init__(self, bot, fill='FILLED', filled_size=Decimal('0.01'), fail=False):
        self.bot = bot
        self.fill = fill
        self.filled_size = filled_size
        self.fail = fail
        self.calls = []

    async def fetch_bbo_prices(self, contract_id):
        return Decimal('2999'), Decimal('3001')

    async def place_open_order(self, contract_id, quantity, direction):
        self.calls.append(('maker', direction, quantity))
        if self.fail:
            return OrderResult(False, error_message='simulated rejection')
        # Deliver on the next event-loop turn, after the source resets its event.
        if self.fill is not None:
            asyncio.get_running_loop().call_soon(self._deliver_fill)
        return OrderResult(True, order_id='mock-1', price=Decimal('3000'))

    def _deliver_fill(self):
        self.bot.lastOrderUpdate = {'status': self.fill, 'filled_size': str(self.filled_size)}
        self.bot.orderFilledEvent.set()

    async def place_market_order(self, contract_id, quantity, direction):
        self.calls.append(('hedge', direction, quantity))
        return OrderResult(not self.fail, price=Decimal('3000'),
                           error_message='simulated hedge rejection' if self.fail else None)

    async def cancel_order(self, order_id):
        self.calls.append(('cancel', order_id))
        return OrderResult(True, order_id=order_id)


class OfflineBot(HedgeBotCore):
    """Fixture-only host for the original method, with no live initialization path."""

    def __init__(self, fill='FILLED', filled_size=Decimal('0.01'), hedge_fail=False, primary_fail=False):
        self.logger = logging.getLogger('offline-portfolio')
        self.orderCounter = 0
        self.fillRateStats = {'attempts': 0, 'filled': 0, 'timeout': 0, 'total_volume': Decimal('0')}
        self.primaryExchangeName = 'mock-primary'
        self.hedgeExchangeName = 'mock-hedge'
        self.primaryContractId = self.hedgeContractId = 'ETH-PERP-SIMULATED'
        self.ticker = 'ETH'
        self.orderQuantity = Decimal('0.01')
        self.fillTimeout = 1.0
        self.orderFilledEvent = asyncio.Event()
        self.lastOrderUpdate = None
        self.positionImbalance = Decimal('0')
        self.trades = []
        self.primaryClient = MockExchange(self, fill, filled_size, primary_fail)
        self.hedgeClient = MockExchange(self, fail=hedge_fail)

    def logTradeToCsv(self, *row):
        # Keep fixture output in memory; production CSV paths are deliberately absent.
        self.trades.append(row)


async def main():
    bot = OfflineBot()
    success = await bot.executeHedgeCycle('buy')
    print(json.dumps({'mode': 'OFFLINE_ONLY', 'success': success,
                      'simulated_hedge': [(kind, side, str(size)) for kind, side, size in bot.hedgeClient.calls],
                      'recorded_imbalance': str(bot.positionImbalance)}, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
