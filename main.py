import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
from datetime import datetime

# --- CONFIGURACIÓN TITAN V9.2 ---
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
FILE_DB = "titan_portfolio.json"
CAP_MENSUAL = 500 

TICKERS_MACRO = ['^VIX', 'HYG', 'EURUSD=X', 'SPY'] 
TICKERS_SEGURIDAD = ['IWQU.L']
POOL_TECH = ['NVDA', 'MSFT', 'AAPL', 'GOOGL', 'AMZN', 'AVGO', 'TSM', 'META']
POOL_EXPLOSION = ['COIN', 'MSTR', 'TSLA', 'BITO', 'PLTR']

def cargar_memoria():
    if not os.path.exists(FILE_DB):
        return {
            "fecha_inicio": str(datetime.now()),
            "total_ingresado": 0.0,
            "cash": 0.0,
            "posiciones": {}
        }
    with open(FILE_DB, 'r') as f: return json.load(f)

def enviar_telegram(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def obtener_momentum_calidad(data, tickers):
    scores = {}
    for t in tickers:
        try:
            returns = data[t].pct_change().dropna()
            total_ret = (data[t].iloc[-1] / data[t].iloc[-60]) - 1
            vol = returns.std() * np.sqrt(252)
            scores[t] = total_ret / vol if vol > 0 else -999
        except: scores[t] = -999
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def ejecutar_titan_v9():
    mem = cargar_memoria()
    todos = TICKERS_MACRO + TICKERS_SEGURIDAD + POOL_TECH + POOL_EXPLOSION
    data = yf.download(todos, period="8mo", progress=False, auto_adjust=True)
    if isinstance(data.columns, pd.MultiIndex): data = data['Close']

    # 1. ANÁLISIS DEL CLIMA (MACRO)
    vix = data['^VIX'].iloc[-1]
    hyg_sano = data['HYG'].iloc[-1] > data['HYG'].rolling(20).mean().iloc[-1] * 0.99
    mercado_sano = vix < 31 and hyg_sano

    # 2. SELECCIÓN DE LÍDERES
    lider_tech = obtener_momentum_calidad(data, POOL_TECH)[0][0]
    lider_exp = obtener_momentum_calidad(data, POOL_EXPLOSION)[0][0]

    # 3. ACTUALIZACIÓN CONTABLE (A partir de Abril)
    ahora = datetime.now()
    es_dia_pago = ahora.day == 1 and ahora.month >= 4 # Inicia en Abril
    
    if es_dia_pago:
        mem["cash"] += CAP_MENSUAL
        mem["total_ingresado"] += CAP_MENSUAL
    
    # 4. VALORACIÓN DE CARTERA
    valor_acciones = 0.0
    for t, info in mem["posiciones"].items():
        if t in data.columns:
            valor_acciones += info["unidades"] * data[t].iloc[-1]

    patrimonio_neto = mem["cash"] + valor_acciones
    beneficio_total = patrimonio_neto - mem["total_ingresado"]
    rentabilidad_pct = (beneficio_total / mem["total_ingresado"] * 100) if mem["total_ingresado"] > 0 else 0

    # --- DISEÑO DE INFORME "FAMILY OFFICE" ---
    msg = f"🏛️ **TITAN WEALTH MANAGEMENT**\n"
    msg += f"📅 {ahora.strftime('%d %b, %Y')} | *ESTADO DE CUENTA*\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"

    # BLOQUE 1: PATRIMONIO
    msg += f"💰 **PATRIMONIO NETO:** `{patrimonio_neto:.2f}€`\n"
    msg += f"📈 **Rendimiento:** `{beneficio_total:+.2f}€` ({rentabilidad_pct:+.1f}%)\n"
    msg += f"🏦 **Efectivo (4%):** `{mem['cash']:.2f}€`\n\n"

    # BLOQUE 2: PULSO DEL MERCADO
    msg += "🚦 **SEÑAL DEL MERCADO:** " + ("`NORMAL` 🟢" if mercado_sano else "`DEFENSIVA` 🔴") + "\n"
    msg += f"• *Miedo (VIX):* {vix:.1f} | *Bonos:* {'Saludables' if hyg_sano else 'Riesgo'}\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"

    # BLOQUE 3: ACCIONES REQUERIDAS (Trade Republic)
    if es_dia_pago:
        msg += "⚡ **MISIÓN DE INVERSIÓN (Día 1)**\n"
        msg += "Entra en Trade Republic y ejecuta:\n"
        if mercado_sano:
            msg += f"1️⃣ Comprar **250€** de `IWQU.L` (Calidad)\n"
            msg += f"2️⃣ Comprar **150€** de `{lider_tech}` (Tech)\n"
            msg += f"3️⃣ Comprar **100€** de `{lider_exp}` (Explosión)\n"
            msg += "\n*Nota: Tu bot ya ha registrado estas compras.*"
        else:
            msg += "🛡️ **NO COMPRAR.** Deja los 500€ en efectivo. El mercado está cayendo y es mejor esperar cobrando el 4%."
    else:
        msg += "👮 **ESTADO DE TUS INVERSIONES**\n"
        if not mem["posiciones"]:
            msg += "No hay acciones compradas aún. Esperando al día 1 de Abril.\n"
        else:
            msg += "Tus posiciones están bajo vigilancia. No hace falta que operes hoy. Deja que el interés compuesto trabaje.\n"

    msg += "\n━━━━━━━━━━━━━━━━━━\n"
    msg += f"🧠 **¿POR QUÉ {lider_tech}?**\n"
    msg += f"Es el líder del Nasdaq con el mejor equilibrio entre subida y estabilidad. Supera al 99% del mercado hoy."

    enviar_telegram(msg)
    with open(FILE_DB, 'w') as f: json.dump(mem, f, indent=4)

if __name__ == "__main__":
    ejecutar_titan_v9()
