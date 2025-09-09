import logging

FORMAT = '%(asctime)s - ^COL_START^%(levelname)s^COL_END^:     %(name)s:	%(message)s'

class CustomLogFormat(logging.Formatter):
    """Logging colored formatter, adapted from https://stackoverflow.com/a/56944256/3638629"""

    grey = '\x1b[38;21m'
    blue = '\x1b[38;5;39m'
    green = '\x1b[32m'
    yellow = '\x1b[38;5;226m'
    red = '\x1b[38;5;196m'
    bold_red = '\x1b[31;1m'
    reset = '\x1b[0m'

    def __init__(self):
        super().__init__(fmt=FORMAT)
        self.fmt = FORMAT

        self.FORMATS = {
            logging.DEBUG: self.fmt.replace('^COL_START^', self.grey).replace('^COL_END^', self.reset),
            logging.INFO: self.fmt.replace('^COL_START^', self.green).replace('^COL_END^', self.reset),
            logging.WARNING: self.fmt.replace('^COL_START^', self.yellow).replace('^COL_END^', self.reset),
            logging.ERROR: self.fmt.replace('^COL_START^', self.red).replace('^COL_END^', self.reset),
            logging.CRITICAL: self.fmt.replace('^COL_START^', self.bold_red).replace('^COL_END^', self.reset),
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)