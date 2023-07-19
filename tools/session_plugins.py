from typing import Optional
from flask import session

from tools import config


class SessionProjectPlugin:
    @staticmethod
    def set(plugins: list) -> None:
        session[config.PROJECT_CACHE_PLUGINS] = plugins

    @staticmethod
    def pop() -> Optional[int]:
        return session.pop(config.PROJECT_CACHE_PLUGINS, default=None)

    @staticmethod
    def get() -> Optional[int]:
        return session.get(config.PROJECT_CACHE_PLUGINS)
