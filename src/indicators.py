"""
Technical indicators calculation module
Supports RSI, EMA, MACD, ATR, Bollinger Bands, and more
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
import logging
from config import Config

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """Calculate technical indicators from OHLCV data"""

    def __init__(self):
        """Initialize indicator calculator"""
        self.previous_indicators: Dict[str, Dict] = {}

    @staticmethod
    def calculate_rsi(prices: np.ndarray, period: int = 14) -> Optional[float]:
        """
        Calculate Relative Strength Index

        Args:
            prices: Array of closing prices
            period: RSI period (default 14)

        Returns:
            RSI value or None if insufficient data
        """
        if len(prices) < period + 1:
            return None

        # Calculate price changes
        deltas = np.diff(prices)

        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Calculate average gains and losses
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        # Avoid division by zero
        if avg_loss == 0:
            return 100.0

        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi)

    @staticmethod
    def calculate_ema(prices: np.ndarray, period: int = 20) -> Optional[float]:
        """
        Calculate Exponential Moving Average

        Args:
            prices: Array of closing prices
            period: EMA period (default 20)

        Returns:
            EMA value or None if insufficient data
        """
        if len(prices) < period:
            return None

        # Calculate multiplier
        multiplier = 2 / (period + 1)

        # Start with SMA
        ema = np.mean(prices[:period])

        # Calculate EMA for remaining prices
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return float(ema)

    @staticmethod
    def calculate_macd(
        prices: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Optional[Tuple[float, float, float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence)

        Args:
            prices: Array of closing prices
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line period (default 9)

        Returns:
            Tuple of (macd, signal, histogram) or None if insufficient data
        """
        if len(prices) < slow + signal:
            return None

        # Calculate EMAs
        ema_fast = pd.Series(prices).ewm(span=fast, adjust=False).mean()
        ema_slow = pd.Series(prices).ewm(span=slow, adjust=False).mean()

        # Calculate MACD line
        macd_line = ema_fast - ema_slow

        # Calculate signal line
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()

        # Calculate histogram
        histogram = macd_line - signal_line

        return (
            float(macd_line.iloc[-1]),
            float(signal_line.iloc[-1]),
            float(histogram.iloc[-1])
        )

    @staticmethod
    def calculate_atr(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> Optional[float]:
        """
        Calculate Average True Range

        Args:
            high: Array of high prices
            low: Array of low prices
            close: Array of closing prices
            period: ATR period (default 14)

        Returns:
            ATR value or None if insufficient data
        """
        if len(close) < period + 1:
            return None

        # Calculate true ranges
        high_low = high[1:] - low[1:]
        high_close = np.abs(high[1:] - close[:-1])
        low_close = np.abs(low[1:] - close[:-1])

        true_ranges = np.maximum(high_low, np.maximum(high_close, low_close))

        # Calculate ATR
        atr = np.mean(true_ranges[-period:])

        return float(atr)

    @staticmethod
    def calculate_bollinger_bands(
        prices: np.ndarray,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Optional[Tuple[float, float, float]]:
        """
        Calculate Bollinger Bands

        Args:
            prices: Array of closing prices
            period: Period for moving average (default 20)
            std_dev: Number of standard deviations (default 2.0)

        Returns:
            Tuple of (upper, middle, lower) or None if insufficient data
        """
        if len(prices) < period:
            return None

        # Calculate middle band (SMA)
        middle = np.mean(prices[-period:])

        # Calculate standard deviation
        std = np.std(prices[-period:])

        # Calculate upper and lower bands
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        return float(upper), float(middle), float(lower)

    @staticmethod
    def calculate_stochastic(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> Optional[float]:
        """
        Calculate Stochastic Oscillator

        Args:
            high: Array of high prices
            low: Array of low prices
            close: Array of closing prices
            period: Stochastic period (default 14)

        Returns:
            Stochastic K value or None if insufficient data
        """
        if len(close) < period:
            return None

        # Get the period slice
        period_high = high[-period:]
        period_low = low[-period:]
        current_close = close[-1]

        # Calculate %K
        highest_high = np.max(period_high)
        lowest_low = np.min(period_low)

        if highest_high == lowest_low:
            return 50.0

        stoch_k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100

        return float(stoch_k)

    @staticmethod
    def calculate_volume_spike(volumes: np.ndarray, threshold: float = 2.0) -> bool:
        """
        Detect volume spike

        Args:
            volumes: Array of volumes
            threshold: Multiplier threshold (default 2.0 = 200%)

        Returns:
            True if volume spike detected
        """
        if len(volumes) < 20:
            return False

        # Calculate average volume
        avg_volume = np.mean(volumes[-20:-1])

        # Check if current volume is spike
        current_volume = volumes[-1]

        if avg_volume == 0:
            return False

        return current_volume / avg_volume >= threshold

    @staticmethod
    def calculate_obv(close: np.ndarray, volume: np.ndarray) -> Optional[float]:
        """
        Calculate On-Balance Volume

        Args:
            close: Array of closing prices
            volume: Array of volumes

        Returns:
            OBV value or None if insufficient data
        """
        if len(close) < 2:
            return None

        obv = 0
        for i in range(1, len(close)):
            if close[i] > close[i - 1]:
                obv += volume[i]
            elif close[i] < close[i - 1]:
                obv -= volume[i]

        return float(obv)

    def calculate_ema_trend(self, prices: np.ndarray, period: int = 20) -> int:
        """
        Calculate EMA trend direction

        Args:
            prices: Array of closing prices
            period: EMA period

        Returns:
            1 for uptrend, -1 for downtrend, 0 for neutral
        """
        if len(prices) < period + 1:
            return 0

        # Calculate current and previous EMA
        current_ema = self.calculate_ema(prices, period)
        previous_ema = self.calculate_ema(prices[:-1], period)

        if current_ema is None or previous_ema is None:
            return 0

        if current_ema > previous_ema:
            return 1
        elif current_ema < previous_ema:
            return -1
        return 0

    def calculate_all_indicators(
        self,
        df: pd.DataFrame,
        timeframe: str
    ) -> Dict[str, any]:
        """
        Calculate all indicators for a dataframe

        Args:
            df: DataFrame with OHLCV data
            timeframe: Timeframe identifier

        Returns:
            Dictionary of indicator values
        """
        indicators = {}

        try:
            # Convert to numpy arrays
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            volume = df['volume'].values

            # RSI
            indicators['rsi'] = self.calculate_rsi(close, Config.RSI_PERIOD)

            # EMA
            indicators['ema'] = self.calculate_ema(close, Config.EMA_PERIOD)
            indicators['ema_trend'] = self.calculate_ema_trend(close, Config.EMA_PERIOD)

            # MACD
            macd_result = self.calculate_macd(
                close,
                Config.MACD_FAST,
                Config.MACD_SLOW,
                Config.MACD_SIGNAL
            )
            if macd_result:
                indicators['macd'], indicators['macd_signal'], indicators['macd_hist'] = macd_result
            else:
                indicators['macd'] = indicators['macd_signal'] = indicators['macd_hist'] = None

            # ATR
            indicators['atr'] = self.calculate_atr(high, low, close, Config.ATR_PERIOD)

            # Bollinger Bands
            bb_result = self.calculate_bollinger_bands(close)
            if bb_result:
                indicators['bb_upper'], indicators['bb_middle'], indicators['bb_lower'] = bb_result
            else:
                indicators['bb_upper'] = indicators['bb_middle'] = indicators['bb_lower'] = None

            # Stochastic
            indicators['stoch'] = self.calculate_stochastic(high, low, close)

            # Volume indicators
            indicators['volume_spike'] = self.calculate_volume_spike(
                volume,
                Config.VOLUME_SPIKE_THRESHOLD
            )
            indicators['obv'] = self.calculate_obv(close, volume)

            # Store previous values for comparison
            key = timeframe
            if key in self.previous_indicators:
                indicators['rsi_prev'] = self.previous_indicators[key].get('rsi')
                indicators['atr_prev'] = self.previous_indicators[key].get('atr')
            else:
                indicators['rsi_prev'] = indicators['rsi']
                indicators['atr_prev'] = indicators['atr']

            # Update previous indicators
            self.previous_indicators[key] = indicators.copy()

            logger.debug(f"Calculated indicators for {timeframe}: {indicators}")

        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}

        return indicators

    def get_indicator_summary(self, indicators: Dict) -> str:
        """
        Get human-readable summary of indicators

        Args:
            indicators: Dictionary of indicator values

        Returns:
            Summary string
        """
        summary_parts = []

        if indicators.get('rsi') is not None:
            rsi = indicators['rsi']
            if rsi < 30:
                summary_parts.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 70:
                summary_parts.append(f"RSI overbought ({rsi:.1f})")
            else:
                summary_parts.append(f"RSI neutral ({rsi:.1f})")

        if indicators.get('ema_trend') == 1:
            summary_parts.append("EMA uptrend")
        elif indicators.get('ema_trend') == -1:
            summary_parts.append("EMA downtrend")

        if indicators.get('volume_spike'):
            summary_parts.append("Volume spike detected")

        if indicators.get('macd_hist') is not None:
            if indicators['macd_hist'] > 0:
                summary_parts.append("MACD bullish")
            else:
                summary_parts.append("MACD bearish")

        return ", ".join(summary_parts) if summary_parts else "No clear signals"
