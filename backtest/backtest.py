"""
Backtesting module for testing trading strategy on historical data
Simulates trading without risking real capital
"""
import ccxt
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import json
from pathlib import Path

from config import Config
from src.indicators import IndicatorCalculator
from src.signal_generator import SignalGenerator
from src.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class Backtester:
    """Backtest trading strategy on historical data"""

    def __init__(self):
        """Initialize backtester"""
        self.indicator_calculator = IndicatorCalculator()
        self.signal_generator = SignalGenerator()
        self.risk_manager = RiskManager()

        # Backtest state
        self.initial_balance = Config.INITIAL_BALANCE
        self.balance = self.initial_balance
        self.positions = {}
        self.trades = []
        self.equity_curve = []

        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0

    def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        days: int = 30
    ) -> pd.DataFrame:
        """
        Fetch historical data for backtesting

        Args:
            symbol: Trading pair
            timeframe: Timeframe (e.g., '1m')
            days: Number of days of history

        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Fetching {days} days of {timeframe} data for {symbol}...")

        try:
            exchange = ccxt.gateio({
                'apiKey': Config.GATE_API_KEY,
                'secret': Config.GATE_SECRET,
                'enableRateLimit': True
            })
            exchange.set_sandbox_mode(Config.SANDBOX_MODE)
            exchange.load_markets()

            # Calculate since timestamp
            since = exchange.milliseconds() - (days * 24 * 60 * 60 * 1000)

            # Fetch all data
            all_ohlcv = []
            current_since = since

            while True:
                ohlcv = exchange.fetch_ohlcv(
                    symbol,
                    timeframe,
                    since=current_since,
                    limit=1000
                )

                if not ohlcv:
                    break

                all_ohlcv.extend(ohlcv)
                current_since = ohlcv[-1][0] + 1

                # Stop if we reached current time
                if current_since >= exchange.milliseconds():
                    break

                logger.info(f"Fetched {len(all_ohlcv)} candles...")

            # Convert to DataFrame
            df = pd.DataFrame(
                all_ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            logger.info(f"Fetched {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            raise

    def prepare_data(
        self,
        df_1m: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Prepare multi-timeframe data from 1-minute data

        Args:
            df_1m: 1-minute OHLCV data

        Returns:
            Tuple of (df_1m, df_15m, df_4h)
        """
        # Resample to 15m
        df_15m = df_1m.set_index('timestamp').resample('15T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna().reset_index()

        # Resample to 4h
        df_4h = df_1m.set_index('timestamp').resample('4H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna().reset_index()

        return df_1m, df_15m, df_4h

    def simulate_trade(
        self,
        signal: str,
        price: float,
        timestamp: datetime,
        atr: float
    ):
        """
        Simulate opening/closing trades

        Args:
            signal: Trading signal
            price: Current price
            timestamp: Current timestamp
            atr: Current ATR
        """
        # Close opposite position if exists
        if signal == 'LONG' and 'short' in self.positions:
            self.close_position('short', price, timestamp, "Reversal")
        elif signal == 'SHORT' and 'long' in self.positions:
            self.close_position('long', price, timestamp, "Reversal")

        # Open new position
        if signal == 'LONG' and 'long' not in self.positions:
            position_size = Config.POSITION_SIZE / price
            stop_loss = self.risk_manager.calculate_stop_loss(price, 'long', atr)

            self.positions['long'] = {
                'entry_price': price,
                'size': position_size,
                'timestamp': timestamp,
                'stop_loss': stop_loss
            }

            logger.debug(f"Opened LONG at ${price:.2f}")

        elif signal == 'SHORT' and 'short' not in self.positions:
            position_size = Config.POSITION_SIZE / price
            stop_loss = self.risk_manager.calculate_stop_loss(price, 'short', atr)

            self.positions['short'] = {
                'entry_price': price,
                'size': position_size,
                'timestamp': timestamp,
                'stop_loss': stop_loss
            }

            logger.debug(f"Opened SHORT at ${price:.2f}")

    def close_position(
        self,
        side: str,
        price: float,
        timestamp: datetime,
        reason: str
    ):
        """
        Close a position

        Args:
            side: Position side
            price: Exit price
            timestamp: Current timestamp
            reason: Close reason
        """
        if side not in self.positions:
            return

        position = self.positions[side]
        entry_price = position['entry_price']
        size = position['size']

        # Calculate PnL
        if side == 'long':
            pnl = (price - entry_price) * size * Config.LEVERAGE
        else:
            pnl = (entry_price - price) * size * Config.LEVERAGE

        # Update balance
        self.balance += pnl

        # Record trade
        trade = {
            'side': side,
            'entry_price': entry_price,
            'exit_price': price,
            'entry_time': position['timestamp'],
            'exit_time': timestamp,
            'pnl': pnl,
            'pnl_percent': (pnl / Config.POSITION_SIZE) * 100,
            'reason': reason
        }

        self.trades.append(trade)
        self.total_trades += 1

        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        logger.debug(
            f"Closed {side.upper()}: PnL=${pnl:.2f} ({trade['pnl_percent']:.2f}%) | {reason}"
        )

        # Remove position
        del self.positions[side]

    def check_stops(self, price: float, timestamp: datetime):
        """
        Check if any stops are hit

        Args:
            price: Current price
            timestamp: Current timestamp
        """
        for side in list(self.positions.keys()):
            position = self.positions[side]
            stop_loss = position['stop_loss']

            # Check stop loss
            if side == 'long' and price <= stop_loss:
                self.close_position(side, stop_loss, timestamp, "Stop loss")
            elif side == 'short' and price >= stop_loss:
                self.close_position(side, stop_loss, timestamp, "Stop loss")

    def run_backtest(
        self,
        df_1m: pd.DataFrame,
        df_15m: pd.DataFrame,
        df_4h: pd.DataFrame
    ):
        """
        Run backtest on historical data

        Args:
            df_1m: 1-minute data
            df_15m: 15-minute data
            df_4h: 4-hour data
        """
        logger.info("Starting backtest...")
        logger.info(f"Initial balance: ${self.initial_balance:.2f}")

        # Track signal statistics
        signal_count = {'LONG': 0, 'SHORT': 0, 'HOLD': 0}
        max_score = 0
        min_score = 0

        # Ensure we have enough data for indicators (different for each timeframe)
        min_length_1m = max(Config.RSI_PERIOD, Config.EMA_PERIOD, Config.ATR_PERIOD) + 50
        min_length_15m = max(Config.RSI_PERIOD, Config.EMA_PERIOD, Config.ATR_PERIOD) + 10
        min_length_4h = max(Config.RSI_PERIOD, Config.EMA_PERIOD, Config.ATR_PERIOD) + 5

        logger.info(f"Starting backtest loop: Processing {len(df_1m) - min_length_1m} candles")
        logger.info(f"Data available: 1m={len(df_1m)}, 15m={len(df_15m)}, 4h={len(df_4h)}")
        logger.info(f"Min lengths: 1m={min_length_1m}, 15m={min_length_15m}, 4h={min_length_4h}")

        # Iterate through 1m candles
        loop_count = 0
        skipped_count = 0
        for i in range(min_length_1m, len(df_1m)):
            loop_count += 1
            # Get current data windows
            current_1m = df_1m.iloc[:i+1]
            current_timestamp = current_1m.iloc[-1]['timestamp']
            current_price = current_1m.iloc[-1]['close']

            # Get corresponding 15m and 4h data
            current_15m = df_15m[df_15m['timestamp'] <= current_timestamp]
            current_4h = df_4h[df_4h['timestamp'] <= current_timestamp]

            # Check if we have enough data for each timeframe
            if len(current_15m) < min_length_15m or len(current_4h) < min_length_4h:
                skipped_count += 1
                if skipped_count == 1:
                    logger.debug(f"Skipping early candles: 15m={len(current_15m)}/{min_length_15m}, 4h={len(current_4h)}/{min_length_4h}")
                continue

            # Calculate indicators
            indicators_1m = self.indicator_calculator.calculate_all_indicators(
                current_1m.tail(250),
                '1m'
            )
            indicators_15m = self.indicator_calculator.calculate_all_indicators(
                current_15m.tail(250),
                '15m'
            )
            indicators_4h = self.indicator_calculator.calculate_all_indicators(
                current_4h.tail(250),
                '4h'
            )

            # Log first indicator values for debugging
            if loop_count == 1:
                logger.debug(f"First indicators_1m: {list(indicators_1m.keys())}")
                logger.debug(f"Sample values - RSI: {indicators_1m.get('rsi')}, EMA: {indicators_1m.get('ema')}")

            # Generate signal
            signal, score, reason = self.signal_generator.generate_signal(
                indicators_1m,
                indicators_15m,
                indicators_4h
            )

            # Log first few signals for debugging
            if loop_count <= 5:
                logger.debug(f"Loop {loop_count}: signal={signal}, score={score}, reason={reason}")

            # Track signal statistics
            signal_count[signal] += 1
            max_score = max(max_score, score)
            min_score = min(min_score, score)

            # Log high score signals for debugging
            if abs(score) >= 60:
                logger.debug(
                    f"Strong signal: {signal} | Score: {score} | "
                    f"Price: ${current_price:.2f} | {reason}"
                )

            # Check stops
            self.check_stops(current_price, current_timestamp)

            # Execute signal
            if signal != 'HOLD':
                atr = indicators_1m.get('atr', current_price * 0.02)
                self.simulate_trade(signal, current_price, current_timestamp, atr)

            # Record equity
            equity = self.balance
            for side, pos in self.positions.items():
                if side == 'long':
                    unrealized = (current_price - pos['entry_price']) * pos['size'] * Config.LEVERAGE
                else:
                    unrealized = (pos['entry_price'] - current_price) * pos['size'] * Config.LEVERAGE
                equity += unrealized

            self.equity_curve.append({
                'timestamp': current_timestamp,
                'equity': equity
            })

            # Update max drawdown
            peak = max([e['equity'] for e in self.equity_curve])
            drawdown = (peak - equity) / peak
            self.max_drawdown = max(self.max_drawdown, drawdown)

            # Log progress every 1000 candles
            if i % 1000 == 0:
                logger.info(
                    f"Progress: {i}/{len(df_1m)} candles | "
                    f"Balance: ${self.balance:.2f} | "
                    f"Trades: {self.total_trades}"
                )

        # Close any open positions
        for side in list(self.positions.keys()):
            self.close_position(
                side,
                df_1m.iloc[-1]['close'],
                df_1m.iloc[-1]['timestamp'],
                "End of backtest"
            )

        # Log signal statistics
        logger.info("Backtest completed")
        logger.info(f"Total loop iterations: {loop_count}")
        logger.info(f"Skipped iterations (insufficient data): {skipped_count}")
        logger.info(f"Processed iterations: {loop_count - skipped_count}")
        logger.info(f"Signal Statistics:")
        logger.info(f"  LONG signals: {signal_count['LONG']}")
        logger.info(f"  SHORT signals: {signal_count['SHORT']}")
        logger.info(f"  HOLD signals: {signal_count['HOLD']}")
        logger.info(f"  Max score: {max_score}")
        logger.info(f"  Min score: {min_score}")
        logger.info(f"  Signal threshold: LONG>={Config.SIGNAL_THRESHOLD_LONG}, SHORT<=-{Config.SIGNAL_THRESHOLD_LONG}")

    def generate_report(self) -> Dict:
        """
        Generate backtest report

        Returns:
            Dictionary with backtest results
        """
        if self.total_trades == 0:
            logger.warning("No trades executed during backtest")
            return {}

        # Calculate statistics
        win_rate = (self.winning_trades / self.total_trades) * 100
        total_return = ((self.balance - self.initial_balance) / self.initial_balance) * 100

        # Calculate Sharpe ratio
        if self.trades:
            returns = [t['pnl_percent'] for t in self.trades]
            sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0

        # Profit factor
        gross_profit = sum([t['pnl'] for t in self.trades if t['pnl'] > 0])
        gross_loss = abs(sum([t['pnl'] for t in self.trades if t['pnl'] < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        report = {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'total_return': total_return,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'max_drawdown': self.max_drawdown * 100,
            'sharpe_ratio': sharpe,
            'profit_factor': profit_factor,
            'average_win': gross_profit / self.winning_trades if self.winning_trades > 0 else 0,
            'average_loss': gross_loss / self.losing_trades if self.losing_trades > 0 else 0
        }

        return report

    def print_report(self):
        """Print formatted backtest report"""
        report = self.generate_report()

        if not report:
            logger.error("No report data available")
            return

        print("\n" + "=" * 60)
        print("BACKTEST REPORT")
        print("=" * 60)
        print(f"Initial Balance:    ${report['initial_balance']:,.2f}")
        print(f"Final Balance:      ${report['final_balance']:,.2f}")
        print(f"Total Return:       {report['total_return']:.2f}%")
        print("-" * 60)
        print(f"Total Trades:       {report['total_trades']}")
        print(f"Winning Trades:     {report['winning_trades']}")
        print(f"Losing Trades:      {report['losing_trades']}")
        print(f"Win Rate:           {report['win_rate']:.2f}%")
        print("-" * 60)
        print(f"Max Drawdown:       {report['max_drawdown']:.2f}%")
        print(f"Sharpe Ratio:       {report['sharpe_ratio']:.2f}")
        print(f"Profit Factor:      {report['profit_factor']:.2f}")
        print(f"Average Win:        ${report['average_win']:.2f}")
        print(f"Average Loss:       ${report['average_loss']:.2f}")
        print("=" * 60 + "\n")

    def save_results(self, filename: str = "backtest_results.json"):
        """
        Save backtest results to file

        Args:
            filename: Output filename
        """
        results = {
            'report': self.generate_report(),
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }

        output_path = Path(__file__).parent / filename

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Results saved to {output_path}")


def main():
    """Run backtest"""
    logging.basicConfig(
        level=logging.DEBUG,  # Changed to DEBUG to see signal details
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    backtester = Backtester()

    # Fetch historical data (6 days - Gate.io testnet limit: 10,000 candles)
    # 6 days * 24 hours * 60 minutes = 8,640 candles < 10,000 limit
    df_1m = backtester.fetch_historical_data(
        Config.TRADING_PAIR,
        '1m',
        days=6
    )

    # Prepare multi-timeframe data
    df_1m, df_15m, df_4h = backtester.prepare_data(df_1m)

    # Run backtest
    backtester.run_backtest(df_1m, df_15m, df_4h)

    # Print report
    backtester.print_report()

    # Save results
    backtester.save_results()


if __name__ == "__main__":
    main()
