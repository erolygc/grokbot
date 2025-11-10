"""
Trade execution module for opening/closing positions on Gate.io
Supports hedge mode, market orders, and position management
"""
import ccxt
import logging
from typing import Dict, Optional, List
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


class TradeExecutor:
    """Execute trades on Gate.io futures exchange"""

    def __init__(self, exchange: ccxt.gateio):
        """
        Initialize trade executor

        Args:
            exchange: CCXT Gate.io exchange instance
        """
        self.exchange = exchange
        self.positions: Dict = {}
        self.orders: List[Dict] = []
        self._enable_hedge_mode()

    def _enable_hedge_mode(self):
        """Enable hedge mode (dual position mode) on Gate.io"""
        try:
            # Set hedge mode for the trading pair
            symbol = Config.TRADING_PAIR.replace('/', '_')

            # Gate.io API call to enable dual mode
            # Note: This might need to be done manually on Gate.io interface
            # as API support varies
            logger.info("Attempting to enable hedge mode...")

            # Try to set dual mode via API
            try:
                self.exchange.futures_set_dual_mode(
                    symbol=symbol,
                    dual_side=True
                )
                logger.info("Hedge mode enabled successfully")
            except AttributeError:
                logger.warning(
                    "Hedge mode API not available. "
                    "Please enable 'Dual Position Mode' manually on Gate.io"
                )

        except Exception as e:
            logger.error(f"Failed to enable hedge mode: {e}")
            logger.warning(
                "Please manually enable 'Dual Position Mode' in Gate.io settings"
            )

    def calculate_position_size(self, price: float) -> float:
        """
        Calculate position size in contracts

        Args:
            price: Current price

        Returns:
            Position size in contracts
        """
        # Position size in USD
        position_usd = Config.POSITION_SIZE

        # Calculate contracts
        contracts = position_usd / price

        logger.debug(
            f"Position size: {position_usd} USD = {contracts:.6f} contracts at ${price}"
        )

        return contracts

    def open_long_position(
        self,
        symbol: str,
        price: float,
        stop_loss: Optional[float] = None
    ) -> Optional[Dict]:
        """
        Open a long position

        Args:
            symbol: Trading pair
            price: Entry price
            stop_loss: Stop loss price (optional)

        Returns:
            Order dictionary or None if failed
        """
        try:
            # Calculate position size
            amount = self.calculate_position_size(price)

            logger.info(
                f"Opening LONG position: {amount:.6f} contracts at ${price:.2f}"
            )

            # Create market buy order
            order = self.exchange.create_market_buy_order(
                symbol,
                amount,
                params={
                    'leverage': Config.LEVERAGE,
                    'positionSide': 'long'  # For hedge mode
                }
            )

            logger.info(f"LONG order executed: {order['id']}")

            # Store position
            self.positions['long'] = {
                'side': 'long',
                'amount': amount,
                'entry_price': price,
                'stop_loss': stop_loss,
                'timestamp': datetime.now(),
                'order_id': order['id']
            }

            # Store order
            self.orders.append(order)

            return order

        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds for LONG order: {e}")
            return None
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error opening LONG: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error opening LONG: {e}")
            return None

    def open_short_position(
        self,
        symbol: str,
        price: float,
        stop_loss: Optional[float] = None
    ) -> Optional[Dict]:
        """
        Open a short position

        Args:
            symbol: Trading pair
            price: Entry price
            stop_loss: Stop loss price (optional)

        Returns:
            Order dictionary or None if failed
        """
        try:
            # Calculate position size
            amount = self.calculate_position_size(price)

            logger.info(
                f"Opening SHORT position: {amount:.6f} contracts at ${price:.2f}"
            )

            # Create market sell order
            order = self.exchange.create_market_sell_order(
                symbol,
                amount,
                params={
                    'leverage': Config.LEVERAGE,
                    'positionSide': 'short'  # For hedge mode
                }
            )

            logger.info(f"SHORT order executed: {order['id']}")

            # Store position
            self.positions['short'] = {
                'side': 'short',
                'amount': amount,
                'entry_price': price,
                'stop_loss': stop_loss,
                'timestamp': datetime.now(),
                'order_id': order['id']
            }

            # Store order
            self.orders.append(order)

            return order

        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds for SHORT order: {e}")
            return None
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error opening SHORT: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error opening SHORT: {e}")
            return None

    def close_position(
        self,
        symbol: str,
        side: str,
        reason: str = "Signal"
    ) -> Optional[Dict]:
        """
        Close an existing position

        Args:
            symbol: Trading pair
            side: Position side ('long' or 'short')
            reason: Reason for closing

        Returns:
            Order dictionary or None if failed
        """
        if side not in self.positions:
            logger.warning(f"No {side} position to close")
            return None

        try:
            position = self.positions[side]
            amount = position['amount']
            entry_price = position['entry_price']

            logger.info(
                f"Closing {side.upper()} position: {amount:.6f} contracts | "
                f"Reason: {reason}"
            )

            # Close position (opposite order)
            if side == 'long':
                order = self.exchange.create_market_sell_order(
                    symbol,
                    amount,
                    params={'positionSide': 'long', 'reduceOnly': True}
                )
            else:
                order = self.exchange.create_market_buy_order(
                    symbol,
                    amount,
                    params={'positionSide': 'short', 'reduceOnly': True}
                )

            # Calculate PnL
            exit_price = order.get('price', order.get('average', 0))
            if side == 'long':
                pnl = (exit_price - entry_price) * amount * Config.LEVERAGE
            else:
                pnl = (entry_price - exit_price) * amount * Config.LEVERAGE

            pnl_percent = (pnl / Config.POSITION_SIZE) * 100

            logger.info(
                f"{side.upper()} closed: PnL = ${pnl:.2f} ({pnl_percent:.2f}%)"
            )

            # Remove from positions
            del self.positions[side]

            # Store order
            self.orders.append(order)

            return order

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error closing {side}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error closing {side}: {e}")
            return None

    def close_all_positions(self, symbol: str, reason: str = "Emergency") -> int:
        """
        Close all open positions

        Args:
            symbol: Trading pair
            reason: Reason for closing

        Returns:
            Number of positions closed
        """
        closed = 0

        for side in list(self.positions.keys()):
            if self.close_position(symbol, side, reason):
                closed += 1

        logger.info(f"Closed {closed} positions | Reason: {reason}")
        return closed

    def update_positions_from_exchange(self, symbol: str):
        """
        Sync positions with exchange

        Args:
            symbol: Trading pair
        """
        try:
            # Fetch positions from exchange
            exchange_positions = self.exchange.fetch_positions([symbol])

            # Update local positions
            for pos in exchange_positions:
                side = pos.get('side', '').lower()
                contracts = pos.get('contracts', 0)

                if contracts > 0:
                    if side not in self.positions:
                        # Position exists on exchange but not locally
                        self.positions[side] = {
                            'side': side,
                            'amount': contracts,
                            'entry_price': pos.get('entryPrice', 0),
                            'stop_loss': None,
                            'timestamp': datetime.now(),
                            'order_id': None
                        }
                        logger.info(f"Synced {side} position from exchange")
                else:
                    # Position closed on exchange
                    if side in self.positions:
                        del self.positions[side]
                        logger.info(f"Removed closed {side} position")

        except Exception as e:
            logger.error(f"Failed to sync positions: {e}")

    def get_position_summary(self) -> Dict:
        """
        Get summary of current positions

        Returns:
            Dictionary with position information
        """
        return {
            'open_positions': len(self.positions),
            'long_open': 'long' in self.positions,
            'short_open': 'short' in self.positions,
            'positions': self.positions.copy()
        }

    def place_stop_loss_order(
        self,
        symbol: str,
        side: str,
        stop_price: float
    ) -> Optional[Dict]:
        """
        Place a stop loss order

        Args:
            symbol: Trading pair
            side: Position side
            stop_price: Stop loss trigger price

        Returns:
            Order dictionary or None if failed
        """
        if side not in self.positions:
            logger.warning(f"No {side} position for stop loss")
            return None

        try:
            position = self.positions[side]
            amount = position['amount']

            # Create stop loss order
            if side == 'long':
                # Stop loss for long = sell stop
                order = self.exchange.create_order(
                    symbol,
                    'stop',
                    'sell',
                    amount,
                    stop_price,
                    params={
                        'positionSide': 'long',
                        'reduceOnly': True,
                        'stopPrice': stop_price
                    }
                )
            else:
                # Stop loss for short = buy stop
                order = self.exchange.create_order(
                    symbol,
                    'stop',
                    'buy',
                    amount,
                    stop_price,
                    params={
                        'positionSide': 'short',
                        'reduceOnly': True,
                        'stopPrice': stop_price
                    }
                )

            # Update position with stop loss
            self.positions[side]['stop_loss'] = stop_price

            logger.info(
                f"Stop loss placed for {side.upper()}: ${stop_price:.2f}"
            )

            return order

        except Exception as e:
            logger.error(f"Failed to place stop loss: {e}")
            return None

    def get_account_balance(self) -> Optional[Dict]:
        """
        Get account balance

        Returns:
            Balance dictionary or None if failed
        """
        try:
            balance = self.exchange.fetch_balance()

            # Get USDT balance
            usdt_balance = balance.get('USDT', {})

            return {
                'total': usdt_balance.get('total', 0),
                'free': usdt_balance.get('free', 0),
                'used': usdt_balance.get('used', 0)
            }

        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return None

    def get_trade_history(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Get trade history

        Args:
            symbol: Trading pair
            limit: Number of trades to fetch

        Returns:
            List of trade dictionaries
        """
        try:
            trades = self.exchange.fetch_my_trades(symbol, limit=limit)
            return trades
        except Exception as e:
            logger.error(f"Failed to fetch trade history: {e}")
            return []
