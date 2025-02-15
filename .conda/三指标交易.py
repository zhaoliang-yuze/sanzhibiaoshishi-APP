import ccxt
import pandas as pd
import ta
import time
import logging
import streamlit as st

# 设置日志
logging.basicConfig(filename='trade_log.txt', level=logging.INFO)

# 配置OKEX API
exchange = ccxt.okx({
    'apiKey': '0bbb6965-1fe9-46ca-882e-f56093c86cb1',
    'secret': 'E66B6E1D913EFC520445043AB0969352',
    'password': 'Zhaoliang123456+',
})
# 获取15分钟K线数据并计算Stochastic RSI, MACD 和 SKDJ
def get_indicators():
    candles = exchange.fetch_ohlcv('ETH/USDT', '15m')  # 获取15分钟K线数据
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])

    # 计算RSI和Stochastic RSI
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['stochastic'] = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'], window=14).stoch()

    # 平滑K和D
    df['K'] = df['stochastic'].rolling(window=3).mean()
    df['D'] = df['K'].rolling(window=3).mean()

    # 计算MACD
    df['macd'] = ta.trend.MACD(df['close']).macd()
    df['macd_signal'] = ta.trend.MACD(df['close']).macd_signal()

    # 计算SKDJ (使用 stoch_k 和 stoch_d)
    df['skdj_k'] = df['K'].rolling(window=3).mean()  # 对K进行平滑
    df['skdj_d'] = df['D'].rolling(window=3).mean()  # 对D进行平滑


    return df

# 判断买入/卖出信号（结合Stochastic RSI, MACD 和 SKDJ）
def get_signal(df, use_macd=False, use_skdj=False):
    last_stochastic = df['stochastic'].iloc[-1]
    last_k = df['K'].iloc[-1]
    last_d = df['D'].iloc[-1]

    # 判断Stochastic RSI信号
    if last_k > last_d and last_stochastic < 20:
        signal = "buy"
    elif last_k < last_d and last_stochastic > 80:
        signal = "sell"
    else:
        signal = None

    # 如果启用了MACD
    if use_macd:
        last_macd = df['macd'].iloc[-1]
        last_macd_signal = df['macd_signal'].iloc[-1]
        if last_macd > last_macd_signal:
            signal = "buy" if signal != "sell" else signal
        elif last_macd < last_macd_signal:
            signal = "sell" if signal != "buy" else signal

    # 如果启用了SKDJ
    if use_skdj:
        last_skdj_k = df['skdj_k'].iloc[-1]
        last_skdj_d = df['skdj_d'].iloc[-1]
        if last_skdj_k > last_skdj_d:
            signal = "buy" if signal != "sell" else signal
        elif last_skdj_k < last_skdj_d:
            signal = "sell" if signal != "buy" else signal

    return signal

# 下单操作：挂限价单
def place_order(signal, amount=1):
    price = get_latest_price()  # 获取当前市场价格
    if signal == "buy":
        buy_price = price * 1.001  # 买三挂单：当前价格 + 0.1%
        order = exchange.create_limit_buy_order('ETH/USDT', amount, buy_price)
        logging.info(f"买入订单: {order} | 当前价格: {buy_price}")
    elif signal == "sell":
        sell_price = price * 0.999  # 卖三挂单：当前价格 - 0.1%
        order = exchange.create_limit_sell_order('ETH/USDT', amount, sell_price)
        logging.info(f"卖出订单: {order} | 当前价格: {sell_price}")
    return order

# 获取当前ETH/USDT的最新价格
def get_latest_price():
    ticker = exchange.fetch_ticker('ETH/USDT')
    return ticker['last']

# 订单未成交时撤单
def cancel_order_if_not_filled(order, timeout=300):
    start_time = time.time()
    while True:
        order_status = exchange.fetch_order(order['id'], 'ETH/USDT')
        if order_status['status'] == 'closed':
            logging.info(f"订单已成交: {order_status}")
            break
        if time.time() - start_time > timeout:  # 超过5分钟未成交
            exchange.cancel_order(order['id'], 'ETH/USDT')
            logging.info(f"订单未成交，已撤单: {order['id']}")
            break
        time.sleep(10)

# 显示账户信息
def display_account_info():
    account_info = exchange.fetch_balance()
    st.write("账户余额:", account_info)

# 自动交易的主逻辑
def auto_trade(use_macd=False, use_skdj=False):
    df = get_indicators()  # 获取指标数据
    signal = get_signal(df, use_macd, use_skdj)  # 获取买入/卖出信号

    if signal:
        order = place_order(signal)  # 下单
        cancel_order_if_not_filled(order)  # 如果未成交，撤单

# 配置面板：用户可以调整参数
def config_panel():
    st.title("自动交易配置面板")
    st.sidebar.header("配置参数")
    
    # 配置 Stochastic RSI 参数
    smooth_k = st.sidebar.slider('K平滑', 1, 10, 3)
    smooth_d = st.sidebar.slider('D平滑', 1, 10, 3)
    rsi_length = st.sidebar.slider('RSI长度', 1, 30, 14)
    stochastic_length = st.sidebar.slider('Stochastic长度', 1, 30, 14)
    
    # 配置是否使用 MACD 和 SKDJ
    use_macd = st.sidebar.checkbox('启用 MACD')
    use_skdj = st.sidebar.checkbox('启用 SKDJ')

    st.sidebar.write(f"当前K平滑：{smooth_k}")
    st.sidebar.write(f"当前D平滑：{smooth_d}")
    st.sidebar.write(f"当前RSI长度：{rsi_length}")
    st.sidebar.write(f"当前Stochastic长度：{stochastic_length}")
    
    # 实时显示账户信息
    display_account_info()

    # 执行自动交易
    auto_trade(use_macd, use_skdj)

# 运行自动交易
if __name__ == '__main__':
    config_panel()  # 显示配置面板