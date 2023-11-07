from abc import ABC, abstractmethod
from typing import Any

from pylon.core.tools import log


class ProjectCreationStep(ABC):
    all_steps = []

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    def __eq__(self, other: 'ProjectCreationStep') -> bool:
        return self.name == other.name

    def __new__(cls, *args, **kwargs):
        klass = super().__new__(cls)
        try:
            index = ProjectCreationStep.all_steps.index(klass)
            return ProjectCreationStep.all_steps[index]
        except ValueError:
            ProjectCreationStep.all_steps.append(klass)
            return klass

    def __init__(self, module=None):
        self.module = module
        self._created = {
            'initialized': False,
            'ok': None,
            'msg': '',
            'step': self.name
        }
        self._deleted = {
            'initialized': False,
            'ok': None,
            'msg': '',
            'step': self.name
        }

        self.create = self.check_status('_created')(self.create)
        self.delete = self.check_status('_deleted')(self.delete)

        log.info('Init step %s', self.name)

    @property
    def status(self) -> dict:
        return {
            'created': self._created,
            'deleted': self._deleted
        }

    def check_status(self, bool_attr: str):
        def decorator(func):
            def wrapper(*args, **kwargs):
                log.info('%s is called %s', self, bool_attr)
                bound_property = getattr(self, bool_attr)
                bound_property['initialized'] = True
                try:
                    result = func(*args, **kwargs)
                    bound_property['ok'] = True
                    return result
                except Exception as e:
                    bound_property['ok'] = False
                    bound_property['msg'] = str(e)
                    log.warning('%s Failed with %s', self, e)
                    raise
            return wrapper
        return decorator

    def __repr__(self) -> str:
        extra = []
        if self._created['ok']:
            extra.append('created')
        if self._deleted['ok']:
            extra.append('deleted')

        return f'<Step: {self.name} {" ".join(extra)}>'

    @abstractmethod
    def create(self, *args, **kwargs) -> dict | None | Any:
        ...

    @abstractmethod
    def delete(self, *args, **kwargs) -> Any:
        ...
