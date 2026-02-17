import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime

# --- GEN 5.1 TITAN: TRADE REPUBLIC MANAGER (DEBUGGED) ---
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# CONFIGURACIÓN CAPITAL MENSUAL
CAP_MENSUAL = 500 

# UNIVERSO DE ACTIVOS
TICKERS_REF = ['^VIX', 'HYG', 'SPY'] 
TICKERS_SEGURIDAD = ['IWQU.L']
TICKERS_RIESGO_POOL = ['NVDA', 'MSFT', 'AAPL', 'GOOGL', 'META', 'AMZN', 'AVGO', 'TSM', 'ASML']
TICKERS_EXPLOSION_POOL = ['COIN', 'MSTR', 'MARA', 'TSLA', 'PLTR']

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Error Telegram: {e}")

def obtener_lider_momentum(data, tickers, ventana=60):
    """Retorna el activo con mejor rendimiento relativo."""
    best_ticker = None
    best_perf = -999
    
    # Validamos qué tickers existen realmente en los datos descargados
    tickers_disponibles = [t for t in tickers if t in data.columns]
    
    if not tickers_disponibles:
        # Si no hay datos, devolvemos el primero de la lista original por defecto
        return tickers[0], 0.0

    for t in tickers_disponibles:
        try:
            # Check de seguridad por si faltan datos históricos
            if len(data[t].dropna()) < ventana:
                continue
                
            precio_hoy = data[t].iloc[-1]
            precio_base = data[t].iloc[-ventana]
            
            # Evitar división por cero o datos nulos
            if pd.isna(precio_hoy) or pd.isna(precio_base) or precio_base == 0:
                continue
                
            perf = (precio_hoy / precio_base) - 1
            if perf > best_perf:
                best_perf = perf
                best_ticker = t
        except Exception: 
            continue
            
    # Si después del bucle sigue siendo None, asignamos el primero por defecto
    if best_ticker is None:
        best_ticker = tickers[0]
        best_perf = 0.0
        
    return best_ticker, best_perf * 100

def ejecutar_titan_v5():
    print("🧠 GEN 5.1: Iniciando Protocolo Blindado...")
    
    # 1. DATOS DE MERCADO (Descarga Robusta)
    todos = TICKERS_REF + TICKERS_SEGURIDAD + TICKERS_RIESGO_POOL + TICKERS_EXPLOSION_POOL
    
    try:
        # auto_adjust=True ayuda a evitar problemas de precios
        data = yf.download(todos, period="6mo", progress=False, auto_adjust=True)
        
        # Corrección crítica para yfinance reciente: 
        # Si descarga múltiples tickers, a veces crea MultiIndex. Nos quedamos con 'Close'.
        if 'Close' in data.columns and isinstance(data.columns, pd.MultiIndex):
            data = data['Close']
        elif 'Close' in data.columns:
             # Si no es MultiIndex pero tiene columna Close (caso raro 1 solo ticker)
            pass 
        
        # Si data está vacío (error de red)
        if data.empty:
            raise Exception("Datos vacíos descargados")
            
    except Exception as e:
        enviar_telegram(f"⚠️ Error crítico descargando datos: {e}. Revisa GitHub.")
        return

    # 2. ANÁLISIS MACRO (SEMÁFORO)
    try:
        vix = data['^VIX'].iloc[-1] if '^VIX' in data.columns else 20.0
        
        # Gestión de fallo en HYG
        if 'HYG' in data.columns:
            hyg_hoy = data['HYG'].iloc[-1]
            hyg_media = data['HYG'].rolling(20).mean().iloc[-1]
            mercado_sano = (vix < 32) and (hyg_hoy > hyg_media * 0.98)
            hyg_status = "Estables ✅" if hyg_hoy > hyg_media * 0.98 else "Debilidad ⚠️"
        else:
            mercado_sano = (vix < 32)
            hyg_status = "N/A ⚠️"
            
    except:
        vix = 20.0
        mercado_sano = True # Modo seguro por defecto
        hyg_status = "Error Datos"

    # 3. CONTEXTO TEMPORAL
    dia_actual = datetime.now().day
    es_dia_inversion = (dia_actual == 1)
    
    # 4. SELECCIÓN DE ACTIVOS LÍDERES
    lider_riesgo, perf_riesgo = obtener_lider_momentum(data, TICKERS_RIESGO_POOL)
    lider_exp, perf_exp = obtener_lider_momentum(data, TICKERS_EXPLOSION_POOL)
    
    # Verificación de Salud Técnica (Precio > Media 20 días)
    try:
        sma20_riesgo = data[lider_riesgo].rolling(20).mean().iloc[-1]
        precio_riesgo = data[lider_riesgo].iloc[-1]
        salud_riesgo = precio_riesgo > sma20_riesgo
    except:
        salud_riesgo = True # Por defecto si faltan datos

    try:
        sma20_exp = data[lider_exp].rolling(20).mean().iloc[-1]
        precio_exp = data[lider_exp].iloc[-1]
        salud_exp = precio_exp > sma20_exp
    except:
        salud_exp = True

    # --- GENERACIÓN DEL INFORME TITAN ---
    reporte = f"🏛️ **TITAN INTELLIGENCE: INFORME OPERATIVO**\n"
    reporte += f"📅 *{datetime.now().strftime('%d/%m/%Y')} | Trade Republic Manager*\n\n"
    
    # SECCIÓN 1: ESTADO DEL MERCADO
    estado_str = "ALCISTA (RISK ON)" if mercado_sano else "DEFENSIVO (RISK OFF)"
    icono_estado = "🟢" if mercado_sano else "🔴"
    
    reporte += f"🚦 **ESTADO GLOBAL: {estado_str}** {icono_estado}\n"
    reporte += f"• **VIX:** {vix:.2f} {'✅' if vix < 30 else '⚠️'}\n"
    reporte += f"• **Bonos (HYG):** {hyg_status}\n"
    
    if mercado_sano:
        reporte += "• **Veredicto:** El flujo de capital favorece a la Renta Variable.\n"
    else:
        reporte += "• **Veredicto:** Mercado inestable. Prioridad: Protección de Capital.\n"
    
    reporte += "-" * 20 + "\n\n"
    
    # SECCIÓN 2: LA MISIÓN
    
    if es_dia_inversion:
        reporte += f"📋 **TU MISIÓN DE HOY (INYECCIÓN MENSUAL)**\n"
        reporte += f"💰 **Capital Nuevo:** {CAP_MENSUAL} €\n\n"
        
        if not mercado_sano:
            reporte += "🛡️ **ACCIÓN DEFENSIVA:**\n"
            reporte += "• **NO COMPRAR ACCIONES HOY.**\n"
            reporte += "• Deja los 500€ en la cuenta de Efectivo (4%).\n"
        else:
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
        reporte += f"👮 **MODO GUARDIÁN (AUDITORÍA DIARIA)**\n"
        
        if not mercado_sano:
             reporte += "🚨 **ALERTA ROJA - ACCIÓN REQUERIDA**\n"
             reporte += "El mercado se ha girado a BAJISTA hoy.\n"
             reporte += "1. **Vender** posiciones especulativas (`COIN`, `NVDA`, etc).\n"
             reporte += "2. **Mover liquidez** a Cuenta Remunerada.\n"
        else:
            reporte += f"🔍 **Revisión `{lider_riesgo}`:**\n"
            if salud_riesgo:
                reporte += "• ✅ **Saludable:** Precio sobre la media. **MANTENER**.\n"
            else:
                reporte += "• ⚠️ **PELIGRO:** Tendencia rota. **VENDER/ROTAR**.\n"
            
            reporte += f"\n🔍 **Revisión `{lider_exp}`:**\n"
            if salud_exp:
                reporte += "• ✅ **Saludable:** Momentum intacto. **MANTENER**.\n"
            else:
                reporte += "• ⚠️ **PELIGRO:** Debilidad. **VENDER**.\n"

    reporte += "\n" + "-" * 20 + "\n"
    reporte += "🔮 **DATA INSIGHT:**\n"
    reporte += "Sistema Blindado V5.1 - Ejecución robusta."

    enviar_telegram(reporte)

if __name__ == "__main__":
    ejecutar_titan_v5()
