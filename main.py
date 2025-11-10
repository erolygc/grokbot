"""
Main trading bot - Orchestrates all modules
Runs the complete trading system with data collection, signal generation, and execution
"""
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from config import Config
from src.data_collector import DataCollector
from src.indicators import IndicatorCalculator
from src.signal_generator import SignalGenerator
from src.trade_executor import TradeExecutor
from src.risk_manager import RiskManager
from src.utils import setup_logger, TelegramNotifier

# Setup logger
logger = setup_logger('TradingBot', Config.LOG_FILE, Config.LOG_LEVEL)


class TradingBot:
    """Main trading bot orchestrating all components"""

    def __init__(self):
        """Initialize trading bot"""
        logger.info("=" * 60)
        logger.info("Initializing Crypto Trading Bot")
        logger.info("=" * 60)

        # Initialize components
        self.data_collector = DataCollector()
        self.indicator_calculator = IndicatorCalculator()
        self.signal_generator = SignalGenerator()
        self.trade_executor = TradeExecutor(self.data_collector.exchange)
        self.risk_manager = RiskManager()
        self.telegram = TelegramNotifier(
            Config.TELEGRAM_BOT_TOKEN,
            Config.TELEGRAM_CHAT_ID
        )

        # State variables
        self.running = False
        self.last_trade_time = None
        self.update_counter = 0

        logger.info(f"Trading pair: {Config.TRADING_PAIR}")
        logger.info(f"Sandbox mode: {Config.SANDBOX_MODE}")
        logger.info(f"Leverage: {Config.LEVERAGE}x")
        logger.info(f"Position size: ${Config.POSITION_SIZE}")
        logger.info("Bot initialized successfully")

    async def initialize(self):
        """Initialize bot with historical data"""
        logger.info("Loading historical data...")

        try:
            # Load historical data for all timeframes
            self.data_collector.initialize_historical_data()

            logger.info("Historical data loaded successfully")

            # Send initialization message
            if self.telegram.enabled:
                self.telegram.send_message(
                    "<b>🤖 Trading Bot Started</b>\n"
                    f"Pair: {Config.TRADING_PAIR}\n"
                    f"Mode: {'SANDBOX' if Config.SANDBOX_MODE else 'LIVE'}\n"
                    f"Leverage: {Config.LEVERAGE}x"
                )

        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise

    async def update_market_data(self):
        """Update market data for all timeframes"""
        try:
            self.data_collector.update_all_timeframes()
        except Exception as e:
            logger.error(f"Failed to update market data: {e}")

    async def process_signals(self):
        """Process signals and execute trades"""
        try:
            # Get dataframes for each timeframe
            df_1m = self.data_collector.get_dataframe(Config.TRADING_PAIR, '1m')
            df_15m = self.data_collector.get_dataframe(Config.TRADING_PAIR, '15m')
            df_4h = self.data_collector.get_dataframe(Config.TRADING_PAIR, '4h')

            if df_1m is None or df_15m is None or df_4h is None:
                logger.warning("Insufficient data for signal generation")
                return

            # Calculate indicators for each timeframe
            indicators_1m = self.indicator_calculator.calculate_all_indicators(df_1m, '1m')
            indicators_15m = self.indicator_calculator.calculate_all_indicators(df_15m, '15m')
            indicators_4h = self.indicator_calculator.calculate_all_indicators(df_4h, '4h')

            # Get funding rate
            funding_rate = self.data_collector.fetch_funding_rate(Config.TRADING_PAIR)

            # Generate signal
            signal, score, reason = self.signal_generator.generate_signal(
                indicators_1m,
                indicators_15m,
                indicators_4h,
                funding_rate
            )

            # Get current price
            current_price = self.data_collector.get_latest_price(Config.TRADING_PAIR)
            if not current_price:
                logger.error("Failed to get current price")
                return

            # Log signal
            logger.info(
                f"Signal: {signal} | Score: {score} | Price: ${current_price:.2f}"
            )

            # Check if in cooldown
            if self.signal_generator.should_wait_for_cooldown(self.last_trade_time):
                return

            # Get account balance
            balance_info = self.trade_executor.get_account_balance()
            if not balance_info:
                logger.error("Failed to get balance")
                return

            current_balance = balance_info['free']

            # Check if should stop trading
            should_stop, stop_reason = self.risk_manager.should_stop_trading(current_balance)
            if should_stop:
                logger.error(f"Trading stopped: {stop_reason}")
                if self.telegram.enabled:
                    self.telegram.send_error_alert(f"Trading stopped: {stop_reason}")
                # Close all positions
                self.trade_executor.close_all_positions(Config.TRADING_PAIR, stop_reason)
                return

            # Execute trades based on signal
            await self.execute_signal(signal, current_price, indicators_1m)

            # Manage existing positions
            await self.manage_positions(current_price, indicators_1m)

        except Exception as e:
            logger.error(f"Error processing signals: {e}")

    async def execute_signal(self, signal: str, current_price: float, indicators: dict):
        """
        Execute trading signal

        Args:
            signal: Trading signal (LONG/SHORT/HOLD)
            current_price: Current market price
            indicators: Current indicators
        """
        if signal == 'HOLD':
            return

        # Get current positions
        positions = self.trade_executor.get_position_summary()

        # Calculate stop loss
        atr = indicators.get('atr', current_price * 0.02)
        stop_loss = self.risk_manager.calculate_stop_loss(
            current_price,
            signal.lower(),
            atr
        )

        if signal == 'LONG' and not positions['long_open']:
            # Open long position
            logger.info(f"Opening LONG position at ${current_price:.2f}")

            order = self.trade_executor.open_long_position(
                Config.TRADING_PAIR,
                current_price,
                stop_loss
            )

            if order:
                self.last_trade_time = datetime.now()
                # Send notification
                if self.telegram.enabled:
                    self.telegram.send_trade_alert('LONG', current_price, "Signal triggered")

        elif signal == 'SHORT' and not positions['short_open']:
            # Open short position
            logger.info(f"Opening SHORT position at ${current_price:.2f}")

            order = self.trade_executor.open_short_position(
                Config.TRADING_PAIR,
                current_price,
                stop_loss
            )

            if order:
                self.last_trade_time = datetime.now()
                # Send notification
                if self.telegram.enabled:
                    self.telegram.send_trade_alert('SHORT', current_price, "Signal triggered")

    async def manage_positions(self, current_price: float, indicators: dict):
        """
        Manage existing positions (trailing stop, take profit)

        Args:
            current_price: Current market price
            indicators: Current indicators
        """
        positions = self.trade_executor.positions

        for side, position in list(positions.items()):
            entry_price = position['entry_price']
            amount = position['amount']
            atr = indicators.get('atr', current_price * 0.02)

            # Update trailing stop
            trailing_stop, triggered = self.risk_manager.update_trailing_stop(
                side,
                current_price,
                entry_price,
                atr
            )

            if triggered:
                logger.info(f"Trailing stop triggered for {side.upper()}")
                self.trade_executor.close_position(
                    Config.TRADING_PAIR,
                    side,
                    "Trailing stop"
                )
                self.risk_manager.reset_trailing_stop(side)
                self.risk_manager.record_trade(side, entry_price, current_price, amount)
                continue

            # Check take profit
            if self.risk_manager.should_close_partial(side, current_price, entry_price):
                logger.info(f"Take profit reached for {side.upper()}")
                # Close 50% of position
                half_amount = amount / 2
                logger.info(f"Closing 50% of {side} position ({half_amount:.6f} contracts)")

                # For now, close full position (partial close requires more complex logic)
                self.trade_executor.close_position(
                    Config.TRADING_PAIR,
                    side,
                    "Take profit"
                )
                self.risk_manager.reset_trailing_stop(side)
                self.risk_manager.record_trade(side, entry_price, current_price, amount)

    async def run(self):
        """Main bot loop"""
        logger.info("Starting trading bot main loop")
        self.running = True

        # Initialize
        await self.initialize()

        # Main loop
        while self.running:
            try:
                self.update_counter += 1

                # Update market data
                await self.update_market_data()

                # Process signals every minute
                if self.update_counter % 6 == 0:  # Every 60 seconds (6 * 10s)
                    await self.process_signals()

                # Log status every 5 minutes
                if self.update_counter % 30 == 0:  # Every 300 seconds (30 * 10s)
                    self.log_status()

                # Wait 10 seconds
                await asyncio.sleep(10)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(60)

        logger.info("Bot stopped")

    def log_status(self):
        """Log current bot status"""
        logger.info("=" * 60)
        logger.info("Bot Status")
        logger.info("=" * 60)

        # Position summary
        positions = self.trade_executor.get_position_summary()
        logger.info(f"Open positions: {positions['open_positions']}")
        logger.info(f"Long: {positions['long_open']} | Short: {positions['short_open']}")

        # Balance
        balance = self.trade_executor.get_account_balance()
        if balance:
            logger.info(f"Balance: ${balance['total']:.2f}")

        # Statistics
        stats = self.risk_manager.get_statistics()
        logger.info(f"Total trades: {stats['total_trades']}")
        logger.info(f"Win rate: {stats['win_rate']:.1f}%")
        logger.info(f"Total PnL: ${stats['total_pnl']:.2f}")

        logger.info("=" * 60)

    def stop(self):
        """Stop the bot"""
        logger.info("Stopping bot...")
        self.running = False

        # Close all positions
        logger.info("Closing all positions...")
        self.trade_executor.close_all_positions(Config.TRADING_PAIR, "Bot stopped")

        # Log final statistics
        stats = self.risk_manager.get_statistics()
        logger.info("=" * 60)
        logger.info("Final Statistics")
        logger.info("=" * 60)
        logger.info(f"Total trades: {stats['total_trades']}")
        logger.info(f"Winning trades: {stats['winning_trades']}")
        logger.info(f"Losing trades: {stats['losing_trades']}")
        logger.info(f"Win rate: {stats['win_rate']:.1f}%")
        logger.info(f"Total PnL: ${stats['total_pnl']:.2f}")
        logger.info(f"Average PnL: ${stats['average_pnl']:.2f}")
        logger.info("=" * 60)

        # Send final message
        if self.telegram.enabled:
            self.telegram.send_message(
                "<b>🛑 Trading Bot Stopped</b>\n"
                f"Total trades: {stats['total_trades']}\n"
                f"Win rate: {stats['win_rate']:.1f}%\n"
                f"Total PnL: ${stats['total_pnl']:.2f}"
            )


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}")
    if bot:
        bot.stop()
    sys.exit(0)


# Global bot instance
bot = None


async def main():
    """Main entry point"""
    global bot

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Create and run bot
        bot = TradingBot()
        await bot.run()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
