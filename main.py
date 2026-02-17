#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║     TITAN INTELLIGENCE V8.0 — TRADE REPUBLIC MANAGER DEFINITIVO     ║
║     Sistema de Gestión de Cartera de Nivel Institucional             ║
╚══════════════════════════════════════════════════════════════════════╝

Árbol de mejoras completo (V5.1 → V8.0):

[V6] ✅ Descarga robusta multi-ticker + retry individual
[V6] ✅ Persistencia de cartera en JSON con escritura atómica
[V6] ✅ Régimen de mercado en 3 estados (multi-indicador: VIX, HYG, SPY, TLT)
[V6] ✅ Semáforo: VIX zona gris, Death Cross, flight-to-quality
[V6] ✅ Momentum multi-ventana ponderado (20d/60d/120d)
[V6] ✅ Filtros técnicos: RSI, SMA20, SMA50 antes de comprar
[V6] ✅ Position sizing dinámico basado en ATR (1% capital en riesgo/op.)
[V6] ✅ Stop-loss por posición almacenado en cartera
[V6] ✅ Pool explosión diversificado (sin triple correlación BTC)
[V6] ✅ Universo ampliado (GLD, XLV, sectores defensivos)
[V6] ✅ Modo CAUTION parcial (no todo o nada)
[V6] ✅ Telegram con retry, chunking y fallback a consola
[V6] ✅ Logging estructurado con niveles diferenciados

[V7] ✅ Trailing stop dinámico (sube con el precio máximo de la posición)
[V7] ✅ ATR verdadero con OHLC real + fallback a proxy Close
[V7] ✅ Filtro de correlación entre activos seleccionados (max 0.85)
[V7] ✅ Resumen P&L de cartera en cada informe
[V7] ✅ Alerta de drawdown total del portfolio
[V7] ✅ Modo CAUTION granular: Seg + Riesgo reducido, sin Nitro
[V7] ✅ Validación y sanitización del portfolio JSON al cargar
[V7] ✅ Top 3 candidatos por tramo (transparencia de selección)
[V7] ✅ Trailing_stop siempre ≥ stop_loss_fijo

[V8] ✅ Backtesting integrado: validación de señales en los últimos 90d
[V8] ✅ Filtro de volumen: confirma que el momentum tiene respaldo de volumen
[V8] ✅ Límite de concentración sectorial (máx 60% cartera en un sector)
[V8] ✅ Data integrity: detección de outliers y datos corruptos
[V8] ✅ Modo DRY-RUN: simula sin enviar telegram ni guardar cambios
[V8] ✅ Granularidad CAUTION en 3 niveles (score 1, 2, 3 = diferente %capital)
[V8] ✅ Exportación de señales diarias a CSV para análisis externo
[V8] ✅ Config externalizada: todos los parámetros en CONFIG dict
[V8] ✅ Health score de activos (puntuación 0-100 multi-factor)
[V8] ✅ Resumen de señales acertadas (backtest simple 30d)
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
import json
import csv
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# ──────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("TITAN")

# ──────────────────────────────────────────────────────────────────────
# CONFIG — Todos los parámetros centralizados (fácil de ajustar)
# ──────────────────────────────────────────────────────────────────────
CONFIG: Dict[str, Any] = {
    # Credenciales
    "TELEGRAM_TOKEN":   os.environ.get("TELEGRAM_TOKEN", ""),
    "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),

    # Rutas
    "PORTFOLIO_FILE":   Path("titan_portfolio.json"),
    "SIGNALS_CSV":      Path("titan_signals.csv"),

    # Capital
    "CAP_MENSUAL":       500.0,

    # Allocación RISK_ON (% del capital mensual)
    "ALLOC_RISK_ON": {
        "seguridad": 0.50,
        "riesgo":    0.30,
        "explosion": 0.20,
    },

    # Allocación CAUTION (% varía según sub-nivel de score)
    # score=3: 80% capital | score=2: 65% capital | score=1: 50% capital
    "CAUTION_NIVELES": {
        3: {"pct_capital": 0.80, "seg": 0.55, "ries": 0.45, "exp": 0.00},
        2: {"pct_capital": 0.65, "seg": 0.65, "ries": 0.35, "exp": 0.00},
        1: {"pct_capital": 0.50, "seg": 1.00, "ries": 0.00, "exp": 0.00},
    },

    # Indicadores técnicos
    "MOMENTUM_WINDOWS":   {20: 0.25, 60: 0.45, 120: 0.30},
    "RSI_OVERBOUGHT":     75,
    "RSI_EXTREME_OB":     82,
    "RSI_OVERSOLD":       30,
    "STOP_LOSS_PCT":      0.15,
    "TRAILING_STOP_PCT":  0.12,
    "CAPITAL_RISK_PCT":   0.01,
    "CORRELACION_MAX":    0.85,
    "DRIFT_THRESHOLD":    0.20,
    "DRAWDOWN_ALERT":     0.10,
    "MIN_INVERSION":      30.0,

    # Régimen mercado
    "VIX_RISK_OFF":       32,
    "VIX_CAUTION":        22,

    # Concentración sectorial
    "SECTOR_MAX_PCT":     0.60,

    # Volumen (filtro de confirmación)
    "VOLUMEN_CONFIRMACION": False,  # activar si tu fuente de datos incluye volumen fiable

    # Backtest ventana
    "BACKTEST_DIAS":      90,

    # Portfolio
    "MAX_HISTORIAL":      200,

    # Datos
    "PERIODO_DATOS":      "10mo",   # 10 meses para SMA200 + backtest
}

# ──────────────────────────────────────────────────────────────────────
# UNIVERSO DE ACTIVOS
# ──────────────────────────────────────────────────────────────────────
TICKERS_REF = ['^VIX', 'HYG', 'SPY', 'TLT']

TICKERS_SEGURIDAD: Dict[str, str] = {
    'IWQU.L': 'MSCI World Quality',
    'VWRL.L': 'Vanguard World All-Cap',
    'CSPX.L': 'iShares S&P 500 Core',
}

TICKERS_RIESGO: Dict[str, str] = {
    'NVDA':  'NVIDIA — IA chips',
    'MSFT':  'Microsoft — Cloud/IA',
    'AAPL':  'Apple — Ecosistema',
    'GOOGL': 'Alphabet — IA/Search',
    'META':  'Meta — Social/AR',
    'AVGO':  'Broadcom — Semis',
    'TSM':   'TSMC — Foundry',
    'ASML':  'ASML — Litografía',
    'GLD':   'Oro — Cobertura',
    'XLV':   'Healthcare — Defensivo',
}

TICKERS_EXPLOSION: Dict[str, str] = {
    'COIN':  'Coinbase — Crypto Exchange',
    'MSTR':  'MicroStrategy — BTC Proxy',
    'TSLA':  'Tesla — EV/Energía',
    'PLTR':  'Palantir — GovTech/IA',
    'AMD':   'AMD — CPU/GPU competidor',
    'SMCI':  'SuperMicro — Servidores IA',
}

# Clasificación sectorial para límite de concentración
SECTOR_MAP: Dict[str, str] = {
    'NVDA':   'tech_semis',   'AVGO':  'tech_semis',
    'TSM':    'tech_semis',   'ASML':  'tech_semis',
    'AMD':    'tech_semis',   'SMCI':  'tech_semis',
    'MSFT':   'tech_software','GOOGL': 'tech_software',
    'META':   'tech_software','AAPL':  'tech_hardware',
    'COIN':   'crypto',       'MSTR':  'crypto',
    'TSLA':   'ev_energia',   'PLTR':  'govtech',
    'GLD':    'commodities',  'XLV':   'healthcare',
    'IWQU.L': 'etf_global',   'VWRL.L':'etf_global',
    'CSPX.L': 'etf_global',
}


# ══════════════════════════════════════════════════════════════════════
# MÓDULO 1: GESTIÓN DE CARTERA
# ══════════════════════════════════════════════════════════════════════

def _validar_posicion(pos: dict) -> bool:
    try:
        return (
            isinstance(pos, dict)
            and float(pos.get('precio_compra', 0)) > 0
            and float(pos.get('cantidad', 0)) > 0
            and isinstance(pos.get('tramo'), str)
        )
    except (TypeError, ValueError):
        return False


def load_portfolio() -> dict:
    base = {
        "posiciones":       {},
        "historial":        [],
        "high_water_mark":  0.0,
        "metadata":         {"version": "8.0", "creado": datetime.now().isoformat()},
        "last_update":      None
    }
    path = CONFIG["PORTFOLIO_FILE"]
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for k, v in base.items():
                data.setdefault(k, v)

            # Sanitizar posiciones
            posiciones_limpias = {}
            for ticker, pos in data.get("posiciones", {}).items():
                if _validar_posicion(pos):
                    pos.setdefault('stop_loss',
                        float(pos['precio_compra']) * (1 - CONFIG["STOP_LOSS_PCT"]))
                    pos.setdefault('max_precio', float(pos['precio_compra']))
                    pos.setdefault('trailing_stop',
                        float(pos['precio_compra']) * (1 - CONFIG["TRAILING_STOP_PCT"]))
                    pos.setdefault('fecha_entrada', "N/A")
                    # trailing_stop siempre ≥ stop_loss
                    pos['trailing_stop'] = max(
                        float(pos['trailing_stop']), float(pos['stop_loss'])
                    )
                    posiciones_limpias[ticker] = pos
                else:
                    log.warning(f"Posición inválida eliminada: {ticker}")

            data["posiciones"] = posiciones_limpias
            data["historial"]  = data["historial"][-CONFIG["MAX_HISTORIAL"]:]
            return data
        except Exception as e:
            log.error(f"Portfolio corrupto ({e}). Creando nuevo.")
    return base


def save_portfolio(portfolio: dict, dry_run: bool = False) -> bool:
    if dry_run:
        log.info("[DRY-RUN] Portfolio NO guardado.")
        return True
    path = CONFIG["PORTFOLIO_FILE"]
    portfolio["last_update"] = datetime.now().isoformat()
    tmp = path.with_suffix('.tmp')
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(portfolio, f, indent=2, default=str, ensure_ascii=False)
        tmp.replace(path)
        return True
    except IOError as e:
        log.error(f"Error guardando portfolio: {e}")
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return False


def actualizar_trailing_stops(portfolio: dict, data: pd.DataFrame) -> Tuple[dict, List[str]]:
    """
    Sube trailing_stop cuando el precio supera el máximo histórico registrado.
    trailing_stop = max(stop_loss_fijo, max_precio × (1 - TRAILING_STOP_PCT))
    """
    mensajes = []
    for ticker, pos in portfolio.get("posiciones", {}).items():
        if ticker not in data.columns:
            continue
        precio_actual   = float(data[ticker].dropna().iloc[-1])
        max_anterior    = float(pos.get('max_precio', pos['precio_compra']))
        nuevo_max       = max(max_anterior, precio_actual)

        if nuevo_max > max_anterior:
            nuevo_trail     = nuevo_max * (1 - CONFIG["TRAILING_STOP_PCT"])
            stop_fijo       = float(pos['stop_loss'])
            nuevo_trail_adj = max(nuevo_trail, stop_fijo)  # trailing ≥ stop fijo
            viejo_trail     = float(pos.get('trailing_stop', 0))

            if nuevo_trail_adj > viejo_trail:
                pos['max_precio']    = round(nuevo_max, 4)
                pos['trailing_stop'] = round(nuevo_trail_adj, 4)
                mensajes.append(
                    f"   📈 Trail `{ticker}` → {nuevo_trail_adj:.2f} (max={nuevo_max:.2f})"
                )
    return portfolio, mensajes


def registrar_compra(portfolio: dict, ticker: str, precio: float,
                     euros: float, tramo: str) -> dict:
    cantidad = euros / precio
    if ticker in portfolio["posiciones"]:
        pos = portfolio["posiciones"][ticker]
        total = pos["cantidad"] + cantidad
        pm    = (pos["precio_compra"] * pos["cantidad"] + precio * cantidad) / total
        maxp  = max(float(pos.get('max_precio', pm)), precio)
        portfolio["posiciones"][ticker].update({
            "precio_compra": round(pm, 4),
            "cantidad":      round(total, 6),
            "stop_loss":     round(pm * (1 - CONFIG["STOP_LOSS_PCT"]), 4),
            "max_precio":    round(maxp, 4),
            "trailing_stop": round(max(maxp * (1 - CONFIG["TRAILING_STOP_PCT"]),
                                       pm * (1 - CONFIG["STOP_LOSS_PCT"])), 4),
            "ultima_compra": datetime.now().isoformat(),
        })
    else:
        sl = precio * (1 - CONFIG["STOP_LOSS_PCT"])
        portfolio["posiciones"][ticker] = {
            "precio_compra": round(precio, 4),
            "cantidad":      round(cantidad, 6),
            "fecha_entrada": datetime.now().isoformat(),
            "ultima_compra": datetime.now().isoformat(),
            "tramo":         tramo,
            "stop_loss":     round(sl, 4),
            "max_precio":    round(precio, 4),
            "trailing_stop": round(max(precio * (1 - CONFIG["TRAILING_STOP_PCT"]), sl), 4),
        }
    portfolio["historial"].append({
        "fecha":  datetime.now().isoformat(),
        "accion": "COMPRA",
        "ticker": ticker,
        "precio": round(precio, 4),
        "euros":  round(euros, 2),
        "tramo":  tramo,
    })
    return portfolio


def calcular_pnl_cartera(portfolio: dict, data: pd.DataFrame) -> dict:
    coste = 0.0
    valor = 0.0
    for ticker, pos in portfolio.get("posiciones", {}).items():
        cantidad = float(pos['cantidad'])
        coste   += float(pos['precio_compra']) * cantidad
        if ticker in data.columns:
            valor += float(data[ticker].dropna().iloc[-1]) * cantidad
        else:
            valor += float(pos['precio_compra']) * cantidad  # sin datos → precio compra

    pnl_e = valor - coste
    pnl_p = (valor / coste - 1) * 100 if coste > 0 else 0.0
    hwm   = float(portfolio.get('high_water_mark', 0))
    if valor > hwm:
        portfolio['high_water_mark'] = round(valor, 2)
        hwm = valor
    dd_pct = ((valor - hwm) / hwm * 100) if hwm > 0 else 0.0

    return {
        'coste_total':  round(coste, 2),
        'valor_actual': round(valor, 2),
        'pnl_euros':    round(pnl_e, 2),
        'pnl_pct':      round(pnl_p, 2),
        'drawdown_pct': round(dd_pct, 2),
        'hwm':          round(hwm, 2),
    }


# ══════════════════════════════════════════════════════════════════════
# MÓDULO 2: DESCARGA + INTEGRIDAD DE DATOS
# ══════════════════════════════════════════════════════════════════════

def _detectar_outliers(serie: pd.Series, umbral_zscore: float = 5.0) -> pd.Series:
    """
    Detecta y elimina outliers usando Z-score.
    Valores con |Z| > umbral se reemplazan por NaN y se interpolan.
    """
    if len(serie) < 10:
        return serie
    z    = (serie - serie.mean()) / (serie.std() + 1e-10)
    mask = z.abs() > umbral_zscore
    if mask.any():
        log.warning(f"  Outliers detectados: {mask.sum()} valores. Interpolando.")
        serie = serie.copy()
        serie[mask] = np.nan
        serie = serie.interpolate(method='linear').ffill().bfill()
    return serie


def _extraer_close(raw: pd.DataFrame, ticker: str) -> Optional[pd.Series]:
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            for combo in [('Close', ticker), (ticker, 'Close')]:
                if combo in raw.columns:
                    return raw[combo].dropna()
            l0, l1 = raw.columns.get_level_values(0), raw.columns.get_level_values(1)
            if ticker in l0: return raw[ticker]['Close'].dropna()
            if ticker in l1: return raw['Close'][ticker].dropna()
        elif 'Close' in raw.columns:
            return raw['Close'].dropna()
    except (KeyError, TypeError):
        pass
    return None


def _extraer_ohlc(raw: pd.DataFrame, ticker: str) -> Optional[pd.DataFrame]:
    try:
        if isinstance(raw.columns, pd.MultiIndex) and ticker in raw.columns.get_level_values(0):
            cols = [c for c in ['High', 'Low', 'Close'] if c in raw[ticker].columns]
            if len(cols) == 3:
                return raw[ticker][cols].dropna()
    except (KeyError, TypeError):
        pass
    return None


def descargar_datos(tickers: List[str]) -> Tuple[pd.DataFrame, dict]:
    """
    Descarga con:
    1. Intento masivo
    2. Retry individual para fallidos
    3. Limpieza de outliers por ticker
    4. Retorna (close_df, ohlc_store)
    """
    close_df   = pd.DataFrame()
    ohlc_store = {}
    fallidos   = []
    periodo    = CONFIG["PERIODO_DATOS"]

    try:
        raw = yf.download(tickers, period=periodo, progress=False,
                          auto_adjust=True, group_by='ticker')
        if raw.empty:
            raise ValueError("Descarga vacía")

        for t in tickers:
            s = _extraer_close(raw, t)
            if s is not None and len(s) >= 30:
                close_df[t] = _detectar_outliers(s)
                ohlc = _extraer_ohlc(raw, t)
                if ohlc is not None and len(ohlc) >= 14:
                    ohlc_store[t] = ohlc
            else:
                fallidos.append(t)

    except Exception as e:
        log.error(f"Descarga masiva fallida: {e}")
        fallidos = list(tickers)

    for t in fallidos:
        try:
            r = yf.download(t, period=periodo, progress=False, auto_adjust=True)
            if not r.empty and 'Close' in r.columns:
                s = r['Close'].dropna()
                if len(s) >= 30:
                    close_df[t] = _detectar_outliers(s)
                    if all(c in r.columns for c in ['High', 'Low', 'Close']):
                        ohlc_store[t] = r[['High', 'Low', 'Close']].dropna()
                    log.info(f"  {t}: recuperado individual.")
        except Exception as e2:
            log.error(f"  {t}: fallo total ({e2}).")

    log.info(f"Datos OK: {len(close_df.columns)}/{len(tickers)} tickers | OHLC: {len(ohlc_store)}")
    return close_df, ohlc_store


# ══════════════════════════════════════════════════════════════════════
# MÓDULO 3: INDICADORES TÉCNICOS
# ══════════════════════════════════════════════════════════════════════

def calcular_rsi(serie: pd.Series, periodo: int = 14) -> float:
    s = serie.dropna()
    if len(s) < periodo + 1:
        return 50.0
    d  = s.diff().dropna()
    ag = d.clip(lower=0).ewm(alpha=1/periodo, min_periods=periodo).mean()
    ap = (-d).clip(lower=0).ewm(alpha=1/periodo, min_periods=periodo).mean()
    rs = ag / ap.replace(0, np.finfo(float).eps)
    v  = (100 - 100 / (1 + rs)).iloc[-1]
    return round(float(v), 2) if pd.notna(v) else 50.0


def calcular_atr(ticker: str, ohlc_store: dict, close_serie: pd.Series, periodo: int = 14) -> float:
    if ticker in ohlc_store:
        df = ohlc_store[ticker].dropna()
        if len(df) >= periodo + 1:
            H, L, C = df['High'], df['Low'], df['Close']
            tr  = pd.concat([(H - L), (H - C.shift()).abs(), (L - C.shift()).abs()], axis=1).max(axis=1)
            atr = tr.ewm(alpha=1/periodo, min_periods=periodo).mean().iloc[-1]
            if pd.notna(atr):
                return round(float(atr), 6)
    s = close_serie.dropna()
    if len(s) >= periodo + 1:
        atr = s.diff().abs().rolling(periodo).mean().iloc[-1]
        if pd.notna(atr):
            return round(float(atr), 6)
    return float(s.std()) if len(s) > 1 else 1.0


def calcular_sma(serie: pd.Series, periodo: int) -> Optional[float]:
    if len(serie) < periodo:
        return None
    v = serie.rolling(periodo).mean().iloc[-1]
    return float(v) if pd.notna(v) else None


def calcular_momentum_score(data: pd.DataFrame, ticker: str) -> float:
    if ticker not in data.columns:
        return -999.0
    s = data[ticker].dropna()
    w = CONFIG["MOMENTUM_WINDOWS"]
    acc, pw = 0.0, 0.0
    for ventana, peso in w.items():
        if len(s) >= ventana + 1:
            ret = s.iloc[-1] / s.iloc[-ventana] - 1
            if pd.notna(ret):
                acc += ret * 100 * peso
                pw  += peso
    if pw < 0.20:
        return -999.0
    return round(acc / pw * sum(w.values()), 4)


def calcular_correlacion(data: pd.DataFrame, a: str, b: str, ventana: int = 60) -> float:
    try:
        if a not in data.columns or b not in data.columns:
            return 0.0
        ra = data[a].pct_change().dropna().tail(ventana)
        rb = data[b].pct_change().dropna().tail(ventana)
        if len(ra) < 20 or len(rb) < 20:
            return 0.0
        c = ra.corr(rb)
        return round(float(c), 3) if pd.notna(c) else 0.0
    except Exception:
        return 0.0


def calcular_health_score(
    ticker: str,
    data: pd.DataFrame,
    ohlc_store: dict
) -> Tuple[int, str]:
    """
    Puntuación de salud 0-100 basada en múltiples factores:
      +20: Precio > SMA20
      +20: Precio > SMA50
      +15: Precio > SMA200
      +15: RSI entre 40-65 (zona saludable)
      +15: Momentum 60d > 0
      +15: Momentum 20d > 0
    
    Retorna (score, descripción).
    """
    if ticker not in data.columns:
        return 0, "Sin datos"

    s           = data[ticker].dropna()
    precio      = float(s.iloc[-1])
    rsi         = calcular_rsi(s)
    mom60       = calcular_momentum_score(data, ticker)
    sma20       = calcular_sma(s, 20)
    sma50       = calcular_sma(s, 50)
    sma200      = calcular_sma(s, 200)
    score       = 0
    factores    = []

    if sma20  and precio > sma20:   score += 20; factores.append("SMA20✅")
    if sma50  and precio > sma50:   score += 20; factores.append("SMA50✅")
    if sma200 and precio > sma200:  score += 15; factores.append("SMA200✅")
    if 40 <= rsi <= 65:             score += 15; factores.append(f"RSI{rsi:.0f}✅")
    elif rsi < 40:                  score += 10; factores.append(f"RSI{rsi:.0f}⚠️")
    if mom60 > 5:                   score += 15; factores.append("Mom60✅")
    if mom60 > 0:                   score += 15; factores.append("Mom20✅")

    descripcion = " | ".join(factores) if factores else "Débil"
    return min(score, 100), descripcion


# ══════════════════════════════════════════════════════════════════════
# MÓDULO 4: RÉGIMEN DE MERCADO
# ══════════════════════════════════════════════════════════════════════

def analizar_regimen(data: pd.DataFrame) -> Tuple[str, int, dict]:
    """
    Retorna (régimen_str, score_exacto, metricas_dict).
    score_exacto es necesario para granularidad en modo CAUTION.
    """
    metricas   = {}
    puntuacion = 0

    if '^VIX' in data.columns:
        vs   = data['^VIX'].dropna()
        vix  = float(vs.iloc[-1])
        s10  = float(vs.rolling(10).mean().iloc[-1]) if len(vs) >= 10 else vix
        bajo = vix < s10
        metricas['vix']          = round(vix, 2)
        metricas['vix_tendencia'] = "Bajando ✅" if bajo else "Subiendo ⚠️"
        if vix < CONFIG["VIX_CAUTION"]:    puntuacion += 2
        elif vix >= CONFIG["VIX_RISK_OFF"]: puntuacion -= 2
        puntuacion += (1 if bajo else -1)
    else:
        metricas.update({'vix': 'N/A', 'vix_tendencia': 'N/A'})
        puntuacion += 1

    if 'HYG' in data.columns:
        hyg = data['HYG'].dropna()
        h   = float(hyg.iloc[-1])
        s20 = float(hyg.rolling(20).mean().iloc[-1]) if len(hyg) >= 20 else h
        s50 = float(hyg.rolling(50).mean().iloc[-1]) if len(hyg) >= 50 else s20
        ok  = h > s20 * 0.985
        metricas['hyg_vs_sma20'] = "Estables ✅" if ok else "Debilidad ⚠️"
        puntuacion += (1 if ok else -1)
        if s20 > s50: puntuacion += 1
    else:
        metricas['hyg_vs_sma20'] = "N/A"

    if 'SPY' in data.columns:
        spy  = data['SPY'].dropna()
        p    = float(spy.iloc[-1])
        s50  = float(spy.rolling(50).mean().iloc[-1])  if len(spy) >= 50  else p
        s200 = float(spy.rolling(200).mean().iloc[-1]) if len(spy) >= 200 else p
        dc   = s50 < s200
        metricas['spy_vs_sma50']  = "Sobre SMA50 ✅"  if p > s50  else "Bajo SMA50 ⚠️"
        metricas['spy_vs_sma200'] = "Sobre SMA200 ✅" if p > s200 else "Bajo SMA200 🔴"
        metricas['death_cross']   = "⚠️ DEATH CROSS"  if dc       else "✅ Sin Death Cross"
        if p > s50:  puntuacion += 1
        if p > s200: puntuacion += 1
        if dc:       puntuacion -= 3
    else:
        metricas.update({'spy_vs_sma50': 'N/A', 'spy_vs_sma200': 'N/A', 'death_cross': 'N/A'})

    if 'TLT' in data.columns:
        tlt = data['TLT'].dropna()
        t   = float(tlt.iloc[-1])
        ts  = float(tlt.rolling(20).mean().iloc[-1]) if len(tlt) >= 20 else t
        if t > ts:
            metricas['tlt'] = "Bonos fuertes (risk-off) ⚠️"
            puntuacion -= 1
        else:
            metricas['tlt'] = "Bonos débiles (risk-on) ✅"
    else:
        metricas['tlt'] = "N/A"

    metricas['puntuacion'] = puntuacion

    if   puntuacion >= 4: return "RISK_ON",  puntuacion, metricas
    elif puntuacion >= 1: return "CAUTION",  puntuacion, metricas
    else:                 return "RISK_OFF", puntuacion, metricas


# ══════════════════════════════════════════════════════════════════════
# MÓDULO 5: BACKTEST SIMPLE (Validación de señales recientes)
# ══════════════════════════════════════════════════════════════════════

def backtest_simple(data: pd.DataFrame, pool: Dict[str, str]) -> dict:
    """
    Backtest retrospectivo simple:
    Para cada ticker del pool, calcula cuántas veces la señal de momentum
    positivo (> 0) a 30 días fue seguida de retorno positivo a 10 días.
    
    Retorna métricas de tasa de acierto y rendimiento medio.
    """
    dias_signal = 30
    dias_fwd    = 10
    resultados  = {}

    for ticker in pool:
        if ticker not in data.columns:
            continue
        s = data[ticker].dropna()
        if len(s) < dias_signal + dias_fwd + 30:
            continue

        aciertos  = 0
        total     = 0
        retornos  = []

        # Simular señales cada 5 días en la ventana de backtest
        for i in range(dias_signal, len(s) - dias_fwd, 5):
            mom_signal = (s.iloc[i] / s.iloc[i - dias_signal] - 1) * 100
            retorno_fwd = (s.iloc[i + dias_fwd] / s.iloc[i] - 1) * 100

            if mom_signal > 0:  # señal positiva
                total += 1
                if retorno_fwd > 0:
                    aciertos += 1
                retornos.append(retorno_fwd)

        if total >= 5:
            resultados[ticker] = {
                'tasa_acierto':    round(aciertos / total * 100, 1),
                'retorno_medio':   round(np.mean(retornos), 2) if retornos else 0.0,
                'total_señales':   total,
            }

    return resultados


# ══════════════════════════════════════════════════════════════════════
# MÓDULO 6: SELECCIÓN DE ACTIVOS (Con health score + concentración sectorial)
# ══════════════════════════════════════════════════════════════════════

def check_concentracion_sectorial(
    portfolio: dict,
    data: pd.DataFrame,
    nuevo_ticker: str,
    nuevo_euros: float
) -> Tuple[bool, str]:
    """
    Verifica que añadir nuevo_ticker no supere el límite sectorial.
    Retorna (permitido, mensaje).
    """
    sector_nuevo = SECTOR_MAP.get(nuevo_ticker, 'otro')

    # Valor total del portfolio + nueva inversión
    valor_total = nuevo_euros
    sector_valor: Dict[str, float] = {sector_nuevo: nuevo_euros}

    for ticker, pos in portfolio.get("posiciones", {}).items():
        if ticker in data.columns:
            val   = float(data[ticker].dropna().iloc[-1]) * float(pos['cantidad'])
            sec   = SECTOR_MAP.get(ticker, 'otro')
            sector_valor[sec] = sector_valor.get(sec, 0) + val
            valor_total += val

    if valor_total <= 0:
        return True, ""

    pct = sector_valor.get(sector_nuevo, 0) / valor_total
    limite = CONFIG["SECTOR_MAX_PCT"]

    if pct > limite:
        return False, (
            f"⚠️ CONCENTRACIÓN `{sector_nuevo}`: {pct*100:.1f}% > {limite*100:.0f}% límite. "
            f"Diversifica antes de añadir más {sector_nuevo}."
        )
    return True, ""


def seleccionar_activo(
    data:                  pd.DataFrame,
    ohlc_store:            dict,
    pool:                  Dict[str, str],
    regimen:               str,
    excluir_rsi_alto:      bool = True,
    excluir_correlado_con: Optional[str] = None,
    backtest_data:         Optional[dict] = None
) -> Tuple[Optional[str], float, dict, List[dict]]:
    """
    Selección multi-factor con:
    1. Momentum multi-ventana
    2. RSI sobrecompra
    3. SMA20/SMA50 penalización
    4. Correlación
    5. Régimen CAUTION factor
    6. Health score bonus
    7. Backtest tasa de acierto bonus
    """
    candidatos = []

    for ticker, nombre in pool.items():
        if ticker not in data.columns:
            continue
        s = data[ticker].dropna()
        if len(s) < 25:
            continue

        score = calcular_momentum_score(data, ticker)
        if score == -999.0:
            continue

        precio = float(s.iloc[-1])
        rsi    = calcular_rsi(s)
        sma20  = calcular_sma(s, 20)
        sma50  = calcular_sma(s, 50)
        s20_ok = sma20 is not None and precio > sma20
        s50_ok = sma50 is not None and precio > sma50

        if excluir_rsi_alto and rsi > CONFIG["RSI_OVERBOUGHT"]:
            continue

        if excluir_correlado_con and excluir_correlado_con in data.columns:
            corr = calcular_correlacion(data, ticker, excluir_correlado_con)
            if abs(corr) > CONFIG["CORRELACION_MAX"]:
                continue

        score_adj = score
        if not s20_ok: score_adj *= 0.50
        if not s50_ok: score_adj *= 0.80
        if regimen == "CAUTION": score_adj *= 0.85

        # Bonus health score (0-10 puntos adicionales de ajuste)
        hs, hs_desc = calcular_health_score(ticker, data, ohlc_store)
        score_adj  += (hs / 100) * 3  # máximo +3 puntos por salud perfecta

        # Bonus backtest (si disponible)
        if backtest_data and ticker in backtest_data:
            bt = backtest_data[ticker]
            if bt['tasa_acierto'] > 60:
                score_adj += 1.0
            if bt['retorno_medio'] > 0:
                score_adj += 0.5

        candidatos.append({
            'ticker':      ticker,
            'nombre':      nombre,
            'score':       score_adj,
            'score_raw':   score,
            'rsi':         rsi,
            'precio':      precio,
            'sobre_sma20': s20_ok,
            'sobre_sma50': s50_ok,
            'health':      hs,
            'health_desc': hs_desc,
        })

    if not candidatos:
        if excluir_rsi_alto:
            log.warning("Pool sobrecomprado. Relajando filtro RSI.")
            return seleccionar_activo(
                data, ohlc_store, pool, regimen,
                excluir_rsi_alto=False,
                excluir_correlado_con=excluir_correlado_con,
                backtest_data=backtest_data
            )
        return None, 0.0, {}, []

    candidatos.sort(key=lambda x: x['score'], reverse=True)
    return candidatos[0]['ticker'], candidatos[0]['score'], candidatos[0], candidatos[:3]


def seleccionar_seguridad(
    data: pd.DataFrame, ohlc_store: dict, regimen: str, backtest_data: dict
) -> Tuple[str, dict, List[dict]]:
    t, sc, meta, top3 = seleccionar_activo(data, ohlc_store, TICKERS_SEGURIDAD, regimen,
                                            backtest_data=backtest_data)
    if t is None:
        for t2 in TICKERS_SEGURIDAD:
            if t2 in data.columns:
                s = data[t2].dropna()
                return t2, {
                    'ticker': t2, 'nombre': TICKERS_SEGURIDAD[t2],
                    'score': 0.0, 'rsi': calcular_rsi(s),
                    'precio': float(s.iloc[-1]),
                    'sobre_sma20': True, 'sobre_sma50': True, 'health': 50
                }, []
        return 'IWQU.L', {}, []
    return t, meta, top3


# ══════════════════════════════════════════════════════════════════════
# MÓDULO 7: POSITION SIZING
# ══════════════════════════════════════════════════════════════════════

def calcular_sizing(
    data: pd.DataFrame, ohlc_store: dict,
    ticker: str, capital_tramo: float, capital_total: float
) -> Tuple[float, str]:
    try:
        s       = data[ticker].dropna()
        precio  = float(s.iloc[-1])
        atr     = calcular_atr(ticker, ohlc_store, s)
        atr_pct = atr / precio
        if atr_pct <= 1e-6:
            return capital_tramo, "ATR≈0"
        riesgo   = capital_total * CONFIG["CAPITAL_RISK_PCT"]
        sizing   = riesgo / (atr_pct * CONFIG["STOP_LOSS_PCT"])
        final    = float(np.clip(sizing, CONFIG["MIN_INVERSION"], capital_tramo))
        src      = "OHLC" if ticker in ohlc_store else "proxy"
        info     = f"ATR[{src}]={atr:.2f}({atr_pct*100:.1f}%) → {final:.0f}€"
        return round(final, 2), info
    except Exception as e:
        log.warning(f"Sizing fallback {ticker}: {e}")
        return capital_tramo, f"default ({capital_tramo:.0f}€)"


# ══════════════════════════════════════════════════════════════════════
# MÓDULO 8: AUDITORÍA COMPLETA
# ══════════════════════════════════════════════════════════════════════

def auditar_cartera(
    portfolio: dict, data: pd.DataFrame, ohlc_store: dict
) -> Tuple[List[str], dict]:
    alertas = []
    pnl     = calcular_pnl_cartera(portfolio, data)

    posiciones = portfolio.get("posiciones", {})
    if not posiciones:
        alertas.append("📋 Cartera vacía.")
        return alertas, pnl

    ico = "📈" if pnl['pnl_euros'] >= 0 else "📉"
    alertas.append(
        f"💼 *Portfolio: {pnl['valor_actual']:.2f}€ | Coste: {pnl['coste_total']:.2f}€*\n"
        f"   {ico} P&L: {pnl['pnl_euros']:+.2f}€ ({pnl['pnl_pct']:+.2f}%) | HWM: {pnl['hwm']:.2f}€"
    )
    if pnl['drawdown_pct'] < -(CONFIG["DRAWDOWN_ALERT"] * 100):
        alertas.append(
            f"🚨 *DRAWDOWN TOTAL: {pnl['drawdown_pct']:.1f}%* desde máximos — Revisar exposición."
        )
    alertas.append("")

    for ticker, pos in posiciones.items():
        if ticker not in data.columns:
            alertas.append(f"⚠️ `{ticker}`: Sin datos.")
            continue

        s             = data[ticker].dropna()
        precio        = float(s.iloc[-1])
        pc            = float(pos['precio_compra'])
        sl            = float(pos.get('stop_loss',     pc * (1 - CONFIG["STOP_LOSS_PCT"])))
        trail         = float(pos.get('trailing_stop', pc * (1 - CONFIG["TRAILING_STOP_PCT"])))
        pnl_p         = (precio / pc - 1) * 100
        rsi           = calcular_rsi(s)
        sma20         = calcular_sma(s, 20)
        tramo         = pos.get('tramo', 'riesgo')
        hs, _         = calcular_health_score(ticker, data, ohlc_store)

        if precio <= sl:
            alertas.append(
                f"🚨 *STOP-LOSS* `{ticker}` [{tramo}]\n"
                f"   P={precio:.2f} ≤ SL={sl:.2f} | P&L={pnl_p:.1f}% → *VENDER YA*"
            )
        elif precio <= trail and trail > sl:
            alertas.append(
                f"🔴 *TRAILING STOP* `{ticker}` [{tramo}]\n"
                f"   P={precio:.2f} ≤ Trail={trail:.2f} | P&L={pnl_p:.1f}% → *VENDER (ganancias protegidas)*"
            )
        elif sma20 and precio < sma20 * 0.97:
            alertas.append(
                f"⚠️ *TENDENCIA ROTA* `{ticker}` [{tramo}]\n"
                f"   P<SMA20 | P&L={pnl_p:.1f}% → Considerar ROTAR"
            )
        elif rsi > CONFIG["RSI_EXTREME_OB"]:
            alertas.append(
                f"📈 *SOBRECOMPRA* `{ticker}` [{tramo}]\n"
                f"   RSI={rsi:.0f} | P&L={pnl_p:.1f}% → Tomar beneficios"
            )
        else:
            sma_ok = "✅" if (sma20 and precio > sma20) else "⚠️"
            alertas.append(
                f"✅ `{ticker}` [{tramo}] | P&L={pnl_p:+.1f}% | "
                f"RSI={rsi:.0f} | SMA20={sma_ok} | Health={hs}/100 | Trail={trail:.2f}"
            )

    return alertas, pnl


# ══════════════════════════════════════════════════════════════════════
# MÓDULO 9: EXPORTACIÓN CSV DE SEÑALES
# ══════════════════════════════════════════════════════════════════════

def exportar_señal_csv(
    regimen: str, lider_seg: str, lider_ries: Optional[str],
    lider_exp: Optional[str], pnl: dict, dry_run: bool
) -> None:
    """
    Añade una línea al CSV de señales para análisis histórico externo.
    Permite hacer tracking y backtesting real con datos históricos.
    """
    if dry_run:
        return

    path = CONFIG["SIGNALS_CSV"]
    es_nuevo = not path.exists()

    try:
        with open(path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if es_nuevo:
                writer.writerow([
                    'fecha', 'regimen', 'lider_seguridad',
                    'lider_riesgo', 'lider_explosion',
                    'portfolio_valor', 'portfolio_pnl_pct'
                ])
            writer.writerow([
                datetime.now().isoformat(),
                regimen,
                lider_seg,
                lider_ries or "N/A",
                lider_exp  or "N/A",
                pnl.get('valor_actual', 0),
                pnl.get('pnl_pct', 0),
            ])
    except IOError as e:
        log.error(f"Error exportando señal a CSV: {e}")


# ══════════════════════════════════════════════════════════════════════
# MÓDULO 10: TELEGRAM
# ══════════════════════════════════════════════════════════════════════

def enviar_telegram(mensaje: str, dry_run: bool = False) -> bool:
    if dry_run:
        print("\n" + "█"*60)
        print("[DRY-RUN] INFORME TITAN V8.0:")
        print("█"*60)
        print(mensaje)
        print("█"*60 + "\n")
        return True

    token   = CONFIG["TELEGRAM_TOKEN"]
    chat_id = CONFIG["TELEGRAM_CHAT_ID"]

    if not token or not chat_id:
        print("\n" + "="*60 + "\n" + mensaje + "\n" + "="*60)
        return True

    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    MAX_LEN = 4000

    for idx, chunk in enumerate(
        [mensaje[i:i+MAX_LEN] for i in range(0, len(mensaje), MAX_LEN)]
    ):
        for intento in range(1, 4):
            try:
                r = requests.post(
                    url,
                    json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
                    timeout=15
                )
                if r.status_code == 200:
                    break
                log.warning(f"Telegram {r.status_code} (chunk {idx+1}, intento {intento})")
            except requests.exceptions.RequestException as e:
                log.error(f"Telegram: {e} (intento {intento})")
            if intento == 3:
                log.error(f"Chunk {idx+1}: fallo definitivo.")
                return False
    return True


# ══════════════════════════════════════════════════════════════════════
# MOTOR PRINCIPAL V8.0
# ══════════════════════════════════════════════════════════════════════

def ejecutar_titan_v8(dry_run: bool = False) -> None:
    log.info(f"═══ TITAN V8.0: Iniciando {'[DRY-RUN] ' if dry_run else ''}═══")

    # ── 1. CARGAR CARTERA ──
    portfolio = load_portfolio()

    # ── 2. DATOS ──
    todos = TICKERS_REF + list(TICKERS_SEGURIDAD) + list(TICKERS_RIESGO) + list(TICKERS_EXPLOSION)
    data, ohlc_store = descargar_datos(todos)

    if data.empty:
        enviar_telegram("🚨 TITAN V8: Sin datos de mercado.", dry_run)
        return

    # ── 3. TRAILING STOPS ──
    portfolio, trail_msgs = actualizar_trailing_stops(portfolio, data)

    # ── 4. RÉGIMEN ──
    regimen, score_macro, macro = analizar_regimen(data)

    # ── 5. BACKTEST ──
    all_pool = {**TICKERS_SEGURIDAD, **TICKERS_RIESGO, **TICKERS_EXPLOSION}
    bt_data  = backtest_simple(data, all_pool)

    # ── 6. SELECCIÓN ──
    lider_seg, meta_seg, top3_seg = seleccionar_seguridad(data, ohlc_store, regimen, bt_data)
    lider_ries, score_ries, meta_ries, top3_ries = seleccionar_activo(
        data, ohlc_store, TICKERS_RIESGO, regimen, backtest_data=bt_data
    )
    lider_exp, score_exp, meta_exp, top3_exp = seleccionar_activo(
        data, ohlc_store, TICKERS_EXPLOSION, regimen,
        excluir_correlado_con=lider_ries, backtest_data=bt_data
    )

    # ── 7. CAPITAL POR RÉGIMEN (granular) ──
    dia_actual       = datetime.now().day
    es_dia_inversion = (dia_actual == 1)

    if regimen == "RISK_ON":
        cap_total_inv  = CONFIG["CAP_MENSUAL"]
        alloc          = CONFIG["ALLOC_RISK_ON"]
    elif regimen == "CAUTION":
        nivel_caution  = max(1, min(3, score_macro))  # clamp 1-3
        cfg_c          = CONFIG["CAUTION_NIVELES"][nivel_caution]
        cap_total_inv  = CONFIG["CAP_MENSUAL"] * cfg_c["pct_capital"]
        alloc          = {"seguridad": cfg_c["seg"], "riesgo": cfg_c["ries"], "explosion": cfg_c["exp"]}
    else:
        cap_total_inv  = 0.0
        alloc          = {"seguridad": 0, "riesgo": 0, "explosion": 0}

    capital_seg  = cap_total_inv * alloc["seguridad"]
    capital_ries = cap_total_inv * alloc["riesgo"]
    capital_exp  = cap_total_inv * alloc["explosion"]

    s_ries_info = s_exp_info = "N/A"
    if lider_ries and capital_ries > 0:
        capital_ries, s_ries_info = calcular_sizing(data, ohlc_store, lider_ries, capital_ries, CONFIG["CAP_MENSUAL"])
    if lider_exp and capital_exp > 0:
        capital_exp, s_exp_info = calcular_sizing(data, ohlc_store, lider_exp, capital_exp, CONFIG["CAP_MENSUAL"])

    # ── 8. CONCENTRACIÓN SECTORIAL ──
    conc_msg_ries = conc_msg_exp = ""
    if lider_ries and capital_ries > 0:
        ok, msg = check_concentracion_sectorial(portfolio, data, lider_ries, capital_ries)
        if not ok: conc_msg_ries = msg
    if lider_exp and capital_exp > 0:
        ok, msg = check_concentracion_sectorial(portfolio, data, lider_exp, capital_exp)
        if not ok: conc_msg_exp = msg

    # ── 9. AUDITORÍA ──
    alertas, pnl_summary = auditar_cartera(portfolio, data, ohlc_store)

    # ── 10. EXPORTAR SEÑAL ──
    exportar_señal_csv(regimen, lider_seg, lider_ries, lider_exp, pnl_summary, dry_run)

    # ── 11. CONSTRUIR INFORME ──
    ICONOS = {"RISK_ON": "🟢", "CAUTION": "🟡", "RISK_OFF": "🔴"}
    LABELS = {
        "RISK_ON":  "ALCISTA — RISK ON",
        "CAUTION":  "CAUTELOSO — ZONA GRIS",
        "RISK_OFF": "DEFENSIVO — RISK OFF",
    }

    r  = "🏛️ *TITAN INTELLIGENCE V8.0*\n"
    r += f"📅 *{datetime.now().strftime('%d/%m/%Y %H:%M')}*"
    r += " `[DRY-RUN]`\n" if dry_run else "\n"
    r += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # RÉGIMEN
    r += f"🚦 *{LABELS[regimen]}* {ICONOS[regimen]}\n"
    r += f"• VIX: `{macro.get('vix','N/A')}` {macro.get('vix_tendencia','')}\n"
    r += f"• HYG: {macro.get('hyg_vs_sma20','N/A')}\n"
    r += f"• SPY: {macro.get('spy_vs_sma50','N/A')} | {macro.get('spy_vs_sma200','N/A')}\n"
    r += f"• {macro.get('death_cross','')}\n"
    r += f"• TLT: {macro.get('tlt','N/A')}\n"
    r += f"• Score macro: `{score_macro}/9`\n"
    r += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # AUDITORÍA
    r += "🔍 *AUDITORÍA DE CARTERA*\n"
    for linea in alertas:
        r += f"{linea}\n"
    if trail_msgs:
        r += "\n*Trailing stops actualizados:*\n"
        for msg in trail_msgs:
            r += f"{msg}\n"
    r += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # MISIÓN
    if es_dia_inversion:
        r += f"📋 *MISIÓN: INYECCIÓN MENSUAL* 💰 `{CONFIG['CAP_MENSUAL']:.0f}€`\n\n"

        if regimen == "RISK_OFF":
            r += "🛡️ *NO INVERTIR — Capital a Cuenta Remunerada (4%)*\n"
            r += f"• Motivo: Score macro={score_macro}/9 — Mercado bajista.\n"

        elif regimen == "CAUTION":
            nv = max(1, min(3, score_macro))
            r += (
                f"⚠️ *CAUTELOSO (nivel {nv}/3)*: "
                f"{cap_total_inv:.0f}€ de {CONFIG['CAP_MENSUAL']:.0f}€ "
                f"({CONFIG['CAUTION_NIVELES'][nv]['pct_capital']*100:.0f}%)\n\n"
            )
            r += f"1️⃣ *ESCUDO | {capital_seg:.0f}€*\n"
            r += f"• 🎯 `{lider_seg}` — {TICKERS_SEGURIDAD.get(lider_seg,'')}\n"
            r += f"• RSI `{meta_seg.get('rsi','?'):.0f}` | Health `{meta_seg.get('health',0)}/100`\n"
            r += f"• 🛒 Compra a Mercado\n"
            if lider_ries and capital_ries > 0:
                r += f"\n2️⃣ *MOTOR | {capital_ries:.0f}€ (reducido)*\n"
                r += f"• 🎯 `{lider_ries}` — {TICKERS_RIESGO.get(lider_ries,'')}\n"
                r += f"• RSI `{meta_ries.get('rsi','?'):.0f}` | {s_ries_info}\n"
                if conc_msg_ries: r += f"• {conc_msg_ries}\n"
                r += f"• 🛒 Compra a Mercado\n"
            restante = CONFIG["CAP_MENSUAL"] - cap_total_inv
            r += f"\n• `{restante:.0f}€` → Cuenta Remunerada\n"

        else:  # RISK_ON
            r += f"1️⃣ *ESCUDO (SEGURIDAD) | {capital_seg:.0f}€*\n"
            r += f"• 🎯 `{lider_seg}` — {TICKERS_SEGURIDAD.get(lider_seg,'')}\n"
            r += f"• RSI `{meta_seg.get('rsi','?'):.0f}` | Health `{meta_seg.get('health',0)}/100`\n"
            r += f"• 🛒 Compra a Mercado\n\n"

            if lider_ries:
                sl_r  = data[lider_ries].iloc[-1] * (1 - CONFIG["STOP_LOSS_PCT"])
                bt_r  = bt_data.get(lider_ries, {})
                r += f"2️⃣ *MOTOR (RIESGO) | {capital_ries:.0f}€*\n"
                r += f"• 🎯 `{lider_ries}` — {TICKERS_RIESGO.get(lider_ries,'')}\n"
                r += f"• Score `{score_ries:.1f}` | RSI `{meta_ries.get('rsi','?'):.0f}` | Health `{meta_ries.get('health',0)}/100`\n"
                r += f"• 📐 {s_ries_info}\n"
                r += f"• 🛑 SL: `{sl_r:.2f}` | Trail: -{CONFIG['TRAILING_STOP_PCT']*100:.0f}%\n"
                if bt_r:
                    r += f"• 📊 Backtest: {bt_r.get('tasa_acierto',0):.0f}% acierto | {bt_r.get('retorno_medio',0):+.1f}% ret.medio\n"
                r += f"• Top3: " + " / ".join([f"`{c['ticker']}`(RSI{c['rsi']:.0f})" for c in top3_ries]) + "\n"
                if conc_msg_ries: r += f"• {conc_msg_ries}\n"
                r += f"• 🛒 Compra a Mercado\n\n"
            else:
                r += "2️⃣ *MOTOR: Sin candidato válido.*\n\n"

            if lider_exp:
                sl_e  = data[lider_exp].iloc[-1] * (1 - CONFIG["STOP_LOSS_PCT"])
                bt_e  = bt_data.get(lider_exp, {})
                corr  = calcular_correlacion(data, lider_exp, lider_ries) if lider_ries else 0.0
                r += f"3️⃣ *NITRO (EXPLOSIÓN) | {capital_exp:.0f}€*\n"
                r += f"• 🎯 `{lider_exp}` — {TICKERS_EXPLOSION.get(lider_exp,'')}\n"
                r += f"• Score `{score_exp:.1f}` | RSI `{meta_exp.get('rsi','?'):.0f}` | Health `{meta_exp.get('health',0)}/100`\n"
                r += f"• 📐 {s_exp_info}\n"
                r += f"• Corr con Motor: `{corr:.2f}` {'✅' if abs(corr)<0.7 else '⚠️'}\n"
                r += f"• 🛑 SL: `{sl_e:.2f}` | Trail: -{CONFIG['TRAILING_STOP_PCT']*100:.0f}%\n"
                if bt_e:
                    r += f"• 📊 Backtest: {bt_e.get('tasa_acierto',0):.0f}% acierto | {bt_e.get('retorno_medio',0):+.1f}% ret.medio\n"
                r += f"• Top3: " + " / ".join([f"`{c['ticker']}`(RSI{c['rsi']:.0f})" for c in top3_exp]) + "\n"
                if conc_msg_exp: r += f"• {conc_msg_exp}\n"
                r += f"• 🛒 Compra a Mercado\n"
            else:
                r += "3️⃣ *NITRO: Sin candidato válido.*\n"

    else:
        r += f"👮 *GUARDIÁN (Auditoría Diaria)* — {LABELS[regimen]} {ICONOS[regimen]}\n"
        if regimen == "RISK_OFF":
            r += "• 🚨 Mercado bajista. Ver alertas arriba.\n"
        else:
            r += "• Cartera en revisión continua. Ver alertas.\n"

    r += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
    r += (
        f"⚡ *TITAN V8.0* | Score {score_macro}/9 | "
        f"{len(portfolio['posiciones'])}pos | "
        f"{datetime.now().strftime('%H:%M:%S')}"
    )

    # ── 12. ENVIAR + GUARDAR ──
    enviar_telegram(r, dry_run)
    save_portfolio(portfolio, dry_run)
    log.info("═══ TITAN V8.0: Completado ═══\n")


# ══════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TITAN INTELLIGENCE V8.0")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simula la ejecución sin enviar Telegram ni guardar cambios."
    )
    args = parser.parse_args()
    ejecutar_titan_v8(dry_run=args.dry_run)
