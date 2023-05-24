import os

LOG_FORMAT = (
    "%(asctime)s [%(levelname)s] [%(funcName)s:%(lineno)d] %(name)s: %(message)s"
)
LOG_DEFAULT_HANDLERS = [
    "console",
]
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": LOG_FORMAT,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": "default",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
}
