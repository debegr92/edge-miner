import logging
from typing import List, Tuple, Optional
import numpy as np
import pandas as pd
from ta.trend import PSARIndicator, SMAIndicator


def isIntraday(df:pd.DataFrame) -> True:
    """
    Detect whether a pandas DataFrame with a 'time' column (datetime)
    represents a daily financial series or an intraday one, based on
    the first two rows.

    Args:
        df (pd.DataFrame): Pandas DataFrame object with **time** column (datetime).

    Returns:
        True: True if intraday series
    """
    if 'time' not in df.columns:
        raise ValueError("DataFrame must contain a 'time' column")
    if len(df) < 2:
        raise ValueError("DataFrame must have at least two rows to detect frequency")

    # Ensure sorted by time
    df_sorted = df.sort_values('time').reset_index(drop=True)
    
    delta = df_sorted.loc[1, 'time'] - df_sorted.loc[0, 'time']

    if delta >= pd.Timedelta(days=1):
        return False
    return True


def indicatorFactory(df:pd.DataFrame) -> pd.DataFrame:
    # Chart 1
    df1 = df.copy()
    df1.reset_index(inplace=True, drop=True)

    # Only calculate VWAP on intraday charts
    if isIntraday(df1):
        df1Vwap = VWAP(df1)
        df1['VWAP'] = df1Vwap['VWAP']

    df1Ema = EMA(df1, period=5)
    df1Bb = BollingerBands(df1, period=10)
    df1Adx = ADXDMI(df1)
    df1Rsi = RSI(df1)
    df1Atr = AverageTrueRange(df1)
    
    df1['EMA'] = df1Ema['EMA 5']
    df1['SMA'] = df1Bb['SMA 10']
    df1['BB_PC'] = df1Bb['bb_pc']
    df1['BB_UPPER1'] = df1Bb['bb_upper1']
    df1['BB_UPPER2'] = df1Bb['bb_upper2']
    df1['BB_LOWER1'] = df1Bb['bb_lower1']
    df1['BB_LOWER2'] = df1Bb['bb_lower2']
    df1['ADX'] = df1Adx['ADX']
    df1['DMIP'] = df1Adx['DMIP']
    df1['DMIM'] = df1Adx['DMIM']
    df1['RSI'] = df1Rsi['RSI 14']
    df1['ATR'] = df1Atr['ATR']

    # Volume SMA
    volSmaInd = SMAIndicator(df1['volume'], 10, True)
    df1['VOL_SMA'] = volSmaInd.sma_indicator()

    # Keltner Channel
    df1['KC_UPPER'] = df1['SMA'] + 2.0 * df1['ATR']
    df1['KC_LOWER'] = df1['SMA'] - 2.0 * df1['ATR']

    # Parabolic Stop and Reverse
    psarInd = PSARIndicator(df1['high'], df1['low'], df1['close'], fillna=True)
    df1['PSAR'] = psarInd.psar()

    df1.dropna(inplace=True)
    df1.reset_index(inplace=True, drop=True)

    return df1


def SMA(df:pd.DataFrame, period:int=20) -> pd.DataFrame:
    logging.debug(f'Calculate SMA({period})')
    return pd.DataFrame({
        'time': df['time'],
        f'SMA {period}': df['close'].rolling(window=period).mean()
    }).dropna()


def EMA(df:pd.DataFrame, period:int=10) -> pd.DataFrame:
    logging.debug(f'Calculate EMA({period})')
    return pd.DataFrame({
        'time': df['time'],
        f'EMA {period}': df['close'].ewm(span=period, adjust=False).mean()
    }).dropna()


def BollingerBands(dfIn:pd.DataFrame, period:int=20, std:list=[2,3], source:str='close') -> pd.DataFrame:
    try:
        logging.debug(f'Calculate BollingerBands({period}, {std})')
        df = dfIn.copy()
        N = int(period)
        if len(df) > N:
            # Calc standard deviation
            df['std'] = df[source].rolling(N).std(ddof=0).fillna(0)
            df[f'SMA {period}'] = df[source].rolling(N).mean().fillna(df[source])

            # Calc upper/lower bands for all
            for idx, stdev in enumerate(std):
                df[f'bb_upper{idx+1}'] = df[f'SMA {period}'] + stdev * df['std']
                df[f'bb_lower{idx+1}'] = df[f'SMA {period}'] - stdev * df['std']

            # Calculate symmetric %B
            df['bb_pc'] = (df[source].astype(float) - df[f'SMA {period}']) / df['std']
            df['bb_pc'] = df['bb_pc'].fillna(0)

            # Build return object
            retDf = pd.DataFrame({
                'time': df['time'],
                f'SMA {period}': df[f'SMA {period}'],
                'bb_pc': df['bb_pc'],
            })
            for idx, stdev in enumerate(std):
                retDf[f'bb_upper{idx+1}'] = df[f'bb_upper{idx+1}']
                retDf[f'bb_lower{idx+1}'] = df[f'bb_lower{idx+1}']
            return retDf
        else:
            pd.DataFrame({'time': df['time']})
    except:
        logging.exception('Error while calculating indicator "BollingerBands"')
    return pd.DataFrame({'time': df['time']})


def RSI(dfIn:pd.DataFrame, period:int=14, source:str='close') -> pd.DataFrame:
    try:
        df = dfIn.copy()
        N = int(period)
        if len(df) > N:
            df['change'] = df[source].diff()
            df['gain'] = df.change.mask(df.change < 0, 0.0)
            df['loss'] = -df.change.mask(df.change > 0, -0.0)

            def rma(x, n):
                a = np.full_like(x, np.nan)
                a[n] = x[1:n+1].mean()
                for i in range(n+1, len(x)):
                    a[i] = (a[i-1] * (n - 1) + x[i]) / n
                return a

            df['avg_gain'] = rma(df.gain.to_numpy(), N)
            df['avg_loss'] = rma(df.loss.to_numpy(), N)

            df['rs'] = df.avg_gain / df.avg_loss
            df[f'RSI {period}'] = 100 - (100 / (1 + df.rs))
            #df[f'RSI {period}'] = df[f'RSI {period}'].shift(period-1)
        else:
            df[f'RSI {period}'] = 50
        return pd.DataFrame({
            'time': df['time'],
            f'RSI {period}': df[f'RSI {period}'],
        }).fillna(50)

    except:
        logging.exception('Error while calculating indicator "RSI"')
    return pd.DataFrame({'time': df['time']})


def ADXDMI(dfIn:pd.DataFrame, period:int=14) -> pd.DataFrame:
    try:
        df = dfIn.copy()
        alpha = float(1/period)
        # True Range
        df['H-L'] = df['high'] - df['low']
        df['H-C'] = np.abs(df['high'] - df['close'].shift(1))
        df['L-C'] = np.abs(df['low'] - df['close'].shift(1))
        df['TR'] = df[['H-L', 'H-C', 'L-C']].max(axis=1)
        del df['H-L'], df['H-C'], df['L-C']
        # Average True Range
        df['ATR'] = df['TR'].ewm(alpha=alpha, adjust=False).mean()
        # +-DX
        df['H-pH'] = df['high'] - df['high'].shift(1)
        df['pL-L'] = df['low'].shift(1) - df['low']
        df['+DX'] = np.where(
            (df['H-pH'] > df['pL-L']) & (df['H-pH']>0),
            df['H-pH'],
            0.0
        )
        df['-DX'] = np.where(
            (df['H-pH'] < df['pL-L']) & (df['pL-L']>0),
            df['pL-L'],
            0.0
        )
        # +- DMI
        df['S+DM'] = df['+DX'].ewm(alpha=alpha, adjust=False).mean()
        df['S-DM'] = df['-DX'].ewm(alpha=alpha, adjust=False).mean()
        df['DMIP'] = (df['S+DM']/df['ATR'])*100
        df['DMIM'] = (df['S-DM']/df['ATR'])*100
        # ADX
        df['DX'] = (np.abs(df['DMIP'] - df['DMIM'])/(df['DMIP'] + df['DMIM']))*100
        df['ADX'] = df['DX'].ewm(alpha=alpha, adjust=False).mean()

        return pd.DataFrame({
            'time': df['time'],
            'ADX': df['ADX'],
            'DMIP': df['DMIP'],
            'DMIM': df['DMIM']
        }).fillna(100)
    except:
        logging.exception('Error while calculating indicator "ADXDMI"')
    return pd.DataFrame({'time': df['time']})


def VWAP(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add intraday VWAP (resets daily) as a new column 'VWAP'.
    """
    df = df.copy()
    df.set_index('time', inplace=True, drop=False)

    typical_price = (df['high'] + df['low'] + df['close']) / 3
    date = df.index.date
    cum_vol = df.groupby(date)['volume'].cumsum()
    cum_vol_tp = (typical_price * df['volume']).groupby(date).cumsum()
    df['VWAP'] = cum_vol_tp / cum_vol
    df.reset_index(drop=True, inplace=True)
    return pd.DataFrame({
        'time': df['time'],
        'VWAP': df['VWAP']
    })


def AverageTrueRange(dfIn:pd.DataFrame, period:int=20) -> float:
    try:
        df = dfIn.copy()
        # Calculate ranges
        df['r1'] = df['high']-df['low']
        df['r2'] = df['high']-df['close'].shift(1)
        df['r3'] = df['low']-df['close'].shift(1)
        # Assing maximum of different ranges
        df['MAXTR'] = df[['r1', 'r2', 'r3']].max(axis=1)
        # Average over N
        df['ATR'] = df['MAXTR'].rolling(window=period).mean()
        return pd.DataFrame({
                'time': df['time'],
                f'ATR': df['ATR']
            })
    except:
        logging.exception('Error while calculating indicator "AverageTrueRange"')
    return pd.DataFrame({'time': df['time']})


def getCandleType(open:float, high:float, low:float, close:float) -> int:
    try:
        ctype = 0
        step = (high-low)/5
        # Open
        if open <= low + step:
            ctype = 10
        elif open <= low + 2*step and open > low + step:
            ctype = 20
        elif open <= low + 3*step and open > low + 2*step:
            ctype = 30
        elif open <= low + 4*step and open > low + 3*step:
            ctype = 40
        elif open <= high and open > low + 4*step:
            ctype = 50
        # Close
        if close <= low + step:
            ctype = ctype+1
        elif close < low + 2*step and close > low + step:
            ctype = ctype+2
        elif close < low + 3*step and close >= low + 2*step:
            ctype = ctype+3
        elif close < low + 4*step and close >= low + 3*step:
            ctype = ctype+4
        elif close <= low + 5*step and close >= low + 4*step:
            ctype = ctype+5
        return ctype
    except:
        logging.exception('Error while calculating "CandleType"')
    return 0
