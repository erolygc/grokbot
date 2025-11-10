"""
Setup script for Crypto Trading Bot
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

setup(
    name="grokbot",
    version="1.0.0",
    description="Advanced crypto trading bot with multi-timeframe analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/grokbot",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "ccxt>=4.0.0",
        "python-dotenv>=1.0.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "requests>=2.31.0",
        "ta-lib>=0.4.28",
        "asyncio>=3.4.3",
        "aiohttp>=3.9.0",
    ],
    extras_require={
        "redis": ["redis>=5.0.0"],
        "viz": ["matplotlib>=3.7.0", "plotly>=5.17.0"],
        "dev": ["pytest>=7.4.0", "pytest-asyncio>=0.21.0", "black>=23.0.0", "flake8>=6.1.0"],
    },
    entry_points={
        "console_scripts": [
            "grokbot=main:main",
            "grokbot-backtest=backtest.backtest:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="crypto trading bot bitcoin futures gate.io algorithmic-trading",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/grokbot/issues",
        "Source": "https://github.com/yourusername/grokbot",
    },
)
