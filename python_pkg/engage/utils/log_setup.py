
# standard setup for logging

import sys
import os.path
import logging
import logging.handlers
from user_error import UserError, AREA_ENGAGE

ERROR_LOG_BAD_ARG = 001

# we monkeypatch the level names of logging to include our special "action" level
ACTION = 15
logging._levelNames["ACTION"] = ACTION
logging._levelNames[ACTION] = "ACTION"

log_level = logging.INFO

initialized = False

log_level_map = {
  logging.DEBUG: "DEBUG",
  ACTION: "ACTION",
  logging.INFO: "INFO",
  logging.WARNING: "WARNING",
  logging.ERROR: "ERROR"
}

class LogProxy:
    """Proxy for loggers. Needed since we can't subclass a logger. Delegates
    most calls to the underlying logger"""

    def __init__(self, logger):
        #Set attribute.
        self._logger = logger
        
    def __getattr__(self, attrib):
        if attrib == "action":
            return self.action
        else:
            return getattr(self._logger, attrib)

    def action(self, msg):
        self._logger.log(ACTION, msg)


def add_log_option(option_parser, default="INFO"):
    """Add a logging level option to an command line option parser"""
    option_parser.add_option("-l", "--log", action="store",
                             type="string",
                             help="set log level: DEBUG|ACTION|INFO|WARNING|ERROR",
                             dest="loglevel", default=default)
    option_parser.add_option("-f", "--logfile-name", action="store",
                             type="string",
                             help="logfile name",
                             dest="logfile", default=os.path.basename(sys.argv[0]).replace(".py", "") + ".log")

def extract_log_options_from_options_obj(options):
    """Create the command line arguments for logging based on the
    options object which was output from optparse.
    """
    args = ["--log=%s" % options.loglevel]
    if options.logfile:
        args.append("--logfile=%s" % options.logfile)
    return args


def _initialize_logging(log_directory, logfile_name,
                        rotate_logfiles=True):
    global initialized
    if not initialized:
        log_file_path = os.path.join(log_directory, logfile_name)
        if rotate_logfiles:
            do_rollover = os.path.exists(log_file_path)
            file_handler = logging.handlers.RotatingFileHandler(log_file_path, backupCount=10)
            if do_rollover:
                file_handler.doRollover()
        else:
            file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("[%(levelname)s][%(name)s] %(message)s")
        file_handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)
        initialized = True

    
def parse_log_options(options, log_directory, rotate_logfiles=True):
    """Given parsed options, parse the loglevel and set the level
    appropriately. If the level is bad, print an error message, the
    valid options, and exit"""
    global log_level
    if options.loglevel=="DEBUG": log_level = logging.DEBUG
    elif options.loglevel=="ACTION": log_level = ACTION
    elif options.loglevel=="INFO": log_level = logging.INFO
    elif options.loglevel=="WARNING": log_level = logging.WARNING
    elif options.loglevel=="ERROR": log_level = logging.ERROR
    else:
        raise UserError(AREA_INSTALL, "Logging", ERROR_LOG_BAD_ARG,
                        "Invalid log level: '%s', valid levels are ERROR, WARNING, INFO, ACTION, and DEBUG"
                        % options.loglevel)
    _initialize_logging(log_directory, options.logfile,
                        rotate_logfiles=rotate_logfiles)


def setup_logger(area, subarea):
    if subarea == "__main__":
        subarea = sys.argv[0].replace(".py", "")
    logger = logging.getLogger("%s.%s" % (area, subarea))
    return LogProxy(logger)


def setup_engage_logger(subarea):
    return setup_logger(AREA_ENGAGE, subarea)

# for backward compatibility
setup_engine_logger = setup_engage_logger
setup_script_logger = setup_engage_logger
setup_app_script_logger = setup_engage_logger

class FakeLogger:
    """This is just a fake logger that writes everything to stderr.
    We can use this as our logger until we've initialized the real logger.
    """
    def __init__(self):
        pass
    def debug(self, msg):
        sys.stderr.write(msg + "\n")
    def action(self, msg):
        sys.stderr.write(msg + "\n")
    def info(self, msg):
        sys.stderr.write(msg + "\n")
    def warning(self, msg):
        sys.stderr.write(self, msg + "\n")
    def error(self, msg):
        sys.stderr.write(msg + "\n")
    def exception(self, msg):
        sys.stderr.write(msg + "\n")
    def critical(self, msg):
        sys.stderr.write(msg + "\n")


def logger_for_repl(module_name="repl"):
    """This is a shortcut for when running from the repl. It
    initializes the logging to print to stdout and returns
    a logger.
    """
    global initialized
    if not initialized:
        formatter = logging.Formatter("[%(levelname)s][%(name)s] %(message)s")
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        initialized = True
    return setup_engage_logger(module_name)
