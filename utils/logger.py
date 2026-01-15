import datetime
import sys


class Logger:
    # ANSI escape codes for colors
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def _timestamp():
        return datetime.datetime.now().strftime("%H:%M:%S")

    @classmethod
    def info(cls, msg):
        """General information flow"""
        print(f"{cls.CYAN}[{cls._timestamp()}] [INFO]    {msg}{cls.RESET}")

    @classmethod
    def success(cls, msg):
        """Successful operations"""
        print(f"{cls.GREEN}[{cls._timestamp()}] [SUCCESS] {msg}{cls.RESET}")

    @classmethod
    def warning(cls, msg):
        """Warnings that don't stop execution"""
        print(f"{cls.YELLOW}[{cls._timestamp()}] [WARN]    {msg}{cls.RESET}")

    @classmethod
    def error(cls, msg):
        """Critical errors"""
        print(f"{cls.RED}[{cls._timestamp()}] [ERROR]   {msg}{cls.RESET}")

    @classmethod
    def debug(cls, msg):
        """Debug info (useful for checking subprocess commands)"""
        print(f"{cls.BLUE}[{cls._timestamp()}] [DEBUG]   {msg}{cls.RESET}")

    @classmethod
    def header(cls, msg):
        """Section headers"""
        print(f"\n{cls.BOLD}{cls.HEADER}=== {msg} ==={cls.RESET}")