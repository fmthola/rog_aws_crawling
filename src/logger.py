import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name="AWS_ROG_Explorer", log_file="logs/app.log", level=logging.INFO):
    """
    Sets up a centralized logger with file and console handlers.
    """
    # Create logs directory if it doesn't exist
    if not os.path.exists(os.path.dirname(log_file)):
        os.makedirs(os.path.dirname(log_file))

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s'
    )

    # File Handler
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
    file_handler.setFormatter(formatter)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Add handlers if they don't exist (prevent duplicates)
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

# Global instance
log = setup_logger()
