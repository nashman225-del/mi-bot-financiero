import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime

# GEN 3.0 Cloud - Lectura de secretos seguros
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})

def ejecutar_bot():
    # 1. Definir los activos (Tu estrategia 500€)
    activos = ['IWQU.L', 'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'AVGO', 'COST', 'BITO', 'COIN', 'IWM', 'TSLA', '^VIX']
    
    # 2. Descargar datos reales de hoy
    data = yf.download(activos, period="1y", progress=False)['Close']
    vix = data['^VIX'].iloc[-1]
    precios = data.iloc[-1]
    
    # 3. Reporte
    reporte = f"☁️ **GEN 3.0 SENTINEL CLOUD**\n"
    reporte += f"📅 Fecha: {datetime.now().strftime('%d/%m/%Y')}\n"
    reporte += f"📉 **VIX:** {vix:.2f}\n\n"
    
    if vix > 30:
        reporte += "🚨 **BLOQUEO POR PÁNICO.** No invertir hoy."
    else:
        reporte += "🛒 **ÓRDENES DE HOY (500€):**\n"
        reporte += f"🛡️ **Seguridad (250€):** Comprar IWQU.L\n"
        # Lógica de fuerza relativa simplificada para la nube
        top_expert = data[['NVDA', 'MSFT', 'AAPL']].iloc[-1].idxmax()
        reporte += f"🏢 **Riesgo (150€):** Comprar {top_expert}\n"
        reporte += f"⚡ **Explosión (100€):** Comprar COIN (Momentum)\n"
    
    enviar_telegram(reporte)

if __name__ == "__main__":
    ejecutar_bot()
