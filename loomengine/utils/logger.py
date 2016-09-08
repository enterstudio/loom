import logging
import os
import sys

def _get_handler(logfile):
    if logfile is None:
        return logging.StreamHandler()
    else:
        if not os.path.exists(os.path.dirname(logfile)):
            os.makedirs(os.path.dirname(logfile)) 
    return logging.FileHandler(logfile)

def get_logger(name, logfile=None, loglevel=logging.DEBUG):
    logger = logging.getLogger(name)
    logger.setLevel(loglevel)
    formatter = logging.Formatter('%(levelname)s [%(asctime)s] %(message)s')
    handler = _get_handler(logfile)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def get_console_logger(level=None, formatter=None, name=None):
    import logging
    import sys

    if level is None:
        level = logging.DEBUG

    if name is None:
        name = 'terminal'
        
    logger = logging.getLogger(name)
    logger.setLevel(level)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)

    if formatter is None:
        formatter = logging.Formatter('%(message)s')
        
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger

def get_null_logger(level=None, name=None):
    import logging
    import sys

    if level is None:
        level = logging.DEBUG

    if name is None:
        name = 'terminal'
        
    logger = logging.getLogger(name)
    logger.setLevel(level)

    ch = logging.NullHandler()
    ch.setLevel(level)

    logger.addHandler(ch)

    return logger

class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    Credit to: http://www.electricmonk.nl/log/2011/08/14/redirect-stdout-and-stderr-to-a-logger-in-python/
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip()) 

    def flush(self):
        for handler in self.logger.handlers:
            handler.flush()

def add_stdout(logger, log_level=logging.INFO):
    stdout_logger = StreamToLogger(logger, log_level)
    sys.stdout = stdout_logger

def add_stderr(logger, log_level=logging.ERROR):
    stderr_logger = StreamToLogger(logger, log_level)
    sys.stderr = stderr_logger
