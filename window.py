import asyncio
import os
import sys
import logging
import pandas as pd
from zoneinfo import ZoneInfo
from datetime import date, time, datetime, timedelta

# Charting
from lightweight_charts import Chart
from lightweight_charts.drawings import HorizontalLine
from lightweight_charts.topbar import ButtonWidget, MenuWidget, SwitcherWidget

from colors import *
from indicators import indicatorFactory, getCandleType
from generic_client import GenericClient, ObjectType, QueueObject


TF_DURATION_MAP = {
    '1 day':'5 Y',
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
    '4 hours':'6 M'
}


class Window():

    def __init__(self, client:GenericClient):
        self.logger = logging.getLogger(__name__)
        # Set correct log level
        self.logger.setLevel('INFO')
        self.client = client
        self.dataQueue:asyncio.Queue = client.dataQueue
        self.data:pd.DataFrame = None
        
        self.setups:pd.DataFrame = pd.DataFrame()
        if os.path.exists('setups.json'):
            self.setups = pd.read_json('setups.json')

        # Price Charts
        self.chart = Chart(title='EdgeMiner', inner_height=1, inner_width=1, toolbox=True, maximize=True, debug=False)
        self.chart.watermark('ctrl+f to load ticker', font_size=35, color=WATERMARK_COLOR)
        self.chart.volume_config(up_color=VOLUME_UP_COLOR, down_color=VOLUME_DOWN_COLOR)
        self.chart.topbar.textbox('textbox-ticker', '')
        self.currentTicker = ''
        self.chart.topbar.menu('menu-timeframe', tuple(list(TF_DURATION_MAP.keys())), default='1 day', func=self.onTimeframeSelection)
        self.currentTimeframe = '1 day'
        self.chart.topbar.textbox('sep1', '|')
        # create a button for taking a screenshot of the chart
        self.chart.topbar.button('screenshot', '📸', func=self.onTakeScreenshot)

        # Tools
        self.chart.topbar.textbox('sep2', '|')
        self.riskLine:HorizontalLine = None
        self.chart.topbar.switcher('switcher-type', ('Signal', 'Trade',), 'Signal', func=self.onSwitchType)
        self.chart.topbar.menu('menu-marker', ('🟩', '🟥', '🟪'), default='🟩', func=self.onToggleMarker)
        self.chart.topbar.button('button-clear-all', '🗑️', func=self.onClearAll)

        # Current watched date
        self.chart.topbar.textbox('sep3', '|')
        self.chart.topbar.button('button-prev-day', '⏮️', func=self.onPrevDay)
        self.currentDate = date.today() - timedelta(days=1)
        self.chart.topbar.textbox('textbox-date', self.currentDate.isoformat())	# |<< 2025-08-02 >>|
        self.chart.topbar.button('button-next-day', '⏭️', func=self.onNextDay)

        self.chart.topbar.textbox('sep4', '|')
        self.chart.topbar.menu('menu-strategy', ('Mean Reversion','Trend Follow','VWAP Test','VWAP Cross'), default='Mean Reversion', func=self.onStrategySelection)

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
        # TODO: Dot style not available
        #self.psarLine = self.chart.create_line('PSAR', color=PSAR_COLOR, width=1, price_line=False, price_label=False, style='dotted')

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

            if ':' in searchString:
                # Additional function
                searchString = searchString.upper().replace(' ', '')
                parts = searchString.split(':')
                if parts[0] == 'IMPORT':
                    dates = parts[1].split(',')
                    # Tag trades date by date
                    for d in dates:
                        d = datetime.fromisoformat(d).date()
                        dt = datetime.combine(d, time(15, 30))
                        self.addSetup(dt)
                else:
                    raise Exception('Unknown action')
            else:
                # Request new symbol
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
            # Update chart candles
            self.chart.set(chartData)
            self.chart.legend(visible=True, lines=False, color_based_on_candle=True)
            # Remove loading
            self.chart.watermark(f'{symbol} - {self.currentTimeframe} - {self.currentDate.isoformat()}', color=WATERMARK_COLOR)
            self.chart.spinner(False)
            self.data = chartData
        except:
            self.chart.watermark('Something bad happend :( - check the logs!', font_size=22, color=WATERMARK_COLOR)
            self.chart.spinner(False)
            self.logger.exception('updateChart: EXCEPTION')
        self.updateMarkers()


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
            
            sType = self.chart.topbar['switcher-type'].value
            if sType == 'Signal':
                self.addSetup(datetime.fromtimestamp(timestamp))
            else:
                if tool == '🟪':
                    if self.riskLine == None:
                        self.riskLine = self.chart.horizontal_line(price, RISK_LINE_COLOR, width=2)
                    else:
                        self.riskLine.update(price)
            
        except:
            self.logger.exception('onClick: EXCEPTION')


    def addSetup(self, dt:datetime) -> None:
        try:
            tool = self.chart.topbar['menu-marker'].value
            ticker = self.chart.topbar['textbox-ticker'].value
            strategy = self.chart.topbar['menu-strategy'].value
            timeframe = self.chart.topbar['menu-timeframe'].value
            signalType = self.chart.topbar['switcher-type'].value
            d = {
                'ticker': ticker,
                'strategy': strategy,
                'timeframe': timeframe,
                'signalType': signalType
            }
            
            if tool == '🟩':
                d['direction'] = 'long'
                self.chart.marker(dt.timestamp()*1000, 'below', 'arrow_up', BUY_MARKER_COLOR)
            elif tool == '🟥':
                d['direction'] = 'short'
                self.chart.marker(dt.timestamp()*1000, 'above', 'arrow_down', SELL_MARKER_COLOR)

            # Closest row
            pos = self.data['time'].searchsorted(dt)
            if pos == 0:
                closest_idx = 0
            elif pos == len(self.data):
                closest_idx = len(self.data) - 1
            else:
                before, after = self.data.iloc[pos-1], self.data.iloc[pos]
                closest_idx = pos-1 if abs(before['time'] - dt) <= abs(after['time'] - dt) else pos

            closest_row = self.data.iloc[closest_idx].to_dict()

            # Row before closest (with prefix p)
            before_row = (
                self.data.iloc[closest_idx - 1].to_dict() if closest_idx > 0 else {}
            )
            before_row_prefixed = {f'p{k}': v for k, v in before_row.items()}

            # Combine
            d = {**d, **closest_row, **before_row_prefixed}

            # Calculate additional states
            # percent change
            d['GAP_PC'] = (d['open']/d['pclose']-1.0)*100.0
            d['CHANGE_PC'] = (d['close']/d['open']-1.0)*100.0
            d['pCHANGE_PC'] = (d['pclose']/d['popen']-1.0)*100.0
            # Volume SMA rising
            d['VOL_SMA_RISING'] = d['VOL_SMA'] > d['pVOL_SMA']
            # Volume Multiple vol/volSma
            d['VOL_MULTIPLE'] = d['volume'] / d['VOL_SMA']
            d['pVOL_MULTIPLE'] = d['pvolume'] / d['pVOL_SMA']
            # SMA, EMA
            d['EMA_RISING'] = d['EMA'] > d['pEMA']
            d['SMA_RISING'] = d['SMA'] > d['pSMA']
            d['OVER_EMA'] = d['close'] > d['EMA']
            d['OVER_SMA'] = d['close'] > d['SMA']
            d['pOVER_EMA'] = d['pclose'] > d['pEMA']
            d['pOVER_SMA'] = d['pclose'] > d['pSMA']
            d['EMA_OVER_SMA'] = d['EMA'] > d['SMA']
            d['pEMA_OVER_SMA'] = d['pEMA'] > d['pSMA']
            # BB, KC
            d['BB_PC_RISING'] = d['BB_PC'] > d['pBB_PC']
            d['KC_INSIDE_BB'] = d['BB_UPPER1'] > d['KC_UPPER']
            d['pKC_INSIDE_BB'] = d['pBB_UPPER1'] > d['pKC_UPPER']
            # ATR rising
            d['ATR_RISING'] = d['ATR'] > d['pATR']
            # ADX, DMIs rising
            d['ADX_RISING'] = d['ADX'] > d['pADX']
            d['DMIP_RISING'] = d['DMIP'] > d['pDMIP']
            d['DMIM_RISING'] = d['DMIM'] > d['pDMIM']
            d['DMI_DIFFERENCE'] = d['DMIP'] - d['DMIM']
            d['pDMI_DIFFERENCE'] = d['pDMIP'] - d['pDMIM']
            # RSI Rising
            d['RSI_RISING'] = d['RSI'] > d['pRSI']
            # PSAR Bull
            d['PSAR_BULL'] = d['PSAR'] < d['low']
            d['pPSAR_BULL'] = d['pPSAR'] < d['plow']
            # Candle Type
            d['CANDLE_TYPE'] = getCandleType(d['open'], d['high'], d['low'], d['close'])
            d['pCANDLE_TYPE'] = getCandleType(d['popen'], d['phigh'], d['plow'], d['pclose'])
            # insideCandle
            d['INSIDE_CANDLE'] = d['high'] < d['phigh'] and d['low'] < d['plow']
            d['OUTSIDE_CANDLE'] = d['high'] > d['phigh'] and d['low'] > d['plow']

            # Add all the data to the dict
            if len(self.setups) == 0:
                self.setups = pd.DataFrame(d, index=[0])
            else:
                self.setups.loc[len(self.setups)] = d

            self.setups.to_json('setups.json')
            self.setups.to_csv('setups.csv')
        except Exception as e:
            self.showMessage(f'Unable to save setups.json, check logs!')
            self.logger.exception('addSetup: EXCEPTION')


    def onRangeChange(self, chart:Chart, barsBefore, barsAfter):
        self.logger.debug(f'onRangeChange({barsBefore}, {barsAfter})')


    def onHotkeyScreenshot(self, key:str):
        self.onTakeScreenshot(self.chart)


    def onHotkeyToggleMarker(self, key:str=''):
        self.logger.debug('onHotkeyToggleMarker()')
        menu:MenuWidget = self.chart.topbar.get('menu-marker')
        switcher:SwitcherWidget = self.chart.topbar.get('switcher-type')
        if menu.value == '🟩':
            menu.set('🟥')
        elif menu.value == '🟥':
            if switcher.value == 'Signal':
                menu.set('🟩')
            else:
                menu.set('🟪')
        else:
            menu.set('🟩')
        self.updateMarkers()


    def onSwitchType(self, chart:Chart):
        menu:MenuWidget = self.chart.topbar.get('menu-marker')
        if menu.value == '🟪':
            self.onHotkeyToggleMarker()
        self.updateMarkers()


    def onToggleMarker(self, chart:Chart):
        self.logger.debug('onToggleMarker()')
        sType = self.chart.topbar.get('switcher-type').value
        if sType == 'Signal':
            self.onSwitchType(self.chart)


    def updateMarkers(self) -> None:
        try:
            # Clear all markers
            self.onClearAll(self.chart)

            if len(self.setups) == 0:
                return

            # Filter all signals and trades based on current settings
            signalType = self.chart.topbar['switcher-type'].value
            filter = {
                'ticker': self.chart.topbar['textbox-ticker'].value,
                'strategy': self.chart.topbar['menu-strategy'].value,
                'timeframe': self.chart.topbar['menu-timeframe'].value,
                'signalType': signalType
            }
            currentSetups:pd.DataFrame = self.setups.loc[(self.setups[list(filter)] == pd.Series(filter)).all(axis=1)].copy()
            # Exit if no setups with the current settings
            if len(currentSetups) == 0:
                return

            currentSetups.sort_values('time', ascending=True, inplace=True)

            if signalType == 'Signal':
                for idx, s in currentSetups.iterrows():
                    if s['direction'] == 'long':
                        self.chart.marker(s['time'], 'below', 'arrow_up', BUY_MARKER_COLOR)               
                    else:
                        self.chart.marker(s['time'], 'above', 'arrow_down', SELL_MARKER_COLOR)
            else:
                # TODO: Implement function
                pass

        except:
            self.logger.exception('updateMarkers: EXCEPTION')


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
            # TODO: Only clear current trade
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


    def onStrategySelection(self, chart:Chart):
        self.updateMarkers()


    def showHelpMessage(self):
        self.showMessage("CTRL+F Input Format: AAPL,2025-08-02")


    def onInfoClick(self, chart:Chart):
        self.showHelpMessage()
