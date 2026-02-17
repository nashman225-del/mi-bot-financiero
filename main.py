import yfinance as yf
import pandas as pd
import requests
import os
import json
from datetime import datetime

# --- TITAN V8: PERSISTENT MEMORY CORE ---
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
FILE_DB = "titan_portfolio.json"

# CONFIGURACIÓN
CAP_MENSUAL = 500 

# UNIVERSO DE ACTIVOS
TICKERS_REF = ['^VIX', 'HYG', 'SPY'] 
TICKERS_SEGURIDAD = ['IWQU.L']
TICKERS_RIESGO_POOL = ['NVDA', 'MSFT', 'AAPL', 'GOOGL', 'META', 'AMZN', 'AVGO', 'TSM']
TICKERS_EXPLOSION_POOL = ['COIN', 'MSTR', 'MARA', 'TSLA', 'PLTR', 'BITO']

# --- MÓDULO DE PERSISTENCIA (JSON) ---
def cargar_cartera():
    if not os.path.exists(FILE_DB):
        # Crear estructura inicial si no existe
        return {
            "fecha_inicio": datetime.now().strftime("%Y-%m-%d"),
            "cash_disponible": 0.0,
            "valor_invertido": 0.0,
            "posiciones": {} # Ej: "NVDA": {"unidades": 2.5, "precio_medio": 120}
        }
    try:
        with open(FILE_DB, 'r') as f:
            return json.load(f)
    except:
        return {"cash_disponible": 0.0, "posiciones": {}}

def guardar_cartera(data):
    with open(FILE_DB, 'w') as f:
        json.dump(data, f, indent=4)

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Error Telegram: {e}")

def obtener_lider_momentum(data, tickers, ventana=60):
    best_ticker = tickers[0]
    best_perf = -999
    
    valid_tickers = [t for t in tickers if t in data.columns]
    
    for t in valid_tickers:
        try:
            if len(data[t].dropna()) < ventana: continue
            hoy = data[t].iloc[-1]
            base = data[t].iloc[-ventana]
            if base == 0: continue
            perf = (hoy / base) - 1
            if perf > best_perf:
                best_perf = perf
                best_ticker = t
        except: continue
        
    return best_ticker, best_perf * 100

def ejecutar_titan_v8():
    print("🧠 TITAN V8: Iniciando Sistemas con Memoria Persistente...")
    
    # 1. CARGAR MEMORIA
    cartera = cargar_cartera()
    
    # 2. DATOS MERCADO
    todos = TICKERS_REF + TICKERS_SEGURIDAD + TICKERS_RIESGO_POOL + TICKERS_EXPLOSION_POOL
    try:
        data = yf.download(todos, period="6mo", progress=False, auto_adjust=True)
        if 'Close' in data.columns and isinstance(data.columns, pd.MultiIndex):
            data = data['Close']
    except Exception as e:
        enviar_telegram(f"⚠️ Error Datos V8: {e}")
        return

    # 3. ANÁLISIS MACRO
    try:
        vix = data['^VIX'].iloc[-1] if '^VIX' in data.columns else 20.0
        hyg_hoy = data['HYG'].iloc[-1] if 'HYG' in data.columns else 100
        hyg_media = data['HYG'].rolling(20).mean().iloc[-1] if 'HYG' in data.columns else 90
        mercado_sano = (vix < 32) and (hyg_hoy > hyg_media * 0.98)
    except:
        mercado_sano = True
        vix = 0.0

    # 4. LÓGICA TEMPORAL Y CONTABLE
    dia_actual = datetime.now().day
    es_dia_inversion = (dia_actual == 1)
    
    # Si es día 1, inyectamos capital en la memoria del bot
    msg_capital = ""
    if es_dia_inversion:
        cartera["cash_disponible"] += CAP_MENSUAL
        msg_capital = f"💰 **Inyección Detectada:** +{CAP_MENSUAL}€ añadidos al Cash.\n"
        guardar_cartera(cartera) # Guardamos el ingreso

    # 5. SELECCIÓN DE ACTIVOS
    lider_riesgo, perf_riesgo = obtener_lider_momentum(data, TICKERS_RIESGO_POOL)
    lider_exp, perf_exp = obtener_lider_momentum(data, TICKERS_EXPLOSION_POOL)

    # 6. VALORACIÓN ACTUAL DE LA CARTERA (Lectura de posiciones)
    valor_total_posiciones = 0.0
    detalle_posiciones = ""
    
    if cartera["posiciones"]:
        detalle_posiciones = "\n📊 **CARTERA ACTUAL (VIGILANCIA):**\n"
        for ticker, info in cartera["posiciones"].items():
            if ticker in data.columns:
                precio_actual = data[ticker].iloc[-1]
                valor_pos = info["unidades"] * precio_actual
                valor_total_posiciones += valor_pos
                
                # Check Stop Loss (Media 20)
                sma20 = data[ticker].rolling(20).mean().iloc[-1]
                estado = "✅" if precio_actual > sma20 else "⚠️"
                
                cambio_pct = ((precio_actual - info["precio_medio"]) / info["precio_medio"]) * 100
                detalle_posiciones += f"• `{ticker}`: {valor_pos:.1f}€ ({cambio_pct:+.1f}%) {estado}\n"

    patrimonio_total = cartera["cash_disponible"] + valor_total_posiciones

    # --- REPORTE INTELLIGENCE V8 ---
    reporte = f"🏛️ **TITAN V8 INTELLIGENCE**\n"
    reporte += f"📅 *{datetime.now().strftime('%d/%m/%Y')} | Persistent Core*\n"
    reporte += f"💳 **Patrimonio Total:** {patrimonio_total:.2f} €\n"
    reporte += f"💵 **Liquidez:** {cartera['cash_disponible']:.2f} €\n\n"
    
    reporte += f"🚦 **ESTADO: {'ALCISTA 🟢' if mercado_sano else 'DEFENSIVO 🔴'}**\n"
    reporte += f"• VIX: {vix:.2f} | Bonos: {'Estables' if mercado_sano else 'Débiles'}\n"
    reporte += "-" * 20 + "\n"

    if es_dia_inversion:
        reporte += msg_capital
        reporte += "📋 **MISIÓN DE COMPRA (DÍA 1):**\n"
        if mercado_sano:
            # Simulamos las órdenes (El usuario debe ejecutarlas en Trade Republic)
            # Y actualizamos el JSON (Simulación de ejecución perfecta)
            reporte += f"1️⃣ **SEGURIDAD (250€):** Compra `IWQU.L`\n"
            reporte += f"2️⃣ **RIESGO (150€):** Compra `{lider_riesgo}` (+{perf_riesgo:.1f}%)\n"
            reporte += f"3️⃣ **EXPLOSIÓN (100€):** Compra `{lider_exp}` (+{perf_exp:.1f}%)\n"
            reporte += "\n⚠️ *Nota: Actualiza manualmente el JSON si los precios difieren.*"
            
            # Lógica de actualización automática de cartera (Opcional/Avanzado)
            # Aquí podríamos restar el cash y sumar unidades automáticamente
            # Para V8 simplificado, solo avisamos.
        else:
            reporte += "🛡️ **MERCADO PELIGROSO.** Mantener los 500€ en Cuenta Remunerada (4%).\n"
    else:
        reporte += "👮 **MODO GUARDIÁN (AUDITORÍA):**\n"
        if detalle_posiciones:
            reporte += detalle_posiciones
        else:
            reporte += "• No hay posiciones abiertas. Liquidez al 100%.\n"
            
        if not mercado_sano:
            reporte += "\n🚨 **ALERTA:** Considerar venta de posiciones con ⚠️."

    reporte += "\n" + "-" * 20 + "\n"
    reporte += "🔮 **TITAN MEMORY:** Datos guardados en repositorio."

    enviar_telegram(reporte)
    # Guardamos el estado final (por si hubo inyección de capital)
    guardar_cartera(cartera)

if __name__ == "__main__":
    ejecutar_titan_v8()
