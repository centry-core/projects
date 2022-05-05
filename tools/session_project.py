from typing import Optional
from flask import session

from tools import config


class SessionProject:
    @staticmethod
    def set(project_id: int) -> None:
        session[config.PROJECT_CACHE_KEY] = project_id

    @staticmethod
    def pop() -> Optional[int]:
        return session.pop(config.PROJECT_CACHE_KEY, default=None)

    @staticmethod
    def get() -> Optional[int]:
        return session.get(config.PROJECT_CACHE_KEY)
