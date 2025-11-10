"""
Signal generation module using multi-timeframe analysis
Implements the "Golden Triple Rule" strategy
"""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generate trading signals based on multi-timeframe technical analysis"""

    def __init__(self):
        """Initialize signal generator"""
        self.last_signal = None
        self.last_signal_time = None
        self.signal_history = []

    def check_golden_triple_rule(
        self,
        indicators_1m: Dict,
        indicators_15m: Dict,
        indicators_4h: Dict
    ) -> Tuple[int, str]:
        """
        Apply Golden Triple Rule for signal generation (ENHANCED FOR HIGH ACCURACY)

        Rule 1: 4h EMA trend must be aligned (30 points)
        Rule 2: 15m RSI in favorable zone OR reversal (30 points)
        Rule 3: 1m volume spike (40 points)

        PLUS Multi-timeframe trend alignment bonus (20 points)
        PLUS Strong momentum confirmation (10 points)

        Args:
            indicators_1m: 1-minute indicators
            indicators_15m: 15-minute indicators
            indicators_4h: 4-hour indicators

        Returns:
            Tuple of (score, reason)
        """
        score = 0
        reasons = []

        # Rule 1: 4h EMA Trend (weight: 30) - MANDATORY for direction
        ema_trend_4h = indicators_4h.get('ema_trend', 0)
        if ema_trend_4h > 0:
            score += 30
            reasons.append("4h EMA uptrend")
        elif ema_trend_4h < 0:
            score -= 30
            reasons.append("4h EMA downtrend")

        # Rule 2: 15m RSI Zone (weight: 30) - ENHANCED
        rsi_15m = indicators_15m.get('rsi')
        rsi_prev_15m = indicators_15m.get('rsi_prev')

        if rsi_15m is not None and rsi_prev_15m is not None:
            # LONG signals: RSI oversold or recovering from oversold
            if rsi_15m < Config.RSI_OVERSOLD:
                score += 30
                reasons.append(f"15m RSI oversold zone ({rsi_15m:.1f})")
            elif rsi_prev_15m < Config.RSI_OVERSOLD and rsi_15m >= Config.RSI_OVERSOLD:
                score += 35  # Extra 5 points for actual reversal
                reasons.append(f"15m RSI reversal from oversold ({rsi_15m:.1f})")
            elif Config.RSI_OVERSOLD <= rsi_15m <= 45:
                score += 20  # Partial score for favorable zone
                reasons.append(f"15m RSI favorable zone ({rsi_15m:.1f})")

            # SHORT signals: RSI overbought or dropping from overbought
            elif rsi_15m > Config.RSI_OVERBOUGHT:
                score -= 30
                reasons.append(f"15m RSI overbought zone ({rsi_15m:.1f})")
            elif rsi_prev_15m > Config.RSI_OVERBOUGHT and rsi_15m <= Config.RSI_OVERBOUGHT:
                score -= 35  # Extra 5 points for actual reversal
                reasons.append(f"15m RSI reversal from overbought ({rsi_15m:.1f})")
            elif 55 <= rsi_15m <= Config.RSI_OVERBOUGHT:
                score -= 20  # Partial score for favorable zone
                reasons.append(f"15m RSI favorable zone ({rsi_15m:.1f})")

        # Rule 3: 1m Volume Spike (weight: 40)
        if indicators_1m.get('volume_spike', False):
            score += 40
            reasons.append("1m volume spike detected")

        # BONUS: Multi-timeframe trend alignment (weight: 20)
        ema_trend_1m = indicators_1m.get('ema_trend', 0)
        ema_trend_15m = indicators_15m.get('ema_trend', 0)

        if ema_trend_1m == ema_trend_15m == ema_trend_4h:
            if ema_trend_4h > 0:
                score += 20
                reasons.append("All timeframes bullish aligned")
            elif ema_trend_4h < 0:
                score -= 20
                reasons.append("All timeframes bearish aligned")

        # BONUS: Strong momentum (weight: 10)
        macd_hist_15m = indicators_15m.get('macd_hist')
        if macd_hist_15m is not None:
            if macd_hist_15m > 20:  # Strong bullish momentum
                score += 10
                reasons.append("Strong bullish momentum")
            elif macd_hist_15m < -20:  # Strong bearish momentum
                score -= 10
                reasons.append("Strong bearish momentum")

        reason = " | ".join(reasons) if reasons else "No clear signals"
        return score, reason

    def check_momentum_veto(self, indicators_1m: Dict) -> Tuple[bool, str]:
        """
        Check for sudden momentum change that could veto signal

        Args:
            indicators_1m: 1-minute indicators

        Returns:
            Tuple of (veto, reason)
        """
        atr = indicators_1m.get('atr')
        atr_prev = indicators_1m.get('atr_prev')

        if atr is None or atr_prev is None or atr_prev == 0:
            return False, ""

        atr_change = (atr - atr_prev) / atr_prev

        # Sudden crash detection
        if atr_change < Config.MOMENTUM_VETO_THRESHOLD:
            return True, f"Momentum veto: ATR crash ({atr_change*100:.1f}%)"

        return False, ""

    def check_additional_confirmations(
        self,
        indicators_1m: Dict,
        indicators_15m: Dict
    ) -> Tuple[int, str]:
        """
        Check additional confirmation signals

        Args:
            indicators_1m: 1-minute indicators
            indicators_15m: 15-minute indicators

        Returns:
            Tuple of (additional_score, reasons)
        """
        additional_score = 0
        reasons = []

        # MACD confirmation
        macd_hist_1m = indicators_1m.get('macd_hist')
        if macd_hist_1m is not None:
            if macd_hist_1m > 0:
                additional_score += 10
                reasons.append("MACD bullish")
            elif macd_hist_1m < 0:
                additional_score -= 10
                reasons.append("MACD bearish")

        # Bollinger Bands
        close_price = indicators_1m.get('close')
        bb_lower = indicators_1m.get('bb_lower')
        bb_upper = indicators_1m.get('bb_upper')

        if close_price and bb_lower and bb_upper:
            if close_price < bb_lower:
                additional_score += 10
                reasons.append("Price below BB lower")
            elif close_price > bb_upper:
                additional_score -= 10
                reasons.append("Price above BB upper")

        # Stochastic
        stoch = indicators_15m.get('stoch')
        if stoch is not None:
            if stoch < 20:
                additional_score += 5
                reasons.append(f"Stochastic oversold ({stoch:.1f})")
            elif stoch > 80:
                additional_score -= 5
                reasons.append(f"Stochastic overbought ({stoch:.1f})")

        reason = " | ".join(reasons) if reasons else ""
        return additional_score, reason

    def generate_signal(
        self,
        indicators_1m: Dict,
        indicators_15m: Dict,
        indicators_4h: Dict,
        funding_rate: Optional[float] = None
    ) -> Tuple[str, int, str]:
        """
        Generate trading signal based on all indicators

        Args:
            indicators_1m: 1-minute timeframe indicators
            indicators_15m: 15-minute timeframe indicators
            indicators_4h: 4-hour timeframe indicators
            funding_rate: Current funding rate (optional)

        Returns:
            Tuple of (signal, score, reason)
            signal: 'LONG', 'SHORT', or 'HOLD'
            score: Signal strength score
            reason: Human-readable explanation
        """
        try:
            # Check momentum veto first
            veto, veto_reason = self.check_momentum_veto(indicators_1m)
            if veto:
                logger.warning(f"Signal vetoed: {veto_reason}")
                return 'HOLD', 0, veto_reason

            # Calculate base score using Golden Triple Rule
            base_score, base_reason = self.check_golden_triple_rule(
                indicators_1m,
                indicators_15m,
                indicators_4h
            )

            # Add additional confirmations
            additional_score, additional_reason = self.check_additional_confirmations(
                indicators_1m,
                indicators_15m
            )

            # Calculate total score
            total_score = base_score + additional_score

            # Build full reason
            full_reason = base_reason
            if additional_reason:
                full_reason += f" + {additional_reason}"

            # Add funding rate consideration
            if funding_rate is not None:
                if funding_rate > 0.01:  # High positive funding (longs pay shorts)
                    total_score -= 5
                    full_reason += f" | High funding rate ({funding_rate*100:.3f}%)"
                elif funding_rate < -0.01:  # High negative funding (shorts pay longs)
                    total_score += 5
                    full_reason += f" | Negative funding rate ({funding_rate*100:.3f}%)"

            # Determine signal based on score
            if total_score >= Config.SIGNAL_THRESHOLD_LONG:
                signal = 'LONG'
            elif total_score <= -Config.SIGNAL_THRESHOLD_LONG:
                signal = 'SHORT'
            else:
                signal = 'HOLD'

            # Log signal generation
            logger.info(
                f"Signal: {signal} | Score: {total_score} | {full_reason}"
            )

            # Store signal
            self.last_signal = signal
            self.last_signal_time = datetime.now()
            self.signal_history.append({
                'time': self.last_signal_time,
                'signal': signal,
                'score': total_score,
                'reason': full_reason
            })

            # Keep only last 100 signals
            if len(self.signal_history) > 100:
                self.signal_history.pop(0)

            return signal, total_score, full_reason

        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return 'HOLD', 0, f"Error: {str(e)}"

    def check_reversal_signal(
        self,
        current_position: Optional[str],
        new_signal: str,
        indicators_15m: Dict
    ) -> bool:
        """
        Check if signal indicates position reversal

        Args:
            current_position: Current position ('LONG' or 'SHORT')
            new_signal: New generated signal
            indicators_15m: 15-minute indicators for confirmation

        Returns:
            True if should reverse position
        """
        if not current_position or current_position == 'HOLD':
            return False

        # Check for strong reversal signal
        rsi = indicators_15m.get('rsi')
        if rsi is None:
            return False

        # Long position, check for bearish reversal
        if current_position == 'LONG' and new_signal == 'SHORT':
            if rsi > Config.RSI_OVERBOUGHT:
                logger.info("Strong reversal signal detected: LONG -> SHORT")
                return True

        # Short position, check for bullish reversal
        if current_position == 'SHORT' and new_signal == 'LONG':
            if rsi < Config.RSI_OVERSOLD:
                logger.info("Strong reversal signal detected: SHORT -> LONG")
                return True

        return False

    def get_signal_strength(self, score: int) -> str:
        """
        Get signal strength description

        Args:
            score: Signal score

        Returns:
            Strength description
        """
        abs_score = abs(score)

        if abs_score >= 90:
            return "Very Strong"
        elif abs_score >= 80:
            return "Strong"
        elif abs_score >= 60:
            return "Moderate"
        elif abs_score >= 40:
            return "Weak"
        else:
            return "Very Weak"

    def get_signal_summary(self) -> Dict:
        """
        Get summary of recent signals

        Returns:
            Dictionary with signal statistics
        """
        if not self.signal_history:
            return {
                'total_signals': 0,
                'long_signals': 0,
                'short_signals': 0,
                'hold_signals': 0
            }

        long_count = sum(1 for s in self.signal_history if s['signal'] == 'LONG')
        short_count = sum(1 for s in self.signal_history if s['signal'] == 'SHORT')
        hold_count = sum(1 for s in self.signal_history if s['signal'] == 'HOLD')

        return {
            'total_signals': len(self.signal_history),
            'long_signals': long_count,
            'short_signals': short_count,
            'hold_signals': hold_count,
            'last_signal': self.last_signal,
            'last_signal_time': self.last_signal_time
        }

    def should_wait_for_cooldown(self, last_trade_time: Optional[datetime]) -> bool:
        """
        Check if should wait due to cooldown period

        Args:
            last_trade_time: Time of last trade

        Returns:
            True if should wait
        """
        if not last_trade_time:
            return False

        elapsed = (datetime.now() - last_trade_time).total_seconds()
        remaining = Config.COOLDOWN_PERIOD - elapsed

        if remaining > 0:
            logger.info(f"Cooldown active: {remaining:.0f} seconds remaining")
            return True

        return False
