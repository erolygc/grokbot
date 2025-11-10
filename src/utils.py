"""
Utility functions for logging, notifications, and common operations
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import requests


def setup_logger(name: str, log_file: Path, level: str = 'INFO') -> logging.Logger:
    """
    Set up logger with file and console handlers

    Args:
        name: Logger name
        log_file: Path to log file
        level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger
    """
    # Create logs directory if it doesn't exist
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(getattr(logging, level.upper()))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


class TelegramNotifier:
    """Send notifications via Telegram"""

    def __init__(self, bot_token: Optional[str], chat_id: Optional[str]):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)

    def send_message(self, message: str) -> bool:
        """
        Send message to Telegram

        Args:
            message: Message text

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")
            return False

    def send_trade_alert(self, signal: str, price: float, reason: str) -> bool:
        """
        Send trade signal alert

        Args:
            signal: LONG, SHORT, or CLOSE
            price: Current price
            reason: Signal reason

        Returns:
            True if successful
        """
        emoji = "📈" if signal == "LONG" else "📉" if signal == "SHORT" else "⚠️"
        message = (
            f"{emoji} <b>{signal} Signal</b>\n"
            f"Price: ${price:,.2f}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Reason: {reason}"
        )
        return self.send_message(message)

    def send_error_alert(self, error: str) -> bool:
        """
        Send error alert

        Args:
            error: Error message

        Returns:
            True if successful
        """
        message = f"🚨 <b>Error Alert</b>\n{error}"
        return self.send_message(message)


def calculate_position_size(
    balance: float,
    position_size_usd: float,
    leverage: int,
    price: float
) -> float:
    """
    Calculate position size in contracts

    Args:
        balance: Account balance in USD
        position_size_usd: Desired position size in USD
        leverage: Leverage multiplier
        price: Current price

    Returns:
        Position size in contracts
    """
    # Calculate how much we can actually trade
    max_size = balance * leverage
    actual_size = min(position_size_usd, max_size)

    # Convert USD to contracts
    contracts = actual_size / price

    return contracts


def format_number(number: float, decimals: int = 2) -> str:
    """
    Format number with commas and specified decimals

    Args:
        number: Number to format
        decimals: Number of decimal places

    Returns:
        Formatted string
    """
    return f"{number:,.{decimals}f}"


def save_state(state: Dict[str, Any], file_path: Path) -> bool:
    """
    Save state to JSON file

    Args:
        state: State dictionary
        file_path: Path to save file

    Returns:
        True if successful
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, default=str)
        return True
    except Exception as e:
        logging.error(f"Failed to save state: {e}")
        return False


def load_state(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load state from JSON file

    Args:
        file_path: Path to load file

    Returns:
        State dictionary or None if failed
    """
    try:
        if not file_path.exists():
            return None

        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load state: {e}")
        return None


def get_cooldown_key(pair: str) -> str:
    """
    Generate cooldown cache key

    Args:
        pair: Trading pair

    Returns:
        Cache key string
    """
    return f"cooldown_{pair.replace('/', '_')}"


def is_in_cooldown(last_trade_time: Optional[datetime], cooldown_seconds: int) -> bool:
    """
    Check if still in cooldown period

    Args:
        last_trade_time: Time of last trade
        cooldown_seconds: Cooldown period in seconds

    Returns:
        True if in cooldown
    """
    if not last_trade_time:
        return False

    elapsed = (datetime.now() - last_trade_time).total_seconds()
    return elapsed < cooldown_seconds
