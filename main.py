import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime

# --- GEN 5.0 TITAN: TRADE REPUBLIC MANAGER ---
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# CONFIGURACIÓN CAPITAL MENSUAL
CAP_MENSUAL = 500 

# UNIVERSO DE ACTIVOS (Trade Republic Friendly)
# Referencias Macro
TICKERS_REF = ['^VIX', 'HYG', 'SPY'] 
TICKERS_SEGURIDAD = ['IWQU.L'] # iShares Edge MSCI World Quality

# Pool Riesgo (Tech/Semiconductores)
TICKERS_RIESGO_POOL = ['NVDA', 'MSFT', 'AAPL', 'GOOGL', 'META', 'AMZN', 'AVGO', 'TSM', 'ASML']

# Pool Explosión (Cripto Proxy / High Beta)
TICKERS_EXPLOSION_POOL = ['COIN', 'MSTR', 'MARA', 'TSLA', 'PLTR']

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
    except: pass

def obtener_lider_momentum(data, tickers, ventana=60):
    """Retorna el activo con mejor rendimiento relativo."""
    best_ticker = None
    best_perf = -999
    
    for t in tickers:
        try:
            precio_hoy = data[t].iloc[-1]
            precio_base = data[t].iloc[-ventana]
            perf = (precio_hoy / precio_base) - 1
            if perf > best_perf:
                best_perf = perf
                best_ticker = t
        except: continue
        
    return best_ticker, best_perf * 100

def ejecutar_titan_v5():
    print("🧠 GEN 5.0: Iniciando Protocolo Trade Republic...")
    
    # 1. DATOS DE MERCADO
    todos = TICKERS_REF + TICKERS_SEGURIDAD + TICKERS_RIESGO_POOL + TICKERS_EXPLOSION_POOL
    data = yf.download(todos, period="6mo", progress=False)['Close']
    
    # 2. ANÁLISIS MACRO (SEMÁFORO)
    vix = data['^VIX'].iloc[-1]
    hyg_hoy = data['HYG'].iloc[-1]
    hyg_media = data['HYG'].rolling(20).mean().iloc[-1]
    
    # Semáforo Verde si VIX < 32 y Bonos (HYG) estables
    mercado_sano = (vix < 32) and (hyg_hoy > hyg_media * 0.98)
    
    # 3. CONTEXTO TEMPORAL
    dia_actual = datetime.now().day
    es_dia_inversion = (dia_actual == 1) # Solo el día 1 se inyecta dinero
    
    # 4. SELECCIÓN DE ACTIVOS LÍDERES (Para comprar o vigilar)
    lider_riesgo, perf_riesgo = obtener_lider_momentum(data, TICKERS_RIESGO_POOL)
    lider_exp, perf_exp = obtener_lider_momentum(data, TICKERS_EXPLOSION_POOL)
    
    # Verificación de Salud Técnica (Precio > Media 20 días)
    # Si el activo líder ha perdido su media de 20 días, es señal de VENTA/CORRECCIÓN
    sma20_riesgo = data[lider_riesgo].rolling(20).mean().iloc[-1]
    precio_riesgo = data[lider_riesgo].iloc[-1]
    salud_riesgo = precio_riesgo > sma20_riesgo

    sma20_exp = data[lider_exp].rolling(20).mean().iloc[-1]
    precio_exp = data[lider_exp].iloc[-1]
    salud_exp = precio_exp > sma20_exp

    # --- GENERACIÓN DEL INFORME TITAN ---
    reporte = f"🏛️ **TITAN INTELLIGENCE: INFORME OPERATIVO**\n"
    reporte += f"📅 *{datetime.now().strftime('%d/%m/%Y')} | Trade Republic Manager*\n\n"
    
    # SECCIÓN 1: ESTADO DEL MERCADO
    estado_str = "ALCISTA (RISK ON)" if mercado_sano else "DEFENSIVO (RISK OFF)"
    icono_estado = "🟢" if mercado_sano else "🔴"
    
    reporte += f"🚦 **ESTADO GLOBAL: {estado_str}** {icono_estado}\n"
    reporte += f"• **VIX:** {vix:.2f} {'✅' if vix < 30 else '⚠️'}\n"
    reporte += f"• **Bonos (HYG):** {'Estables ✅' if hyg_hoy > hyg_media * 0.98 else 'Debilidad Detectada ⚠️'}\n"
    
    if mercado_sano:
        reporte += "• **Veredicto:** El flujo de capital favorece a la Renta Variable.\n"
    else:
        reporte += "• **Veredicto:** Mercado inestable. Prioridad: Protección de Capital.\n"
    
    reporte += "-" * 20 + "\n\n"
    
    # SECCIÓN 2: LA MISIÓN (Diferente según el día)
    
    if es_dia_inversion:
        # --- MODO DÍA 1: INYECCIÓN DE CAPITAL ---
        reporte += f"📋 **TU MISIÓN DE HOY (INYECCIÓN MENSUAL)**\n"
        reporte += f"💰 **Capital Nuevo:** {CAP_MENSUAL} €\n\n"
        
        if not mercado_sano:
            reporte += "🛡️ **ACCIÓN DEFENSIVA:**\n"
            reporte += "• **NO COMPRAR ACCIONES HOY.**\n"
            reporte += "• Deja los 500€ en la cuenta de Efectivo (4%).\n"
            reporte += "• *Razón:* Esperamos a que pase la tormenta.\n"
        else:
            # Plan de Compra
            reporte += f"1️⃣ **ESCUDO (SEGURIDAD) | 250 €**\n"
            reporte += f"• 🎯 **Activo:** `IWQU.L`\n"
            reporte += f"• 🛒 **Orden:** Compra a Mercado.\n"
            reporte += f"• 🧠 **Por qué:** Base de calidad mundial.\n\n"
            
            reporte += f"2️⃣ **MOTOR (RIESGO) | 150 €**\n"
            reporte += f"• 🎯 **Activo:** `{lider_riesgo}`\n"
            reporte += f"• 🏆 **Fuerza:** +{perf_riesgo:.1f}% (Líder Tech).\n"
            reporte += f"• 🛒 **Orden:** Compra a Mercado.\n\n"
            
            reporte += f"3️⃣ **NITRO (EXPLOSIÓN) | 100 €**\n"
            reporte += f"• 🎯 **Activo:** `{lider_exp}`\n"
            reporte += f"• 🚀 **Momentum:** +{perf_exp:.1f}% (Líder High Beta).\n"
            reporte += f"• 🛒 **Orden:** Compra a Mercado.\n"

    else:
        # --- MODO DÍA 2-31: GUARDIÁN DE CARTERA ---
        reporte += f"👮 **MODO GUARDIÁN (AUDITORÍA DIARIA)**\n"
        reporte += "Revisando salud de tus posiciones acumuladas...\n\n"
        
        if not mercado_sano:
             reporte += "🚨 **ALERTA ROJA - ACCIÓN REQUERIDA**\n"
             reporte += "El mercado se ha girado a BAJISTA hoy.\n"
             reporte += "1. **Vender** posiciones especulativas (`COIN`, `NVDA`, etc).\n"
             reporte += "2. **Mover liquidez** a Cuenta Remunerada.\n"
        else:
            # Revisión individual
            reporte += f"🔍 **Revisión `{lider_riesgo}`:**\n"
            if salud_riesgo:
                reporte += "• ✅ **Saludable:** Precio sobre la media. **MANTENER**.\n"
            else:
                reporte += "• ⚠️ **PELIGRO:** Ha perdido la tendencia corto plazo. **VALORAR VENTA/ROTACIÓN**.\n"
            
            reporte += f"\n🔍 **Revisión `{lider_exp}`:**\n"
            if salud_exp:
                reporte += "• ✅ **Saludable:** Momentum intacto. **MANTENER**.\n"
            else:
                reporte += "• ⚠️ **PELIGRO:** Debilidad detectada. **VALORAR VENTA**.\n"

    reporte += "\n" + "-" * 20 + "\n"
    reporte += "🔮 **DATA INSIGHT:**\n"
    reporte += "El interés compuesto se construye evitando las grandes caídas, no solo buscando subidas. Trade Republic te paga por esperar (4%) si el mercado duda."

    enviar_telegram(reporte)

if __name__ == "__main__":
    ejecutar_titan_v5()
