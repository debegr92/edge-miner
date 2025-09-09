import os
import json
import asyncio
import logging
from sys import exit, stdout

from window import Window
from ib_client import IBClient

from log_config import CustomLogFormat, FORMAT


# Configure my custom format as STDOUT
# https://docs.python.org/3/library/logging.html#logrecord-attributes
handler = logging.StreamHandler(stdout)
handler.setFormatter(CustomLogFormat())
logging.basicConfig(
    level=logging.INFO,
    format=FORMAT,
    handlers=[
        handler
    ]
)


async def main():
    logger = logging.getLogger('main')
    try:
        # Set correct log level
        logger.setLevel('INFO')
        logger.info('main()')

        dataQueue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        # 7496 -> live, 7497 -> demo
        client = IBClient(dataQueue, loop, port=7497)

        window = Window(client, dataQueue)
        # Start the async processor
        task = asyncio.create_task(window.run())

        # Let the async loop run forever (or until you want to stop)
        logger.debug('await chart window')
        await task
        logger.debug('chart window closed')

        logger.info('Disconnecting from IB API...')
        client.disconnect()

    except KeyboardInterrupt:
        logger.warning('Keyboard interrupt, shutting down...')
        exit()
    except:
        logger.exception('EdgeFinder MAIN EXCEPTION')


if __name__ == '__main__':
    asyncio.run(main())
