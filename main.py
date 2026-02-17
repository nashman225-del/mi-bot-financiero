import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
from datetime import datetime

# --- CONFIGURACIÓN TITAN V10 ---
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
FILE_DB = "titan_portfolio.json"
CAP_MENSUAL = 500 

# Activos de Vigilancia
TICKERS_MACRO = ['^VIX', 'HYG', 'EURUSD=X', 'SPY'] 
TICKERS_SEGURIDAD = ['IWQU.L']
POOL_TECH = ['NVDA', 'MSFT', 'AAPL', 'GOOGL', 'AMZN', 'AVGO', 'TSM', 'META']
POOL_EXPLOSION = ['COIN', 'MSTR', 'TSLA', 'BITO', 'PLTR']

def cargar_memoria():
    default_mem = {"fecha_inicio": str(datetime.now()), "total_ingresado": 0.0, "cash": 0.0, "posiciones": {}}
    if not os.path.exists(FILE_DB): return default_mem
    with open(FILE_DB, 'r') as f:
        try:
            mem = json.load(f)
            for key, value in default_mem.items():
                if key not in mem: mem[key] = value
            return mem
        except: return default_mem

def enviar_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def obtener_analisis_momentum(data, tickers):
    scores = {}
    for t in tickers:
        try:
            returns = data[t].pct_change().dropna()
            total_ret = (data[t].iloc[-1] / data[t].iloc[-60]) - 1
            vol = returns.std() * np.sqrt(252)
            scores[t] = {"score": total_ret / vol if vol > 0 else -999, "ret": total_ret * 100}
        except: scores[t] = {"score": -999, "ret": 0}
    return sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)

def ejecutar_titan_v10():
    mem = cargar_memoria()
    todos = TICKERS_MACRO + TICKERS_SEGURIDAD + POOL_TECH + POOL_EXPLOSION
    
    # 1. DESCARGA DE DATOS
    try:
        data = yf.download(todos, period="8mo", progress=False, auto_adjust=True)
        if isinstance(data.columns, pd.MultiIndex): data = data['Close']
    except: return

    # 2. ANÁLISIS MACRO DETALLADO
    vix = data['^VIX'].iloc[-1]
    hyg_hoy = data['HYG'].iloc[-1]
    hyg_media = data['HYG'].rolling(20).mean().iloc[-1]
    
    # Lógica de Salud
    vix_sano = vix < 31
    bonos_sanos = hyg_hoy > hyg_media * 0.99
    mercado_sano = vix_sano and bonos_sanos

    # 3. IDENTIFICAR LÍDERES ACTUALES
    lider_tech_ticker, lider_tech_info = obtener_analisis_momentum(data, POOL_TECH)[0]
    lider_exp_ticker, lider_exp_info = obtener_analisis_momentum(data, POOL_EXPLOSION)[0]

    # 4. CONTABILIDAD
    ahora = datetime.now()
    es_dia_pago = ahora.day == 1
    if es_dia_pago:
        mem["cash"] += CAP_MENSUAL
        mem["total_ingresado"] += CAP_MENSUAL
    
    # 5. VALORACIÓN Y AUDITORÍA DE POSICIONES
    valor_acciones = 0.0
    analisis_cartera = ""
    necesita_correccion = False

    for t, info in mem["posiciones"].items():
        if t in data.columns:
            precio_actual = data[t].iloc[-1]
            unidades = info["unidades"]
            valor_actual = unidades * precio_actual
            valor_acciones += valor_actual
            
            # Salud técnica: ¿Está por encima de su media de 20 días?
            sma20 = data[t].rolling(20).mean().iloc[-1]
            if precio_actual > sma20:
                analisis_cartera += f"✅ **{t}**: MANTENER (Sigue subiendo con fuerza)\n"
            else:
                analisis_cartera += f"⚠️ **{t}**: CORREGIR (Está empezando a caer)\n"
                necesita_correccion = True

    patrimonio_neto = mem["cash"] + valor_acciones
    beneficio = patrimonio_neto - mem["total_ingresado"]
    rentabilidad = (beneficio / mem["total_ingresado"] * 100) if mem["total_ingresado"] > 0 else 0

    # --- DISEÑO DEL INFORME EXPLICATIVO ---
    msg = f"🏛️ **TITAN ORACLE: AUDITORÍA DE PATRIMONIO**\n"
    msg += f"📅 {ahora.strftime('%d %b, %Y')} | *Gestión Activa*\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"

    # BLOQUE 1: RESUMEN FINANCIERO
    msg += f"💰 **DINERO TOTAL:** `{patrimonio_neto:.2f}€`\n"
    msg += f"📈 **Ganancia Real:** `{beneficio:+.2f}€` ({rentabilidad:+.1f}%)\n"
    msg += f"🏦 **Efectivo en TR (4%):** `{mem['cash']:.2f}€`\n\n"

    # BLOQUE 2: ANÁLISIS DEL MERCADO (¿Por qué pasa lo que pasa?)
    msg += "🌡️ **ESTADO DEL MUNDO:**\n"
    if mercado_sano:
        msg += "🟢 **SITUACIÓN ESTABLE.** "
        msg += "Los bancos están prestando dinero con normalidad y los inversores no tienen miedo. Es un buen momento para que tus inversiones crezcan.\n"
    else:
        msg += "🔴 **SITUACIÓN DE RIESGO.** "
        if not vix_sano: msg += "Hay mucho pánico en las noticias. "
        if not bonos_sanos: msg += "Los grandes fondos están retirando su dinero por miedo a quiebras. "
        msg += "Es mejor ser prudentes y proteger lo que tenemos.\n"
    
    msg += "━━━━━━━━━━━━━━━━━━\n\n"

    # BLOQUE 3: INSTRUCCIONES DE ACCIÓN
    if es_dia_pago:
        msg += "🎯 **MISIÓN: INVERTIR 500€ NUEVOS**\n"
        if mercado_sano:
            msg += f"1. Comprar **250€** de `IWQU.L` (Tu base segura)\n"
            msg += f"2. Comprar **150€** de `{lider_tech_ticker}` (La tecnológica líder)\n"
            msg += f"3. Comprar **100€** de `{lider_exp_ticker}` (Tu acelerador de ganancias)\n"
            msg += "\n*¿Por qué estos?* Porque son los que tienen el crecimiento más sólido este mes."
        else:
            msg += "🛡️ **ORDEN: NO COMPRES NADA.**\n"
            msg += "Guarda los 500€ en tu cuenta de efectivo. El mercado está cayendo y compraremos más barato cuando la tormenta pase."
    else:
        msg += "👮 **AUDITORÍA DE TUS ACCIONES:**\n"
        if not mem["posiciones"]:
            msg += "Aún no tienes acciones. Tu primera compra será el día 1 de mes.\n"
        else:
            msg += analisis_cartera
            if necesita_correccion:
                msg += f"\n👉 **ACCIÓN:** Considera vender las que tienen ⚠️ y mover ese dinero a `{lider_tech_ticker}`, que es el nuevo líder con más fuerza."
            else:
                msg += "\n👉 **ACCIÓN:** No hagas nada. Tus inversiones están perfectas y trabajando para ti."

    msg += "\n\n━━━━━━━━━━━━━━━━━━\n"
    msg += f"🧠 **JUSTIFICACIÓN TÉCNICA:**\n"
    msg += f"Hoy priorizamos `{lider_tech_ticker}` porque su crecimiento es un {lider_tech_info['ret']:.1f}% superior a la media, con un riesgo de caída muy bajo comparado con sus rivales."

    enviar_telegram(msg)
    with open(FILE_DB, 'w') as f: json.dump(mem, f, indent=4)

if __name__ == "__main__":
    ejecutar_titan_v10()
