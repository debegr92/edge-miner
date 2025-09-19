import json
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field


class ObjectType(Enum):
    Message = 0
    HistoricalData = 1


@dataclass
class QueueObject:
    type: ObjectType
    symbol: str = None
    timeframe: str = None
    stringData: str = None
    listData: list = field(default_factory=lambda: [])


class GenericClient():

    def __init__(self, dataQueue:asyncio.Queue, loop:asyncio.AbstractEventLoop):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel('INFO')

        # Stop logger from spamming INFO log if not DEBUG level
        utilsLogger = logging.getLogger('ibapi.utils')
        utilsLogger.setLevel(logging.WARNING)

        self.dataQueue:asyncio.Queue = dataQueue
        self.loop = loop


    def start(self) -> None:
        pass


    def requestData(self, symbol:str, timeframe:str='1 min', duration:str='2 D', endDate:str=''):
        pass

    def close(self):
        pass