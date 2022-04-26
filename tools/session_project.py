from typing import Optional
from flask import session

from tools import config


class SessionProject:
    PROJECT_CACHE_KEY = config.PROJECT_CACHE_KEY

    @staticmethod
    def set(project_id: int) -> None:
        session[SessionProject.PROJECT_CACHE_KEY] = project_id

    @staticmethod
    def pop() -> Optional[int]:
        return session.pop(SessionProject.PROJECT_CACHE_KEY, default=None)

    @staticmethod
    def get() -> Optional[int]:
        return session.get(SessionProject.PROJECT_CACHE_KEY)
