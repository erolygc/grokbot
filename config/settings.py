"""
Configuration settings for the crypto trading bot.
Loads environment variables and provides centralized configuration.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / '.env')


class Config:
    """Main configuration class"""

    # Gate.io API Configuration
    GATE_API_KEY = os.getenv('GATE_API_KEY')
    GATE_SECRET = os.getenv('GATE_SECRET')

    # Trading Configuration
    SANDBOX_MODE = os.getenv('SANDBOX_MODE', 'true').lower() == 'true'
    INITIAL_BALANCE = float(os.getenv('INITIAL_BALANCE', '10000'))
    LEVERAGE = int(os.getenv('LEVERAGE', '3'))
    POSITION_SIZE = float(os.getenv('POSITION_SIZE', '100'))
    TRADING_PAIR = os.getenv('TRADING_PAIR', 'BTC/USDT')

    # Risk Management
    MAX_DRAWDOWN = float(os.getenv('MAX_DRAWDOWN', '0.10'))
    STOP_LOSS_ATR_MULTIPLIER = float(os.getenv('STOP_LOSS_ATR_MULTIPLIER', '0.5'))
    TAKE_PROFIT_PERCENTAGE = float(os.getenv('TAKE_PROFIT_PERCENTAGE', '0.05'))
    MAX_EXPOSURE = float(os.getenv('MAX_EXPOSURE', '0.10'))

    # Redis Configuration
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_DB = int(os.getenv('REDIS_DB', '0'))
    USE_REDIS = os.getenv('USE_REDIS', 'false').lower() == 'true'

    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    USE_TELEGRAM = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = BASE_DIR / os.getenv('LOG_FILE', 'logs/trading_bot.log')

    # Technical Indicators Parameters
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    EMA_PERIOD = 20
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    ATR_PERIOD = 14
    VOLUME_SPIKE_THRESHOLD = 3.0  # 300% of average (ultra high quality)

    # Timeframes for multi-timeframe analysis
    TIMEFRAMES = {
        '1m': {'weight': 20, 'candles': 250},
        '15m': {'weight': 30, 'candles': 250},
        '4h': {'weight': 50, 'candles': 250}
    }

    # Signal Generation - ULTRA HIGH QUALITY MODE
    SIGNAL_THRESHOLD_LONG = 100  # Only perfect signals
    SIGNAL_THRESHOLD_SHORT = -100  # Only perfect signals
    MOMENTUM_VETO_THRESHOLD = -0.05  # -5% ATR change (protective)

    # Cooldown period after wrong signal (seconds)
    COOLDOWN_PERIOD = 600  # 10 minutes

    @classmethod
    def validate(cls):
        """Validate configuration"""
        if not cls.GATE_API_KEY or not cls.GATE_SECRET:
            raise ValueError("Gate.io API credentials not found in .env file")

        if cls.LEVERAGE < 1 or cls.LEVERAGE > 10:
            raise ValueError("Leverage must be between 1 and 10")

        if cls.POSITION_SIZE > cls.INITIAL_BALANCE:
            raise ValueError("Position size cannot exceed initial balance")

        return True


# Validate configuration on import
Config.validate()
