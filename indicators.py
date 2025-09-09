import logging
from typing import List, Tuple, Optional
import numpy as np
import pandas as pd


def indicatorFactory(df:pd.DataFrame) -> pd.DataFrame:
    # Chart 1
    df1 = df.copy()
    df1 = df1.tail(520).copy()
    df1.reset_index(inplace=True, drop=True)
    df1Vwap = VWAP(df1)
    df1Ema = EMA(df1)
    df1Bb = BollingerBands(df1)
    df1Adx = ADXDMI(df1)
    #df1Rsi = RSI(df1)

    #print(df1)
    #print(df1Vwap)
    #print(df1Ema)
    #print(df1Bb)
    #print(df1Adx)
    #print(df1Rsi)

    df1['VWAP'] = df1Vwap['VWAP']
    df1['EMA 10'] = df1Ema['EMA 10']
    df1['SMA 20'] = df1Bb['SMA 20']
    df1['bb_pc'] = df1Bb['bb_pc']
    df1['bb_upper1'] = df1Bb['bb_upper1']
    df1['bb_upper2'] = df1Bb['bb_upper2']
    df1['bb_lower1'] = df1Bb['bb_lower1']
    df1['bb_lower2'] = df1Bb['bb_lower2']
    df1['ADX'] = df1Adx['ADX']
    df1['DMIP'] = df1Adx['DMIP']
    df1['DMIM'] = df1Adx['DMIM']

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


def getSupportResistanceLevels(priceData:pd.DataFrame, sensitivity:int=5, threshold:float=0.01, maxLevels:int=10, decay:float=0.005) -> Optional[List[float]]:
    '''
    Detects the most important support/resistance levels using local highs/lows,
    with recency weighting and clustering.

    Args:
        priceData (pd.DataFrame): Must have 'high' and 'low' columns.
        sensitivity (int): Local extremum window size.
        threshold (float): Max relative % difference to cluster levels.
        maxLevels (int): Max number of strong levels to return (excl. extremes).
        decay (float): Exponential decay for recency weight (higher = more recent bias).

    Returns:
        list: Sorted list of important support/resistance price levels.
    '''
    try:
        highs = priceData['high'].values
        lows = priceData['low'].values
        levels = []
        length = len(priceData)

        for i in range(sensitivity, length - sensitivity):
            isLocalHigh = all(highs[i] > highs[i - j] for j in range(1, sensitivity + 1)) and \
                        all(highs[i] > highs[i + j] for j in range(1, sensitivity + 1))
            isLocalLow = all(lows[i] < lows[i - j] for j in range(1, sensitivity + 1)) and \
                        all(lows[i] < lows[i + j] for j in range(1, sensitivity + 1))

            if isLocalHigh or isLocalLow:
                level = highs[i] if isLocalHigh else lows[i]
                recencyWeight = np.exp(-decay * (length - i))  # Newer = higher weight
                levels.append({'price': level, 'weight': recencyWeight})

        # Cluster similar levels
        clusters = []
        for lvl in levels:
            matched = False
            for cluster in clusters:
                if abs(cluster['price'] - lvl['price']) / lvl['price'] < threshold:
                    # Update cluster with new level
                    cluster['weightedSum'] += lvl['price'] * lvl['weight']
                    cluster['weightTotal'] += lvl['weight']
                    cluster['score'] += lvl['weight']
                    cluster['price'] = cluster['weightedSum'] / cluster['weightTotal']
                    matched = True
                    break
            if not matched:
                clusters.append({
                    'price': lvl['price'],
                    'weightedSum': lvl['price'] * lvl['weight'],
                    'weightTotal': lvl['weight'],
                    'score': lvl['weight']
                })

        # Sort by score (importance) and select top levels
        clusters.sort(key=lambda x: x['score'], reverse=True)
        topLevels = [round(c['price'], 2) for c in clusters[:maxLevels]]

        # Always include all-time high/low
        allTimeHigh = round(priceData['high'].max(), 2)
        allTimeLow = round(priceData['low'].min(), 2)
        if allTimeHigh not in topLevels:
            topLevels.append(allTimeHigh)
        if allTimeLow not in topLevels:
            topLevels.append(allTimeLow)

        return sorted(topLevels)
    except:
        logging.exception('Error while calculating support and resistance levels!')
    return None


def VWAP(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add intraday VWAP (resets daily) as a new column 'VWAP'.
    """
    df = df.copy()
    #df['datetime'] = pd.to_datetime(df['time'])
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
