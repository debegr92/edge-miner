# General Imports
import json
import asyncio
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging
import threading
from typing import Dict, List, Tuple, Optional
# TWS API
from ibapi.client import EClient
from ibapi.common import BarData
from ibapi.contract import Contract, ContractDetails
from ibapi.wrapper import EWrapper

class ObjectType(Enum):
    Message = 0
    HistoricalData = 1
    Positions = 2
    Executions = 3
    Orders = 4
    RealtimeBar = 5
    Price = 6

@dataclass
class QueueObject:
    type: ObjectType
    symbol: str = None
    timeframe: str = None
    stringData: str = None
    listData: list = field(default_factory=lambda: [])


class IBClient(EWrapper, EClient):

    dataQueue:asyncio.Queue

    def __init__(self, dataQueue:asyncio.Queue, loop, host:str='localhost', port:int=7497, clientId:int=4243):
        EClient.__init__(self, self)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel('INFO')

        # Stop logger from spamming INFO log if not DEBUG level
        utilsLogger = logging.getLogger('ibapi.utils')
        utilsLogger.setLevel(logging.WARNING)

        self.dataQueue:asyncio.Queue = dataQueue
        self.loop = loop

        self.host = host
        self.port = port
        self.clientId = clientId

        # Variables to save runtime data
        self.tickerId:int = 0
        self.requestId:int = 0
        self.symbolTimeframeHistTickerIds:Dict[Tuple[str, str], int] = {}	# symbol,timeframe -> tickerId
        self.histTickerIdSymbolTimeframe:Dict[int, Tuple[str, str]] = {}	# tickerId -> symbol,timeframe
        self.symbolLiveTickerIds:Dict[str, int] = {}	# symbol -> tickerId
        self.symbolCandleTickerIds:Dict[str, int] = {}	# symbol -> tickerId
        self.symbolCandleData:Dict[Tuple[str, str], List] = {}		# symbol -> list
        self.cDetails:Dict[str, ContractDetails] = {}	# symbol -> ContractDetails


    def start(self) -> None:
        try:
            self.connect(self.host, self.port, self.clientId)
            # Start IBAPI mainloop
            threading.Thread(target=self.run, daemon=True).start()
        except:
            self.logger.exception(f'Error while connect to TWS/Gateway')


    @staticmethod
    def convertBar(bar:BarData) -> dict:
        t = datetime.fromtimestamp(int(bar.date))
        data = {
            'time': t,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': int(bar.volume)
        }
        return data


    @staticmethod
    def createStockContract(symbol):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = 'STK'
        contract.exchange = 'SMART'
        contract.currency = 'USD'
        return contract


    def sendMessage(self, msg:str) -> None:
        try:
            asyncio.run_coroutine_threadsafe(
                self.dataQueue.put(QueueObject(ObjectType.Message, stringData=msg)),
                self.loop
            )
        except:
            self.logger.exception('sendMessage: EXCEPTION!')


    def getNextTickerId(self) -> int:
        self.tickerId = self.tickerId+1
        return self.tickerId


    def getNextRequestId(self) -> int:
        self.requestId = self.requestId+1
        return self.requestId


    def getSymbolForTickerId(self, id:int, live=False, bar=False) -> Optional[str]:
        try:
            if not live:
                # key: str,str -> symbol, timeframe
                for key, tid in self.symbolTimeframeHistTickerIds.items():
                    if tid == id:
                        return key[0]
            else:
                if not bar:
                    for symbol, tid in self.symbolLiveTickerIds.items():
                        if tid == id:
                            return symbol
                else:
                    for symbol, tid in self.symbolCandleTickerIds.items():
                        if tid == id:
                            return symbol
        except:
            self.logger.exception('getSymbolForTickerId: EXCEPTION')
        return None


    def contractDetails(self, reqId:int, contractDetails:ContractDetails):
        try:
            self.logger.debug(f'contractDetails: reqId={reqId}, contractDetails={contractDetails}')
            self.cDetails[contractDetails.contract.symbol] = contractDetails
        except:
            self.logger.exception('contractDetails: EXCEPTION')


    def contractDetailsEnd(self, reqId:int):
        self.logger.debug('End of contract details')


    def error(self, e:Exception):
        self.logger.error(e)


    def error(self, msg:str):
        if msg != None and 'Order Canceled - reason: - (202)' in msg:
            # Ignore order cancelled error
            return
        self.sendMessage(msg)
        self.logger.error(msg)


    def error(self, reqId:int, code:int, msg:str, misc:str=''):
        if code in [2104, 2106, 2158]:
            if 'is OK' in msg:
                self.logger.info(msg)
            else:
                self.logger.error(msg)
        elif code == 202:
            self.logger.info('Order successfully cancelled')
        else:
            msg = f'{msg} - ({code})'
            self.sendMessage(msg)
            self.logger.error(msg)


    def requestData(self, symbol:str, timeframe:str='1 min', duration:str='10 D', keepUpdated:bool=True):
        try:
            contract = IBClient.createStockContract(symbol)
            # Historical data
            symbol = symbol.upper()
            timeframe = timeframe.lower()
            key = (symbol, timeframe, )
            if key not in self.symbolTimeframeHistTickerIds:
                # Create a new ticker request
                tid = self.getNextTickerId()
                self.symbolTimeframeHistTickerIds[key] = tid
                self.histTickerIdSymbolTimeframe[tid] = key
                self.symbolCandleData[key] = []
                self.reqHistoricalData(
                    tid, contract, '', duration, timeframe, 'TRADES', True, 2, keepUpdated, []
                )
            else:
                # Already requested data for this symbol
                if key in self.symbolCandleData and len(self.symbolCandleData[key]) > 0:
                    asyncio.run_coroutine_threadsafe(
                        self.dataQueue.put(QueueObject(ObjectType.HistoricalData, symbol=key[0], timeframe=key[1], listData=self.symbolCandleData[key])),
                        self.loop
                    )
            # Check if we already have contract details for this stock
            if symbol not in self.cDetails:
                self.reqContractDetails(self.getNextRequestId(), contract)
        except:
            self.logger.exception('requestData: EXCEPTION')


    def historicalData(self, reqId:int, bar:BarData):
        try:
            # Too much output at debug level
            #self.logger.debug(f'historicalData reqId={reqId}, bar={bar}')
            # creation bar dictionary for each bar received
            data = self.convertBar(bar)
            if reqId in self.histTickerIdSymbolTimeframe:
                key = self.histTickerIdSymbolTimeframe[reqId]	# key: (symbol,timeframe)
                self.symbolCandleData[key].append(data)
            else:
                self.logger.warning(f'historicalData: Unknown tickerId={reqId}, bar={bar}')
        except:
            self.logger.exception('historicalData: EXCEPTION')


    def historicalDataUpdate(self, reqId:int, bar:BarData):
        try:
            self.logger.debug(f'historicalDataUpdate reqId={reqId}, bar={bar}')
            data = self.convertBar(bar)
            if reqId not in self.histTickerIdSymbolTimeframe:
                self.logger.warning(f'historicalData: Unknown tickerId={reqId}, bar={bar}')
                return
            key = self.histTickerIdSymbolTimeframe[reqId]	# key: (symbol,timeframe)
            last = self.symbolCandleData[key][-1]
            if last['time'] == data['time']:
                self.symbolCandleData[key][-1] = data
            else:
                self.symbolCandleData[key].append(data)
                # Send to window
                asyncio.run_coroutine_threadsafe(
                    self.dataQueue.put(QueueObject(ObjectType.HistoricalData, symbol=key[0], timeframe=key[1], listData=self.symbolCandleData[key])),
                    self.loop
                )
        except:
            self.logger.exception('historicalDataUpdate: EXCEPTION')


    # callback when all historical data has been received
    def historicalDataEnd(self, reqId:int, start:str, end:str):
        try:
            self.logger.debug(f'historicalDataEnd reqId={reqId}, start={start}, end={end}')
            if reqId not in self.histTickerIdSymbolTimeframe:
                self.logger.warning(f'historicalDataEnd: Unknown tickerId={reqId}, start={start}, end={end}')
                return
            key = self.histTickerIdSymbolTimeframe[reqId]	# key: (symbol,timeframe)
            asyncio.run_coroutine_threadsafe(
                self.dataQueue.put(QueueObject(ObjectType.HistoricalData, symbol=key[0], timeframe=key[1], listData=self.symbolCandleData[key])),
                self.loop
            )
        except:
            self.logger.exception('historicalDataEnd: EXCEPTION')
