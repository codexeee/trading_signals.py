{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 4,
   "id": "101ad5f9",
   "metadata": {},
   "outputs": [
    {
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "2025-03-03 12:46:31.327 No runtime found, using MemoryCacheStorageManager\n"
     ]
    }
   ],
   "source": [
    "import pandas as pd\n",
    "import numpy as np\n",
    "import requests\n",
    "import streamlit as st\n",
    "from datetime import datetime\n",
    "\n",
    "# Cache data fetching to avoid redundant API calls\n",
    "@st.cache_data(ttl=60)  # Cache data for 60 seconds\n",
    "def fetch_data(symbol, interval, limit=100):\n",
    "    url = 'https://api.binance.com/api/v3/klines'\n",
    "    params = {\n",
    "        'symbol': symbol,\n",
    "        'interval': interval,\n",
    "        'limit': limit\n",
    "    }\n",
    "    try:\n",
    "        response = requests.get(url, params=params)\n",
    "        response.raise_for_status()\n",
    "        data = response.json()\n",
    "\n",
    "        if not isinstance(data, list) or len(data) == 0 or not isinstance(data[0], list):\n",
    "            return pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])\n",
    "\n",
    "        o, h, l, c, v = zip(*[(float(d[1]), float(d[2]), float(d[3]), float(d[4]), float(d[5])) for d in data])\n",
    "        datetime = pd.to_datetime([d[0] for d in data], unit='ms')\n",
    "\n",
    "        return pd.DataFrame({\n",
    "            'datetime': datetime,\n",
    "            'open': o,\n",
    "            'high': h,\n",
    "            'low': l,\n",
    "            'close': c,\n",
    "            'volume': v\n",
    "        })\n",
    "    except Exception as e:\n",
    "        st.error(f\"Error fetching data for {symbol} ({interval}): {e}\")\n",
    "        return pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])\n",
    "\n",
    "# Update signals based on new data\n",
    "def update_signals(df, a=1, c=10):\n",
    "    if df.empty:\n",
    "        return None, None, None\n",
    "\n",
    "    df['high-low'] = df['high'] - df['low']\n",
    "    df['high-close_prev'] = np.abs(df['high'] - df['close'].shift(1))\n",
    "    df['low-close_prev'] = np.abs(df['low'] - df['close'].shift(1))\n",
    "    df['tr'] = df[['high-low', 'high-close_prev', 'low-close_prev']].max(axis=1)\n",
    "    df['atr'] = df['tr'].rolling(window=c, min_periods=1).mean()\n",
    "\n",
    "    df['nLoss'] = a * df['atr']\n",
    "    df['xATRTrailingStop'] = np.nan\n",
    "\n",
    "    for i in range(1, len(df)):\n",
    "        if df['close'].iloc[i] > df['xATRTrailingStop'].iloc[i-1] and df['close'].iloc[i-1] > df['xATRTrailingStop'].iloc[i-1]:\n",
    "            df.loc[i, 'xATRTrailingStop'] = max(df['xATRTrailingStop'].iloc[i-1], df['close'].iloc[i] - df['nLoss'].iloc[i])\n",
    "        elif df['close'].iloc[i] < df['xATRTrailingStop'].iloc[i-1] and df['close'].iloc[i-1] < df['xATRTrailingStop'].iloc[i-1]:\n",
    "            df.loc[i, 'xATRTrailingStop'] = min(df['xATRTrailingStop'].iloc[i-1], df['close'].iloc[i] + df['nLoss'].iloc[i])\n",
    "        elif df['close'].iloc[i] > df['xATRTrailingStop'].iloc[i-1]:\n",
    "            df.loc[i, 'xATRTrailingStop'] = df['close'].iloc[i] - df['nLoss'].iloc[i]\n",
    "        else:\n",
    "            df.loc[i, 'xATRTrailingStop'] = df['close'].iloc[i] + df['nLoss'].iloc[i]\n",
    "\n",
    "    df['ema'] = df['close'].ewm(span=1, adjust=False).mean()\n",
    "    df['buy'] = (df['close'] > df['xATRTrailingStop']) & (df['ema'] > df['xATRTrailingStop'])\n",
    "    df['sell'] = (df['close'] < df['xATRTrailingStop']) & (df['ema'] < df['xATRTrailingStop'])\n",
    "\n",
    "    df['signal'] = np.nan\n",
    "    df.loc[df['buy'], 'signal'] = 'Buy'\n",
    "    df.loc[df['sell'], 'signal'] = 'Sell'\n",
    "\n",
    "    latest_signal = df.iloc[-1]\n",
    "    if latest_signal['buy']:\n",
    "        return 'Buy', latest_signal['close'], latest_signal['datetime']\n",
    "    elif latest_signal['sell']:\n",
    "        return 'Sell', latest_signal['close'], latest_signal['datetime']\n",
    "    else:\n",
    "        return 'Hold', None, latest_signal['datetime']\n",
    "\n",
    "# Parameters\n",
    "coins = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'ADAUSDT', 'BNBUSDT', 'SOLUSDT', 'DOTUSDT', 'DOGEUSDT', 'MATICUSDT', 'SHIBUSDT']\n",
    "timeframes = ['1m', '15m', '1h', '1d']\n",
    "\n",
    "# Streamlit UI\n",
    "st.title(\"User-Selected Multi-Coin Trading Signals\")\n",
    "selected_coins = st.multiselect(\"Select coins to analyze\", options=coins, default=['BTCUSDT', 'ETHUSDT'])\n",
    "st.write(\"Trading signals for selected coins and all timeframes:\")\n",
    "\n",
    "# Display data for each selected coin and timeframe\n",
    "for coin in selected_coins:\n",
    "    st.subheader(f\"Signals for {coin}\")\n",
    "    for tf in timeframes:\n",
    "        df = fetch_data(coin, tf)\n",
    "        signal, price, timestamp = update_signals(df)\n",
    "\n",
    "        if signal and price:\n",
    "            st.write(f\"Timeframe: {tf} | Signal: {signal} | Price: {price} | Time: {timestamp}\")\n",
    "        else:\n",
    "            st.write(f\"Timeframe: {tf} | No signal.\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "id": "25bc3926",
   "metadata": {},
   "outputs": [],
   "source": [
    "\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "id": "fe643ea9",
   "metadata": {},
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3 (ipykernel)",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.11.4"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
