"""Extracted source; see PROVENANCE.md and LICENSE. No live adapters included."""
import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

@dataclass
class OrderResult:
    """Standardized order result structure."""
    success: bool
    order_id: Optional[str] = None
    side: Optional[str] = None
    size: Optional[Decimal] = None
    price: Optional[Decimal] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    filled_size: Optional[Decimal] = None

class HedgeBotCore:
    async def executeHedgeCycle(self, direction: str) -> bool:
        """Execute a single hedge cycle.

        Args:
            direction: 'buy' or 'sell' for PRIMARY side

        Returns:
            True if cycle completed successfully
        """
        self.orderCounter += 1
        self.fillRateStats['attempts'] += 1
        oppositeDirection = 'sell' if direction == 'buy' else 'buy'

        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"[CYCLE {self.orderCounter}] PRIMARY {direction.upper()} -> HEDGE {oppositeDirection.upper()}")

        try:
            # Step 1: Get BBO from PRIMARY
            self.logger.info(f"[BBO] Fetching from PRIMARY ({self.primaryExchangeName})...")
            bboPrices = await self.primaryClient.fetch_bbo_prices(self.primaryContractId)
            if not bboPrices:
                self.logger.warning("[WARN] Failed to get BBO prices from PRIMARY")
                return False

            bestBid, bestAsk = bboPrices
            self.logger.info(f"[BBO] PRIMARY: Bid={bestBid}, Ask={bestAsk}")

            # Step 2: Place POST_ONLY maker order on PRIMARY
            # NOTE: Actual price is determined by API (aggressive maker: ask-tick for BUY, bid+tick for SELL)
            self.logger.info(f"[ORDER] Placing {direction.upper()} maker on PRIMARY")
            primaryResult = await self.primaryClient.place_open_order(
                self.primaryContractId,
                self.orderQuantity,
                direction
            )

            if not primaryResult.success:
                self.logger.warning(f"[WARN] PRIMARY order failed: {primaryResult.error_message}")
                return False

            # DIAGNOSTIC Step 0.2: Store order info (price is determined by API)
            self.currentOrderId = primaryResult.order_id
            makerPrice = primaryResult.price  # Get actual price from API
            print(f"[DEBUG] Stored currentOrderId: {self.currentOrderId}, price: {makerPrice}")

            self.logger.info(f"[OK] PRIMARY order placed: ID={primaryResult.order_id} @ {makerPrice}")
            self.logTradeToCsv(
                self.primaryExchangeName, 'PRIMARY', direction,
                str(makerPrice), str(self.orderQuantity), 'placed'
            )

            # Step 3: Wait for fill with timeout (WebSocket event-driven)
            self.orderFilledEvent.clear()
            self.lastOrderUpdate = None
            filledSize = Decimal('0')
            orderFilled = False

            # DIAGNOSTIC Step 0.4: Log event state before wait
            print(f"[DEBUG] BEFORE wait: orderFilledEvent.is_set() = {self.orderFilledEvent.is_set()}")
            print(f"[DEBUG] Waiting for order {self.currentOrderId} fill (timeout={self.fillTimeout}s)...")

            try:
                # Phase 1.5 Step 1 Alternative: Simple wait with 15s timeout (isolated test)
                await asyncio.wait_for(
                    self.orderFilledEvent.wait(),
                    timeout=self.fillTimeout
                )

                # DIAGNOSTIC Step 0.4: Log event state after successful wait
                print(f"[DEBUG] AFTER wait: orderFilledEvent.is_set() = {self.orderFilledEvent.is_set()}")
                print(f"[DEBUG] Event detected! Proceeding with fill processing...")

                if self.lastOrderUpdate:
                    status = self.lastOrderUpdate.get('status', '')
                    filledSize = Decimal(self.lastOrderUpdate.get('filled_size', '0'))

                    if status in ['FILLED', 'filled', 'Filled']:
                        orderFilled = True
                        self.logger.info(f"[WebSocket] Fill detected: {filledSize} {self.ticker}")
                    elif status in ['PARTIALLY_FILLED', 'partially_filled', 'PartiallyFilled']:
                        if filledSize > 0:
                            orderFilled = True
                            self.logger.info(f"[WebSocket] Partial fill: {filledSize}/{self.orderQuantity}")
                    elif status in ['CANCELLED', 'cancelled', 'Cancelled', 'REJECTED', 'rejected']:
                        self.logger.info(f"[WebSocket] Order cancelled/rejected")
                        return False
                    else:
                        filledSize = Decimal('0')
                        orderFilled = False
                        self.logger.warning(f"[WebSocket] Event triggered but unexpected status: {status}")
                else:
                    filledSize = Decimal('0')
                    orderFilled = False
                    self.logger.warning("[WebSocket] Event triggered but no order update")

            except asyncio.TimeoutError:
                orderFilled = False
                filledSize = Decimal('0')
                # DIAGNOSTIC Step 0.4: Log event state on timeout
                print(f"[DEBUG] TIMEOUT! orderFilledEvent.is_set() = {self.orderFilledEvent.is_set()}")
                print(f"[DEBUG] lastOrderUpdate = {self.lastOrderUpdate}")
                self.logger.error(f"[TIMEOUT] Event never set! Final state: is_set={self.orderFilledEvent.is_set()}")
                self.logger.info(f"[WebSocket] Order {primaryResult.order_id} not filled within {self.fillTimeout}s")

            # Step 4: Handle fill status
            if not orderFilled or filledSize <= 0:
                self.logger.info(f"[TIMEOUT] PRIMARY order not filled within {self.fillTimeout}s, cancelling...")
                await self.primaryClient.cancel_order(primaryResult.order_id)
                self.fillRateStats['timeout'] += 1
                self.logTradeToCsv(
                    self.primaryExchangeName, 'PRIMARY', direction,
                    str(makerPrice), str(self.orderQuantity), 'cancelled'
                )
                return False

            # Update fill rate stats
            self.fillRateStats['filled'] += 1
            self.fillRateStats['total_volume'] += filledSize

            self.logTradeToCsv(
                self.primaryExchangeName, 'PRIMARY', direction,
                str(makerPrice), str(filledSize), 'filled'
            )

            # Step 5: Place market order on HEDGE for filled amount
            self.logger.info(f"[HEDGE] Placing {oppositeDirection.upper()} market order on HEDGE for {filledSize}")
            hedgeResult = await self.hedgeClient.place_market_order(
                self.hedgeContractId,
                filledSize,
                oppositeDirection
            )

            if not hedgeResult.success:
                self.logger.error(f"[FAIL] HEDGE order FAILED: {hedgeResult.error_message}")
                self.logger.error(f"[IMBALANCE] POSITION IMBALANCE: {filledSize} {direction} on PRIMARY not hedged!")
                self.positionImbalance += filledSize if direction == 'buy' else -filledSize
                self.logTradeToCsv(
                    self.hedgeExchangeName, 'HEDGE', oppositeDirection,
                    'N/A', str(filledSize), 'FAILED'
                )
                return False

            hedgePrice = hedgeResult.price if hedgeResult.price else 'market'
            self.logger.info(f"[OK] HEDGE order FILLED @ {hedgePrice}")
            self.logTradeToCsv(
                self.hedgeExchangeName, 'HEDGE', oppositeDirection,
                str(hedgePrice), str(filledSize), 'filled'
            )

            self.logger.info(f"[DONE] Cycle {self.orderCounter} COMPLETE")
            return True

        except Exception as e:
            self.logger.error(f"[ERROR] Cycle error: {e}")
            return False
