import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime

# --- GEN 4.0 TITAN: CLOUD NEURAL ARCHITECTURE ---
# Recuperamos las claves seguras de GitHub
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# CONFIGURACIÓN DE CAPITAL
CAP_BASE = 500

# UNIVERSO DE ACTIVOS (Selección Institucional)
# Macro: VIX (Miedo), HYG (Bonos Basura/Riesgo Crédito)
TICKERS_REF = ['^VIX', 'HYG'] 
TICKERS_SEGURIDAD = ['IWQU.L']

# Pool Riesgo (Tech Leaders): El bot elegirá al MÁS FUERTE de estos
TICKERS_RIESGO_POOL = ['NVDA', 'MSFT', 'AAPL', 'GOOGL', 'META', 'AMZN', 'AVGO', 'COST']

# Pool Explosión (High Beta): El bot elegirá al MÁS RÁPIDO de estos
TICKERS_EXPLOSION_POOL = ['COIN', 'BITO', 'MSTR', 'TSLA', 'IWM']

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Error Telegram: {e}")

def obtener_fuerza_relativa(data, tickers, ventana_dias=60):
    """
    Calcula qué acciones han subido más en los últimos X días.
    Retorna una lista ordenada de ganadores: [('NVDA', 0.15), ('MSFT', 0.05)...]
    """
    rendimientos = {}
    for t in tickers:
        try:
            # Precio hoy / Precio hace X días - 1
            # Usamos 'ffill' para rellenar datos faltantes si es festivo
            precio_hoy = data[t].iloc[-1]
            precio_pasado = data[t].iloc[-ventana_dias]
            roi = (precio_hoy / precio_pasado) - 1
            rendimientos[t] = roi
        except:
            rendimientos[t] = -999 # Si falla, lo descartamos
            
    # Ordenar de mayor a menor rendimiento
    ranking = sorted(rendimientos.items(), key=lambda x: x[1], reverse=True)
    return ranking

def ejecutar_titan():
    print("🧠 GEN 4.0 TITAN: Iniciando análisis institucional...")
    
    # 1. DESCARGA DE DATOS MASIVA (6 meses para calcular tendencias)
    todos_tickers = TICKERS_REF + TICKERS_SEGURIDAD + TICKERS_RIESGO_POOL + TICKERS_EXPLOSION_POOL
    data = yf.download(todos_tickers, period="6mo", progress=False)['Close']
    
    # 2. ANÁLISIS MACRO (REGIME FILTER)
    vix = data['^VIX'].iloc[-1]
    
    # Análisis de Bonos Basura (HYG). Si HYG cae, el mercado está enfermo.
    hyg_hoy = data['HYG'].iloc[-1]
    hyg_media = data['HYG'].rolling(20).mean().iloc[-1]
    
    # CONDICIÓN DE SEGURIDAD:
    # 1. VIX debe ser menor a 32 (Pánico controlado)
    # 2. HYG no debe estar desplomándose (Precio > 98% de su media)
    mercado_sano = (vix < 32) and (hyg_hoy > hyg_media * 0.98)
    
    # 3. CONSTRUCCIÓN DEL REPORTE
    reporte = f"🏛️ **TITAN INTELLIGENCE: INFORME DIARIO**\n"
    reporte += f"📅 *{datetime.now().strftime('%d/%m/%Y')} | Estrategia GEN 4.0*\n\n"
    
    if not mercado_sano:
        # ALERTA DE PÁNICO
        reporte += "🚨 **ESTADO: DEFCON 1 (PELIGRO)**\n"
        reporte += f"• **VIX:** {vix:.2f} (Alto Riesgo)\n"
        reporte += f"• **Bonos:** Señal de debilidad crediticia.\n"
        reporte += "-" * 20 + "\n"
        reporte += "🛡️ **MISIÓN DE HOY:**\n"
        reporte += "• **NO COMPRAR RIESGO NI EXPLOSIÓN.**\n"
        reporte += "• Mantener los 500€ en Efectivo o Cuenta Remunerada.\n"
        reporte += "• *Razón:* El mercado está inestable. Preservar capital es prioridad."
        enviar_telegram(reporte)
        return

    # SI EL MERCADO ESTÁ SANO, CALCULAMOS GANADORES
    
    # Ranking Riesgo (Tech)
    ranking_riesgo = obtener_fuerza_relativa(data, TICKERS_RIESGO_POOL)
    lider_riesgo = ranking_riesgo[0][0]
    perf_riesgo = ranking_riesgo[0][1] * 100 
    segundo_riesgo = ranking_riesgo[1][0] # El subcampeón (por si acaso)

    # Ranking Explosión (Cripto/Growth)
    ranking_exp = obtener_fuerza_relativa(data, TICKERS_EXPLOSION_POOL)
    lider_exp = ranking_exp[0][0]
    perf_exp = ranking_exp[0][1] * 100

    # REPORTE ALCISTA (FORMATO MILITAR)
    reporte += f"🚦 **ESTADO DEL MERCADO: ALCISTA (RISK ON)**\n"
    reporte += f"• **VIX (Miedo):** {vix:.2f} (Bajo) ✅\n"
    reporte += f"• **Bonos (HYG):** Estables ✅\n"
    reporte += f"• **Veredicto:** Luz verde para despliegue de capital.\n"
    reporte += "-" * 20 + "\n\n"

    reporte += "📋 **TU MISIÓN DE HOY (500€)**\n\n"

    # BLOQUE 1: SEGURIDAD
    cap_seguridad = CAP_BASE * 0.5 # 250
    reporte += f"1️⃣ **ESCUDO (SEGURIDAD) | {cap_seguridad:.0f} €**\n"
    reporte += f"• 🎯 **Activo:** `IWQU.L` (World Quality)\n"
    reporte += f"• 🛒 **Orden:** Compra a Mercado.\n"
    reporte += f"• 🧠 **Por qué:** Base blindada. Empresas rentables mundiales.\n\n"

    # BLOQUE 2: RIESGO
    cap_riesgo = CAP_BASE * 0.3 # 150
    reporte += f"2️⃣ **MOTOR (RIESGO) | {cap_riesgo:.0f} €**\n"
    reporte += f"• 🎯 **Activo:** `{lider_riesgo}`\n"
    reporte += f"• 🏆 **Fuerza:** +{perf_riesgo:.1f}% (60 días).\n"
    reporte += f"• 🥈 *Alternativa:* {segundo_riesgo}\n"
    reporte += f"• 🛒 **Orden:** Compra a Mercado.\n"
    reporte += f"• 🧠 **Por qué:** El algoritmo confirma que es la acción más fuerte del pool tecnológico hoy. \n\n"

    # BLOQUE 3: EXPLOSIÓN
    cap_explosion = CAP_BASE * 0.2 # 100
    reporte += f"3️⃣ **NITRO (EXPLOSIÓN) | {cap_explosion:.0f} €**\n"
    reporte += f"• 🎯 **Activo:** `{lider_exp}`\n"
    reporte += f"• 🚀 **Momentum:** +{perf_exp:.1f}% (Líder explosivo).\n"
    reporte += f"• 🛒 **Orden:** Compra a Mercado.\n"
    reporte += f"• 🧠 **Por qué:** Alta volatilidad a favor. El capital especulativo está entrando aquí.\n"
    
    reporte += "-" * 20 + "\n"
    reporte += "🔮 **DATA INSIGHT:**\n"
    reporte += "Ejecuta el plan sin emociones. El interés compuesto hará el resto."

    enviar_telegram(reporte)

if __name__ == "__main__":
    ejecutar_titan()
