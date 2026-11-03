import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN_BURAYA")
CHAT_ID = os.environ.get("CHAT_ID", "TELEGRAM_CHAT_ID_BURAYA")

HISSELER = [
    "ENJSA.IS", "GARAN.IS", "EREGL.IS", "KCHOL.IS", "TOASO.IS",
    "VAKBN.IS", "TCELL.IS", "PGSUS.IS", "GUBRF.IS", "ISCTR.IS",
    "FROTO.IS", "ALBRK.IS", "TAVHL.IS", "DIRIT.IS", "BIMAS.IS"
]

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram mesajı gönderilemedi: {e}")

def wilder_atr(df, period):
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr = np.maximum(high - low, np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))))
    return tr.ewm(alpha=1/period, adjust=False).mean()

def calculate_mfi(df, period=14):
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    rmf = tp * df['Volume']
    pos_mf = np.where(tp > tp.shift(1), rmf, 0.0)
    neg_mf = np.where(tp < tp.shift(1), rmf, 0.0)
    
    pos_sum = pd.Series(pos_mf).rolling(window=period).sum()
    neg_sum = pd.Series(neg_mf).rolling(window=period).sum()
    
    mfi = 100.0 - (100.0 / (1.0 + (pos_sum / (neg_sum + 1e-10))))
    return mfi

def hesapla_indikatorler(df):
    ap = 14
    coeff = 1.0
    
    # 1. AlphaTrend Hesaplama (TradingView MFI ve Wilder ATR uyumlu)
    df['ATR'] = wilder_atr(df, ap)
    df['UpT'] = df['Low'] - (df['ATR'] * coeff)
    df['DnT'] = df['High'] + (df['ATR'] * coeff)
    
    df['MFI'] = calculate_mfi(df, ap)
    df['MFI_Cond'] = df['MFI'] >= 50.0
    
    at = []
    current_at = df['Low'].iloc[0]
    for i in range(len(df)):
        if i < ap or pd.isna(df['MFI_Cond'].iloc[i]):
            at.append(current_at)
            continue
        upt_val = df['UpT'].iloc[i]
        dnt_val = df['DnT'].iloc[i]
        prev_at = at[-1]
        
        if df['MFI_Cond'].iloc[i]:
            val = max(upt_val, prev_at)
        else:
            val = min(dnt_val, prev_at)
        at.append(val)
    df['AT'] = at

    # 2. SuperTrend Hesaplama (Factor=3.0, PD=7, Wilder ATR uyumlu)
    factor = 3.0
    pd_val = 7
    hl2 = (df['High'] + df['Low']) / 2
    df['ATR_ST'] = wilder_atr(df, pd_val)
    df['ST_Up'] = hl2 - (factor * df['ATR_ST'])
    df['ST_Dn'] = hl2 + (factor * df['ATR_ST'])
    
    trend = 1
    tsl_list = []
    tr_up = df['ST_Up'].iloc[0]
    tr_dn = df['ST_Dn'].iloc[0]
    
    for i in range(len(df)):
        if i == 0:
            tsl_list.append(tr_up)
            continue
        c = df['Close'].iloc[i]
        c_prev = df['Close'].iloc[i-1]
        
        tr_up = max(df['ST_Up'].iloc[i], tr_up) if c_prev > tr_up else df['ST_Up'].iloc[i]
        tr_dn = min(df['ST_Dn'].iloc[i], tr_dn) if c_prev < tr_dn else df['ST_Dn'].iloc[i]
        
        if c > tr_dn:
            trend = 1
        elif c < tr_up:
            trend = -1
            
        tsl_list.append(tr_up if trend == 1 else tr_dn)
    
    df['TSL'] = tsl_list
    df['Trend'] = np.where(df['AT'] > df['TSL'], 'AL', 'SAT')
    return df

def tarama_yap():
    zaman_dilimleri = {"Saatlik": "60m", "Günlük": "1d", "Haftalık": "1wk"}
    
    for hisse in HISSELER:
        for period_adi, interval in zaman_dilimleri.items():
            try:
                data = yf.download(hisse, period="3mo", interval=interval, progress=False)
                if data.empty:
                    continue
                
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.droplevel(1)
                
                df = hesapla_indikatorler(data)
                son_durum = df['Trend'].iloc[-1]
                onceki_durum = df['Trend'].iloc[-2]
                
                if son_durum != onceki_durum:
                    tv_hisse = hisse.replace(".IS", "")
                    tv_link = f"https://s.tradingview.com/widgetembed/?symbol=BIST:{tv_hisse}&interval=60&theme=dark"
                    
                    msg = f"🚨 *BIST SİNYAL DEĞİŞİKLİĞİ*\n\n📌 Hisse: [{hisse}]({tv_link})\n⏳ Zaman Dilimi: `{period_adi}`\n🔄 Yeni Durum: **{son_durum}**"
                    print(f"Sinyal değişti: {hisse} ({period_adi}) -> {son_durum}")
                    send_telegram_message(msg)
            except Exception as e:
                print(f"{hisse} taranırken hata ({period_adi}): {e}")

if __name__ == "__main__":
    tarama_yap()
