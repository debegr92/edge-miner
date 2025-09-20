import asyncio
import os
import sys
import logging
import pandas as pd
from datetime import date, datetime, timedelta

# Charting
from lightweight_charts import Chart
from lightweight_charts.drawings import HorizontalLine
from lightweight_charts.topbar import ButtonWidget, MenuWidget

from colors import *
from indicators import indicatorFactory
from generic_client import GenericClient, ObjectType, QueueObject


TF_DURATION_MAP = {
    '1 min':'1 D',
    '2 mins':'1 D',
    '3 mins':'1 D',
    '5 mins':'1 D',
    '10 mins':'1 W',
    '15 mins':'1 W',
    '20 mins':'1 M',
    '30 mins':'1 M',
    '1 hour':'3 M',
    '2 hours':'3 M',
    '3 hours':'6 M',
    '4 hours':'6 M',
    '1 day':'5 Y'
}


class Window():

    def __init__(self, client:GenericClient):
        self.logger = logging.getLogger(__name__)
        # Set correct log level
        self.logger.setLevel('INFO')
        self.client = client
        self.dataQueue:asyncio.Queue = client.dataQueue

        # Price Charts
        self.chart = Chart(title='EdgeMiner', inner_height=1, inner_width=1, toolbox=True, maximize=True, debug=False)
        self.chart.watermark('ctrl+f to load ticker', font_size=35, color=WATERMARK_COLOR)
        self.chart.volume_config(up_color=VOLUME_UP_COLOR, down_color=VOLUME_DOWN_COLOR)
        self.chart.topbar.textbox('textbox-ticker', '')
        self.currentTicker = ''
        self.chart.topbar.menu('menu-timeframe', tuple(list(TF_DURATION_MAP.keys())), default='1 min', func=self.onTimeframeSelection)
        self.currentTimeframe = '1 min'
        self.chart.topbar.textbox('sep1', '|')
        # create a button for taking a screenshot of the chart
        self.chart.topbar.button('screenshot', '📸', func=self.onTakeScreenshot)

        # Tools
        self.chart.topbar.textbox('sep2', '|')
        self.riskLine:HorizontalLine = None
        self.chart.topbar.menu('menu-marker', ('🟩', '🟥', '🟪'), default='🟩', func=self.onToggleMarker)
        self.chart.topbar.button('button-clear-all', '🗑️', func=self.onClearAll)

        # Current watched date
        self.chart.topbar.textbox('sep3', '|')
        self.chart.topbar.button('button-prev-day', '⏮️', func=self.onPrevDay)
        self.currentDate = date.today() - timedelta(days=1)
        self.chart.topbar.textbox('textbox-date', self.currentDate.isoformat())	# |<< 2025-08-02 >>|
        self.chart.topbar.button('button-next-day', '⏭️', func=self.onNextDay)

        self.chart.topbar.button('button-info', 'ℹ️', align='right', func=self.onInfoClick)

        self.vwapLine = self.chart.create_line('VWAP', color=VWAP_COLOR, width=2, price_line=False, price_label=False)
        self.emaLine = self.chart.create_line('EMA', color=EMA_COLOR, width=1, price_line=False, price_label=False)
        self.smaLine = self.chart.create_line('SMA', color=SMA_COLOR, width=2, price_line=False, price_label=False)
        self.bb1uLine = self.chart.create_line('BB_UPPER1', color=BB_COLOR, width=1, price_line=False, price_label=False)
        self.bb2uLine = self.chart.create_line('BB_UPPER2', color=BB_COLOR, width=1, price_line=False, price_label=False)
        self.bb1lLine = self.chart.create_line('BB_LOWER1', color=BB_COLOR, width=1, price_line=False, price_label=False)
        self.bb2lLine = self.chart.create_line('BB_LOWER2', color=BB_COLOR, width=1, price_line=False, price_label=False)
        self.kcUpper = self.chart.create_line('KC_UPPER', color=KC_COLOR, width=1, price_line=False, price_label=False)
        self.kcLower = self.chart.create_line('KC_LOWER', color=KC_COLOR, width=1, price_line=False, price_label=False)

        # Indicators
        # ADX
        self.adxLine = self.chart.create_line('ADX', color=ADX_COLOR, price_line=False, width=1, pane_index=1)
        self.dmimLine = self.chart.create_line('DMIM', color=DMIM_COLOR, price_line=False, width=1, pane_index=1)
        self.dmipLine = self.chart.create_line('DMIP', color=DMIP_COLOR, price_line=False, width=1, pane_index=1)
        # Add horizontal lines to ADX indicator
        self.adxLine.horizontal_line(12, text='12', color=HLINE_COLOR, width=1, style='solid', axis_label_visible=False)
        self.adxLine.horizontal_line(20, text='20', color=HLINE_COLOR, width=1, style='solid', axis_label_visible=False)
        # BB%
        self.bbpcLine = self.chart.create_line('BB_PC', color=BBPC_COLOR, price_line=False, width=1, pane_index=2)
        # Add horizontal lines to BB% indicator
        self.bbpcLine.horizontal_line(3, text='+3', color=HLINE_COLOR, width=1, style='solid', axis_label_visible=False)
        self.bbpcLine.horizontal_line(2, text='+2', color=HLINE_COLOR, width=1, style='solid', axis_label_visible=False)
        self.bbpcLine.horizontal_line(0, text='0', color=HLINE_COLOR, width=1, style='solid', axis_label_visible=False)
        self.bbpcLine.horizontal_line(-2, text='-2', color=HLINE_COLOR, width=1, style='solid', axis_label_visible=False)
        self.bbpcLine.horizontal_line(-3, text='-3', color=HLINE_COLOR, width=1, style='solid', axis_label_visible=False)
        # RSI
        self.rsiLine = self.chart.create_line('RSI', color=RSI_COLOR, price_line=False, width=1, pane_index=3)
        # Add horizontal lines to RSI indicator
        self.rsiLine.horizontal_line(50, text='50', color=HLINE_COLOR, width=1, style='solid', axis_label_visible=False)
        self.rsiLine.horizontal_line(70, text='70', color=HLINE_COLOR, width=1, style='solid', axis_label_visible=False)
        self.rsiLine.horizontal_line(30, text='30', color=HLINE_COLOR, width=1, style='solid', axis_label_visible=False)		

        # Resize the main chart pane
        self.chart.resize_pane(0, 600)

        # set up a function to call when searching for symbol
        self.chart.events.search += self.onSearch
        self.chart.events.click += self.onClick
        self.chart.events.range_change += self.onRangeChange

        # Hotkeys
        self.chart.hotkey('ctrl', 'a', self.onHotkeyPrevDay)
        self.chart.hotkey('ctrl', 'd', self.onHotkeyNextDay)
        self.chart.hotkey('ctrl', 's', self.onHotkeyScreenshot)
        self.chart.hotkey('ctrl', 'm', self.onHotkeyToggleMarker)
        self.chart.hotkey('ctrl', 'r', self.onHotkeyClearAll)


    async def run(self):
        try:
            # https://lightweight-charts-python.readthedocs.io/en/latest/tutorials/events.html#async-clock
            self.logger.info('window.run()')
            await asyncio.gather(
                self.chart.show_async(),
                self.queueHandler()
            )
            self.logger.debug('run() END')
        except:
            self.logger.exception('run: EXCEPTION')


    async def queueHandler(self):
        self.logger.debug('queueHandler started')
        self.client.start()
        while self.chart.is_alive:
            try:
                while self.dataQueue.empty():
                    # Exit if chart window is no longer shown
                    if not self.chart.is_alive:
                        return
                    await asyncio.sleep(0.05)

                qo:QueueObject = await self.dataQueue.get()

                # Exit if chart window is no longer shown
                if not self.chart.is_alive:
                    return

                self.logger.debug(f'Got queue object type: {qo.type} for {qo.symbol}')

                if qo.type == ObjectType.Message:
                    self.showMessage(qo.stringData)

                elif qo.type == ObjectType.HistoricalData:
                    sym = qo.symbol
                    currentSym = self.chart.topbar['textbox-ticker'].value
                    # Convert list data to Pandas DataFrame and save
                    if sym == currentSym:
                        df = pd.DataFrame(qo.listData)
                        if qo.timeframe == self.chart.topbar['menu-timeframe'].value:
                            self.updateChart(df, qo.symbol)
                else:
                    self.logger.warning('queueHandler: Unkown queue object type!')
            except:
                self.logger.exception('queueHandler: EXCEPTION')
        self.logger.info('Chart closed, end application...')
        sys.exit()


    def showMessage(self, msg:str) -> None:
        """Show a single line of alert message using JavaScript

        Args:
            msg (str): Single line text message to show. No special characters or line breaks allowed.
        """
        try:
            self.chart.run_script(f'''
                alert("{msg}");
            ''')
        except:
            self.logger.exception(f'showMessage: EXCEPTION!')


    #  get new bar data when the user enters a different symbol
    def onSearch(self, chart:Chart, searchString:str):
        try:
            self.logger.debug(f'onSearch({searchString})')
            if searchString == None or searchString == '' or searchString == self.chart.topbar['textbox-ticker'].value:
                self.logger.warning(f'empty search string or same as active ticker')
                return

            searchString = searchString.replace(' ', '')
            parts = searchString.split(',')
            
            newTicker = self.currentTicker
            newDate = self.currentDate
            if len(parts) > 1:
                # ticker and date
                newTicker = parts[0]
                newDate = date.fromisoformat(parts[1])
            else:
                # only ticker
                try:
                    temp = date.fromisoformat(parts[0])
                    # Successfully parse -> new date
                    newDate = temp
                except:
                    # Otherwise use input as new ticker
                    newTicker = parts[0]

            if newTicker != self.currentTicker or newDate != self.currentDate:
                # Save new data and request
                self.currentTicker = newTicker
                self.currentDate = newDate
                self.getBarData()
        except:
            self.logger.exception('onSearch: EXCEPTION')
            self.showHelpMessage()


    def getBarData(self):
        try:
            self.logger.debug(f'getBarData()')
            self.chart.watermark('loading...', color=WATERMARK_COLOR)
            self.onClearAll(self.chart)
            self.chart.topbar['textbox-ticker'].set(self.currentTicker)
            self.chart.topbar['textbox-date'].set(self.currentDate.isoformat())
            self.chart.spinner(True)
            self.client.requestData(
                self.currentTicker,
                self.currentTimeframe,
                TF_DURATION_MAP[self.currentTimeframe],
                self.currentDate.strftime('%Y%m%d 23:59:59 US/Eastern')
            )
        except:
            self.logger.exception('getBarData: EXCEPTION')


    # called when we want to update what is rendered on the chart
    def updateChart(self, df:pd.DataFrame, symbol:str):
        try:
            # Calculate all data
            chartData = indicatorFactory(df)
            chartData.to_json('out.json')
            # Update chart candles
            self.chart.set(chartData)
            self.chart.legend(visible=True, lines=False, color_based_on_candle=True)

            # Remove loading
            self.chart.watermark(f'{symbol} - {self.currentTimeframe} - {self.currentDate.isoformat()}', color=WATERMARK_COLOR)
            self.chart.spinner(False)

        except:
            self.chart.watermark('Something bad happend :( - check the logs!', font_size=22, color=WATERMARK_COLOR)
            self.chart.spinner(False)
            self.logger.exception('updateChart: EXCEPTION')


    # get new bar data when the user changes timeframes
    def onTimeframeSelection(self, chart:Chart):
        self.logger.debug('selected timeframe -> NOT IMPLEMENTED')
        self.currentTimeframe = self.chart.topbar['menu-timeframe'].value
        if self.currentTicker != None and self.currentTicker != '':
            self.getBarData()


    def onClick(self, chart:Chart, timestamp:float, price:float):
        self.logger.debug(f'onClick({timestamp}, {price})')
        tool = self.chart.topbar['menu-marker'].value
        try:
            if timestamp == None or price == None:
                return
            
            if tool == '🟩':
                self.chart.marker(timestamp*1000, 'below', 'arrow_up', BUY_MARKER_COLOR)
            elif tool == '🟥':
                self.chart.marker(timestamp*1000, 'above', 'arrow_down', SELL_MARKER_COLOR)
            elif tool == '🟪':
                if self.riskLine == None:
                    self.riskLine = self.chart.horizontal_line(price, RISK_LINE_COLOR, width=2)
                else:
                    self.riskLine.update(price)
        except:
            self.logger.exception('onClick: EXCEPTION')


    def onRangeChange(self, chart:Chart, barsBefore, barsAfter):
        self.logger.debug(f'onRangeChange({barsBefore}, {barsAfter})')


    def onHotkeyScreenshot(self, key:str):
        self.onTakeScreenshot(self.chart)


    def onHotkeyToggleMarker(self, key:str):
        self.logger.debug('onHotkeyToggleMarker()')
        menu:MenuWidget = self.chart.topbar.get('menu-marker')
        if menu.value == '🟩':
            menu.set('🟥')
        elif menu.value == '🟥':
            menu.set('🟪')
        else:
            menu.set('🟩')


    def onToggleMarker(self, chart:Chart):
        self.logger.debug('onToggleMarker()')


    # handler for the screenshot button
    def onTakeScreenshot(self, chart:Chart):
        # TODO: Implement symbol, timeframe, date, time, timestamp file name
        try:
            img = chart.screenshot()
            symbol = self.chart.topbar['textbox-ticker'].value
            filename = datetime.now().strftime(f"{symbol}_%Y-%m-%d_%H-%M-%S")

            # Check for screenshot folder or try to create path
            if os.path.exists('screenshots') == False:
                os.makedirs('screenshots')

            p = os.path.join('screenshots', f'{filename}.png')
            with open(p, 'wb') as f:
                f.write(img)
            # Show message on success
            self.showMessage(f'Saved {p}')
        except Exception as e:
            self.showMessage(f'Unable to save screenshot, check logs!')
            self.logger.exception('onTakeScreenshot: EXCEPTION')


    def onHotkeyClearAll(self, key:str):
        self.onClearAll(self.chart)


    def onClearAll(self, chart:Chart):
        try:
            self.logger.debug(f'onClearAll()')
            self.chart.clear_markers()
            if self.riskLine != None:
                self.deleteHorizontalLine(self.riskLine)
                self.riskLine = None
        except:
            self.logger.exception('onDeleteWatchlistClick: EXCEPTION')


    def deleteHorizontalLine(self, hline:HorizontalLine) -> None:
        try:
            self.logger.debug(f'deleteHorizontalLine() id={hline.id}')
            hline.delete()
            hline.run_script(f'''
                const idx = {hline.chart.id}.toolBox._drawingTool._drawings.findIndex(obj => obj._callbackName === "{hline.id}");
                if (idx !== -1)
                    {hline.chart.id}.toolBox._drawingTool._drawings.splice(idx, 1);
            ''')
        except:
            self.logger.exception(f'deleteHorizontalLine: EXCEPTION!')


    def onHotkeyPrevDay(self, key:str):
        self.onPrevDay(self.chart)


    def onPrevDay(self, chart:Chart):
        self.currentDate = self.currentDate - timedelta(days=1)
        self.getBarData()


    def onHotkeyNextDay(self, key:str):
        self.onNextDay(self.chart)


    def onNextDay(self, chart:Chart):
        self.currentDate = self.currentDate + timedelta(days=1)
        self.getBarData()


    def showHelpMessage(self):
        self.showMessage("CTRL+F Input Format: AAPL,2025-08-02")


    def onInfoClick(self, chart:Chart):
        self.showHelpMessage()
