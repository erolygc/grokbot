"""
Risk management module
Handles stop loss, take profit, trailing stops, and position sizing
"""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


class RiskManager:
    """Manage trading risks with stop loss, take profit, and exposure limits"""

    def __init__(self):
        """Initialize risk manager"""
        self.trailing_stops: Dict[str, float] = {}
        self.initial_balance = Config.INITIAL_BALANCE
        self.peak_balance = Config.INITIAL_BALANCE
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0

    def calculate_stop_loss(
        self,
        entry_price: float,
        side: str,
        atr: float
    ) -> float:
        """
        Calculate stop loss price based on ATR

        Args:
            entry_price: Entry price
            side: Position side ('long' or 'short')
            atr: Average True Range value

        Returns:
            Stop loss price
        """
        stop_distance = atr * Config.STOP_LOSS_ATR_MULTIPLIER

        if side == 'long':
            stop_loss = entry_price - stop_distance
        else:
            stop_loss = entry_price + stop_distance

        logger.debug(
            f"Calculated stop loss for {side}: ${stop_loss:.2f} "
            f"(distance: ${stop_distance:.2f})"
        )

        return stop_loss

    def calculate_take_profit(
        self,
        entry_price: float,
        side: str
    ) -> float:
        """
        Calculate take profit price

        Args:
            entry_price: Entry price
            side: Position side ('long' or 'short')

        Returns:
            Take profit price
        """
        profit_distance = entry_price * Config.TAKE_PROFIT_PERCENTAGE

        if side == 'long':
            take_profit = entry_price + profit_distance
        else:
            take_profit = entry_price - profit_distance

        logger.debug(
            f"Calculated take profit for {side}: ${take_profit:.2f} "
            f"({Config.TAKE_PROFIT_PERCENTAGE*100}%)"
        )

        return take_profit

    def update_trailing_stop(
        self,
        side: str,
        current_price: float,
        entry_price: float,
        atr: float
    ) -> Tuple[float, bool]:
        """
        Update trailing stop loss

        Args:
            side: Position side
            current_price: Current market price
            entry_price: Entry price
            atr: Current ATR value

        Returns:
            Tuple of (new_stop_loss, triggered)
        """
        # Calculate trailing distance
        trail_distance = atr * Config.STOP_LOSS_ATR_MULTIPLIER

        # Get current trailing stop
        current_stop = self.trailing_stops.get(side)

        if side == 'long':
            # For long, stop moves up with price
            new_stop = current_price - trail_distance

            # Initialize or update trailing stop
            if current_stop is None:
                self.trailing_stops[side] = max(entry_price - trail_distance, new_stop)
                current_stop = self.trailing_stops[side]
            elif new_stop > current_stop:
                self.trailing_stops[side] = new_stop
                logger.info(f"Trailing stop updated for LONG: ${new_stop:.2f}")

            # Check if stop triggered
            triggered = current_price <= self.trailing_stops[side]

            return self.trailing_stops[side], triggered

        else:  # short
            # For short, stop moves down with price
            new_stop = current_price + trail_distance

            # Initialize or update trailing stop
            if current_stop is None:
                self.trailing_stops[side] = min(entry_price + trail_distance, new_stop)
                current_stop = self.trailing_stops[side]
            elif new_stop < current_stop:
                self.trailing_stops[side] = new_stop
                logger.info(f"Trailing stop updated for SHORT: ${new_stop:.2f}")

            # Check if stop triggered
            triggered = current_price >= self.trailing_stops[side]

            return self.trailing_stops[side], triggered

    def check_take_profit(
        self,
        side: str,
        current_price: float,
        entry_price: float
    ) -> Tuple[bool, float]:
        """
        Check if take profit level reached

        Args:
            side: Position side
            current_price: Current price
            entry_price: Entry price

        Returns:
            Tuple of (reached, profit_percentage)
        """
        if side == 'long':
            profit = (current_price - entry_price) / entry_price
            reached = profit >= Config.TAKE_PROFIT_PERCENTAGE
        else:
            profit = (entry_price - current_price) / entry_price
            reached = profit >= Config.TAKE_PROFIT_PERCENTAGE

        return reached, profit

    def should_close_partial(
        self,
        side: str,
        current_price: float,
        entry_price: float
    ) -> bool:
        """
        Check if should close partial position (50% at 5% profit)

        Args:
            side: Position side
            current_price: Current price
            entry_price: Entry price

        Returns:
            True if should close partial
        """
        reached, profit = self.check_take_profit(side, current_price, entry_price)

        if reached:
            logger.info(
                f"Take profit reached for {side.upper()}: {profit*100:.2f}%"
            )
            return True

        return False

    def check_max_drawdown(self, current_balance: float) -> bool:
        """
        Check if maximum drawdown exceeded

        Args:
            current_balance: Current account balance

        Returns:
            True if max drawdown exceeded
        """
        # Update peak balance
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance

        # Calculate drawdown
        drawdown = (self.peak_balance - current_balance) / self.peak_balance

        if drawdown >= Config.MAX_DRAWDOWN:
            logger.warning(
                f"Maximum drawdown exceeded: {drawdown*100:.2f}% "
                f"(limit: {Config.MAX_DRAWDOWN*100}%)"
            )
            return True

        return False

    def check_exposure(
        self,
        current_balance: float,
        position_value: float
    ) -> bool:
        """
        Check if position would exceed maximum exposure

        Args:
            current_balance: Current balance
            position_value: Value of new position

        Returns:
            True if exposure acceptable
        """
        max_position = current_balance * Config.MAX_EXPOSURE

        if position_value > max_position:
            logger.warning(
                f"Position size ${position_value:.2f} exceeds "
                f"max exposure ${max_position:.2f}"
            )
            return False

        return True

    def calculate_position_pnl(
        self,
        side: str,
        entry_price: float,
        exit_price: float,
        amount: float
    ) -> Tuple[float, float]:
        """
        Calculate position PnL

        Args:
            side: Position side
            entry_price: Entry price
            exit_price: Exit price
            amount: Position size

        Returns:
            Tuple of (pnl_usd, pnl_percentage)
        """
        if side == 'long':
            pnl = (exit_price - entry_price) * amount * Config.LEVERAGE
        else:
            pnl = (entry_price - exit_price) * amount * Config.LEVERAGE

        pnl_percentage = (pnl / Config.POSITION_SIZE) * 100

        return pnl, pnl_percentage

    def record_trade(
        self,
        side: str,
        entry_price: float,
        exit_price: float,
        amount: float
    ):
        """
        Record trade result for statistics

        Args:
            side: Position side
            entry_price: Entry price
            exit_price: Exit price
            amount: Position size
        """
        pnl, pnl_percentage = self.calculate_position_pnl(
            side,
            entry_price,
            exit_price,
            amount
        )

        self.total_trades += 1
        self.total_pnl += pnl

        if pnl > 0:
            self.winning_trades += 1
            logger.info(
                f"Trade closed with PROFIT: ${pnl:.2f} ({pnl_percentage:.2f}%)"
            )
        else:
            self.losing_trades += 1
            logger.info(
                f"Trade closed with LOSS: ${pnl:.2f} ({pnl_percentage:.2f}%)"
            )

    def get_statistics(self) -> Dict:
        """
        Get trading statistics

        Returns:
            Dictionary with statistics
        """
        win_rate = 0
        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100

        avg_pnl = 0
        if self.total_trades > 0:
            avg_pnl = self.total_pnl / self.total_trades

        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'total_pnl': self.total_pnl,
            'average_pnl': avg_pnl,
            'initial_balance': self.initial_balance,
            'peak_balance': self.peak_balance
        }

    def reset_trailing_stop(self, side: str):
        """
        Reset trailing stop for a side

        Args:
            side: Position side
        """
        if side in self.trailing_stops:
            del self.trailing_stops[side]
            logger.debug(f"Reset trailing stop for {side}")

    def get_risk_summary(self, current_balance: float) -> Dict:
        """
        Get risk management summary

        Args:
            current_balance: Current balance

        Returns:
            Dictionary with risk metrics
        """
        drawdown = 0
        if self.peak_balance > 0:
            drawdown = (self.peak_balance - current_balance) / self.peak_balance

        return {
            'current_balance': current_balance,
            'initial_balance': self.initial_balance,
            'peak_balance': self.peak_balance,
            'drawdown': drawdown,
            'drawdown_percentage': drawdown * 100,
            'max_drawdown_limit': Config.MAX_DRAWDOWN * 100,
            'drawdown_healthy': drawdown < Config.MAX_DRAWDOWN
        }

    def should_stop_trading(self, current_balance: float) -> Tuple[bool, str]:
        """
        Check if should stop trading due to risk limits

        Args:
            current_balance: Current balance

        Returns:
            Tuple of (should_stop, reason)
        """
        # Check max drawdown
        if self.check_max_drawdown(current_balance):
            return True, f"Maximum drawdown exceeded ({Config.MAX_DRAWDOWN*100}%)"

        # Check if balance too low
        if current_balance < Config.POSITION_SIZE:
            return True, "Insufficient balance for minimum position"

        return False, ""

    def calculate_optimal_position_size(
        self,
        balance: float,
        price: float,
        volatility: float
    ) -> float:
        """
        Calculate optimal position size based on balance and volatility

        Args:
            balance: Current balance
            price: Current price
            volatility: Market volatility (ATR)

        Returns:
            Optimal position size in USD
        """
        # Base position size
        base_size = Config.POSITION_SIZE

        # Adjust for volatility (reduce size in high volatility)
        volatility_factor = 1.0
        if volatility > 0:
            avg_volatility = price * 0.02  # Assume 2% as average
            volatility_factor = min(1.0, avg_volatility / volatility)

        # Calculate adjusted size
        adjusted_size = base_size * volatility_factor

        # Ensure within exposure limits
        max_size = balance * Config.MAX_EXPOSURE
        optimal_size = min(adjusted_size, max_size)

        logger.debug(
            f"Optimal position size: ${optimal_size:.2f} "
            f"(volatility factor: {volatility_factor:.2f})"
        )

        return optimal_size
