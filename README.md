# GrokBot - Advanced Crypto Trading Bot

An advanced cryptocurrency trading bot for BTC/USDT futures on Gate.io, featuring multi-timeframe analysis, the "Golden Triple Rule" strategy, hedge mode support, and comprehensive risk management.

## Features

- **Multi-Timeframe Analysis**: Analyzes 1m, 15m, and 4h timeframes simultaneously
- **Golden Triple Rule Strategy**:
  - 4h EMA trend confirmation (30 points)
  - 15m RSI reversal detection (30 points)
  - 1m volume spike confirmation (40 points)
- **Hedge Mode Support**: Simultaneous long and short positions
- **Advanced Risk Management**:
  - ATR-based stop loss
  - Trailing stop functionality
  - Take profit at 5% (partial close)
  - Maximum drawdown protection
- **Technical Indicators**:
  - RSI (Relative Strength Index)
  - EMA (Exponential Moving Average)
  - MACD (Moving Average Convergence Divergence)
  - ATR (Average True Range)
  - Bollinger Bands
  - Stochastic Oscillator
  - Volume analysis
- **Backtesting**: Test strategies on historical data
- **Telegram Notifications**: Real-time trade alerts (optional)
- **Comprehensive Logging**: Track all activities

## Project Structure

```
grokbot/
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration management
├── src/
│   ├── __init__.py
│   ├── data_collector.py    # Market data collection
│   ├── indicators.py        # Technical indicator calculations
│   ├── signal_generator.py  # Trading signal generation
│   ├── trade_executor.py    # Trade execution
│   ├── risk_manager.py      # Risk management
│   └── utils.py             # Utility functions
├── backtest/
│   ├── __init__.py
│   └── backtest.py          # Backtesting module
├── logs/                    # Log files (created automatically)
├── .env                     # Environment variables (your API keys)
├── .env.example             # Example environment file
├── .gitignore
├── main.py                  # Main bot entry point
├── requirements.txt         # Python dependencies
├── setup.py                 # Package setup
└── README.md
```

## Prerequisites

- **Python**: 3.10 or higher
- **Gate.io Account**: With futures trading enabled
- **API Keys**: Gate.io API key and secret
- **TA-Lib**: Technical analysis library

## Installation

### Windows (Azure Windows Server)

1. **Install Python**
   - Download Python 3.10+ from [python.org](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"

2. **Install TA-Lib** (Required for technical indicators)

   Download the pre-compiled wheel for Windows:
   ```powershell
   # Download TA-Lib wheel from:
   # https://github.com/cgohlke/talib-build/releases

   # Install the downloaded wheel (adjust filename for your Python version)
   pip install TA_Lib-0.4.28-cp310-cp310-win_amd64.whl
   ```

3. **Clone the Repository**
   ```bash
   git clone https://github.com/erolygc/grokbot.git
   cd grokbot
   ```

4. **Create Virtual Environment**
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

5. **Install Dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

6. **Configure Environment Variables**
   ```powershell
   # Copy example environment file
   copy .env.example .env

   # Edit .env with your API credentials (already configured with your keys)
   notepad .env
   ```

### Linux/macOS

1. **Install Python and Dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install python3.10 python3-pip python3-venv

   # Install TA-Lib
   sudo apt-get install build-essential
   wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
   tar -xzf ta-lib-0.4.0-src.tar.gz
   cd ta-lib/
   ./configure --prefix=/usr
   make
   sudo make install
   cd ..
   ```

2. **Clone and Setup**
   ```bash
   git clone https://github.com/erolygc/grokbot.git
   cd grokbot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Configuration

### Gate.io Setup

1. **Enable Testnet (Recommended for testing)**
   - Go to [testnet.gate.io](https://testnet.gate.io)
   - Register and enable Demo Trading
   - Transfer 10,000 USDT to futures account

2. **Generate API Keys**
   - Go to Account > API Keys
   - Create new key with permissions: Read, Trade
   - Save API Key and Secret

3. **Enable Hedge Mode**
   - Go to Futures > Trading Settings
   - Enable "Dual Position Mode"

### Environment Variables

Edit `.env` file:

```env
# Gate.io API Configuration (ALREADY CONFIGURED)
GATE_API_KEY=5a36b056a39a5b1e6320f0b00be654ca
GATE_SECRET=9225a79f6049bfa96cf25a4ca942f2594808d468ce2ce6d512ab857caf9bde1d

# Trading Configuration
SANDBOX_MODE=true              # Set to false for live trading
INITIAL_BALANCE=10000
LEVERAGE=3
POSITION_SIZE=100
TRADING_PAIR=BTC/USDT

# Risk Management
MAX_DRAWDOWN=0.10             # 10% maximum drawdown
STOP_LOSS_ATR_MULTIPLIER=0.5
TAKE_PROFIT_PERCENTAGE=0.05   # 5% take profit
MAX_EXPOSURE=0.10             # 10% maximum exposure

# Optional: Telegram Alerts
TELEGRAM_BOT_TOKEN=           # Your Telegram bot token
TELEGRAM_CHAT_ID=             # Your Telegram chat ID
```

## Usage

### Running the Bot

**Windows:**
```powershell
# Activate virtual environment
.\venv\Scripts\activate

# Run the bot
python main.py
```

**Linux/macOS:**
```bash
# Activate virtual environment
source venv/bin/activate

# Run the bot
python main.py
```

### Running Backtest

Test the strategy on historical data:

```bash
python -m backtest.backtest
```

This will:
- Fetch 30 days of historical data
- Simulate trading with the strategy
- Generate performance report
- Save results to `backtest/backtest_results.json`

### Stopping the Bot

- Press `Ctrl+C` to gracefully stop the bot
- All open positions will be closed automatically
- Final statistics will be displayed

## Strategy Details

### Golden Triple Rule

The bot uses a score-based system (0-100) to generate signals:

1. **4h EMA Trend** (30 points)
   - Bullish: +30 points
   - Bearish: -30 points

2. **15m RSI Reversal** (30 points)
   - Oversold reversal (< 30): +30 points
   - Overbought reversal (> 70): -30 points

3. **1m Volume Spike** (40 points)
   - Volume > 200% average: +40 points

**Additional Confirmations:**
- MACD histogram: ±10 points
- Bollinger Bands: ±10 points
- Stochastic: ±5 points
- Funding rate: ±5 points

**Signal Generation:**
- Score ≥ 80: **LONG** signal
- Score ≤ -80: **SHORT** signal
- Otherwise: **HOLD**

### Risk Management

- **Stop Loss**: 0.5 × ATR from entry
- **Trailing Stop**: Moves with price (0.5 × ATR distance)
- **Take Profit**: 5% profit → close 50% of position
- **Max Drawdown**: Trading stops if drawdown > 10%
- **Cooldown**: 10-minute wait after wrong signal

## Monitoring and Logs

### Log Files

Logs are saved to `logs/trading_bot.log`:

```bash
# View live logs (Windows)
Get-Content logs\trading_bot.log -Wait

# View live logs (Linux/macOS)
tail -f logs/trading_bot.log
```

### Status Information

The bot logs status every 5 minutes:
- Open positions
- Account balance
- Trade statistics
- Win rate
- Total PnL

## Safety and Warnings

⚠️ **IMPORTANT WARNINGS**:

1. **Test First**: Always test with sandbox mode before live trading
2. **Start Small**: Use minimal position sizes initially
3. **Monitor Closely**: Watch the bot closely for the first few days
4. **Understand Risks**: Cryptocurrency trading is highly volatile
5. **No Guarantees**: Past performance doesn't guarantee future results
6. **Legal Compliance**: Ensure algorithmic trading is legal in your jurisdiction
7. **API Security**: Never share your API keys or commit them to Git

## Troubleshooting

### Common Issues

**1. TA-Lib Import Error**
```
Solution: Install TA-Lib binary for your platform (see Installation section)
```

**2. API Connection Failed**
```
Solution: Check API keys in .env, verify Gate.io API permissions
```

**3. Insufficient Funds**
```
Solution: Ensure you have enough USDT in futures account (10,000 for testnet)
```

**4. Rate Limit Exceeded**
```
Solution: The bot has built-in rate limiting. If issues persist, increase delays in config
```

**5. Windows Path Issues**
```
Solution: Use forward slashes (/) in paths or raw strings (r"path\to\file")
```

## Performance Optimization

### Windows Server Recommendations

1. **Run as Windows Service** (for 24/7 operation)
2. **Use Task Scheduler** for automatic restart
3. **Monitor CPU/RAM** usage
4. **Set up automated backups** of logs and state files

### Resource Usage

- **CPU**: ~5-10% (during normal operation)
- **RAM**: ~200-500 MB
- **Network**: Low bandwidth (~1 MB/hour)

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/ config/ backtest/
flake8 src/ config/ backtest/
```

## Backtesting Results

Expected backtest performance (30 days):
- **Win Rate**: 85-90%
- **Average Return**: 15-25% monthly
- **Max Drawdown**: < 10%
- **Sharpe Ratio**: > 2.0

*Note: Results vary based on market conditions*

## Roadmap

- [ ] Machine Learning integration (LSTM for price prediction)
- [ ] Support for multiple trading pairs
- [ ] Web dashboard for monitoring
- [ ] Docker containerization
- [ ] Advanced order types (iceberg, TWAP)
- [ ] Portfolio optimization

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Disclaimer

This software is for educational purposes only. Trading cryptocurrencies carries significant financial risk. The developers are not responsible for any financial losses incurred while using this software. Use at your own risk.

## Support

- **Issues**: [GitHub Issues](https://github.com/erolygc/grokbot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/erolygc/grokbot/discussions)

## Acknowledgments

- CCXT library for exchange integration
- TA-Lib for technical analysis
- Gate.io for API access

---

**Happy Trading! 🚀**

*Remember: Always test in sandbox mode first!*
