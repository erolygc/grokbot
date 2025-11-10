"""
Data collection module for fetching OHLCV data from Gate.io
Supports multiple timeframes and rolling window management
"""
import ccxt
import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
from collections import deque
from config import Config

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects and manages market data from Gate.io"""

    def __init__(self):
        """Initialize data collector with Gate.io exchange"""
        self.exchange = self._initialize_exchange()
        self.data_buffers: Dict[str, deque] = {}
        self._initialize_buffers()

    def _initialize_exchange(self) -> ccxt.gateio:
        """
        Initialize Gate.io exchange connection

        Returns:
            CCXT Gate.io exchange instance
        """
        try:
            exchange = ccxt.gateio({
                'apiKey': Config.GATE_API_KEY,
                'secret': Config.GATE_SECRET,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'sandboxMode': Config.SANDBOX_MODE
                }
            })

            # Set sandbox mode if enabled
            if Config.SANDBOX_MODE:
                exchange.set_sandbox_mode(True)
                logger.info("Exchange initialized in SANDBOX mode")
            else:
                logger.warning("Exchange initialized in LIVE mode")

            # Load markets
            exchange.load_markets()
            logger.info("Markets loaded successfully")

            return exchange

        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise

    def _initialize_buffers(self):
        """Initialize data buffers for each timeframe"""
        for timeframe in Config.TIMEFRAMES.keys():
            key = f"{Config.TRADING_PAIR}_{timeframe}"
            max_candles = Config.TIMEFRAMES[timeframe]['candles']
            self.data_buffers[key] = deque(maxlen=max_candles)
            logger.info(f"Initialized buffer for {key} with max {max_candles} candles")

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 250,
        since: Optional[int] = None
    ) -> List[List]:
        """
        Fetch OHLCV data from exchange

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '1m', '15m', '1h', '4h')
            limit: Number of candles to fetch
            since: Timestamp to fetch from (milliseconds)

        Returns:
            List of OHLCV candles
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol,
                timeframe,
                since=since,
                limit=limit
            )

            logger.debug(f"Fetched {len(ohlcv)} candles for {symbol} {timeframe}")
            return ohlcv

        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching OHLCV: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching OHLCV: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching OHLCV: {e}")
            raise

    def update_buffer(self, symbol: str, timeframe: str, candles: List[List]):
        """
        Update data buffer with new candles

        Args:
            symbol: Trading pair
            timeframe: Timeframe
            candles: List of OHLCV candles
        """
        key = f"{symbol}_{timeframe}"

        if key not in self.data_buffers:
            max_candles = Config.TIMEFRAMES.get(timeframe, {}).get('candles', 250)
            self.data_buffers[key] = deque(maxlen=max_candles)

        # Add new candles to buffer
        for candle in candles:
            self.data_buffers[key].append(candle)

        logger.debug(f"Updated buffer {key}, now has {len(self.data_buffers[key])} candles")

    def get_buffer(self, symbol: str, timeframe: str) -> Optional[List[List]]:
        """
        Get data buffer for specific symbol and timeframe

        Args:
            symbol: Trading pair
            timeframe: Timeframe

        Returns:
            List of candles or None if buffer doesn't exist
        """
        key = f"{symbol}_{timeframe}"
        buffer = self.data_buffers.get(key)

        if buffer:
            return list(buffer)
        return None

    def get_dataframe(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get data as pandas DataFrame

        Args:
            symbol: Trading pair
            timeframe: Timeframe

        Returns:
            DataFrame with OHLCV data or None
        """
        candles = self.get_buffer(symbol, timeframe)

        if not candles:
            return None

        df = pd.DataFrame(
            candles,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Convert price and volume columns to float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        return df

    def fetch_ticker(self, symbol: str) -> Dict:
        """
        Fetch current ticker data

        Args:
            symbol: Trading pair

        Returns:
            Ticker dictionary
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"Failed to fetch ticker: {e}")
            raise

    def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """
        Fetch order book data

        Args:
            symbol: Trading pair
            limit: Number of orders to fetch per side

        Returns:
            Order book dictionary with bids and asks
        """
        try:
            order_book = self.exchange.fetch_order_book(symbol, limit)
            return order_book
        except Exception as e:
            logger.error(f"Failed to fetch order book: {e}")
            raise

    def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Fetch current funding rate for futures

        Args:
            symbol: Trading pair

        Returns:
            Funding rate or None if not available
        """
        try:
            funding_rate = self.exchange.fetch_funding_rate(symbol)
            return funding_rate.get('fundingRate')
        except Exception as e:
            logger.warning(f"Failed to fetch funding rate: {e}")
            return None

    def calculate_liquidity_depth(self, order_book: Dict) -> Tuple[float, float]:
        """
        Calculate order book liquidity depth

        Args:
            order_book: Order book dictionary

        Returns:
            Tuple of (bid_depth, ask_depth) in USD
        """
        bid_depth = sum([bid[0] * bid[1] for bid in order_book.get('bids', [])])
        ask_depth = sum([ask[0] * ask[1] for ask in order_book.get('asks', [])])

        return bid_depth, ask_depth

    def initialize_historical_data(self):
        """
        Initialize buffers with historical data for all timeframes
        """
        logger.info(f"Initializing historical data for {Config.TRADING_PAIR}")

        for timeframe in Config.TIMEFRAMES.keys():
            limit = Config.TIMEFRAMES[timeframe]['candles']

            try:
                candles = self.fetch_ohlcv(
                    Config.TRADING_PAIR,
                    timeframe,
                    limit=limit
                )

                self.update_buffer(Config.TRADING_PAIR, timeframe, candles)
                logger.info(
                    f"Initialized {timeframe} with {len(candles)} candles"
                )

            except Exception as e:
                logger.error(f"Failed to initialize {timeframe}: {e}")

            # Rate limiting
            time.sleep(self.exchange.rateLimit / 1000)

    def update_all_timeframes(self):
        """
        Update all timeframes with latest candle
        """
        for timeframe in Config.TIMEFRAMES.keys():
            try:
                # Fetch only the latest candle
                candles = self.fetch_ohlcv(
                    Config.TRADING_PAIR,
                    timeframe,
                    limit=1
                )

                if candles:
                    # Check if it's a new candle or update of existing
                    buffer = self.data_buffers.get(f"{Config.TRADING_PAIR}_{timeframe}")
                    if buffer and len(buffer) > 0:
                        last_candle = buffer[-1]
                        new_candle = candles[0]

                        # If timestamps match, update last candle
                        if last_candle[0] == new_candle[0]:
                            buffer[-1] = new_candle
                        else:
                            # New candle, append to buffer
                            buffer.append(new_candle)
                    else:
                        # Buffer empty, add candle
                        self.update_buffer(Config.TRADING_PAIR, timeframe, candles)

                    logger.debug(f"Updated {timeframe} timeframe")

            except Exception as e:
                logger.error(f"Failed to update {timeframe}: {e}")

            # Rate limiting
            time.sleep(self.exchange.rateLimit / 1000)

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Get latest price for symbol

        Args:
            symbol: Trading pair

        Returns:
            Latest price or None
        """
        try:
            ticker = self.fetch_ticker(symbol)
            return ticker.get('last')
        except Exception as e:
            logger.error(f"Failed to get latest price: {e}")
            return None
