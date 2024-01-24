from typing import Union, Optional
import redis
import json

from ..models.project import Project
from ..models.quota import ProjectQuota
from ..models.statistics import Statistic

from tools import rpc_tools
from pylon.core.tools import web, log

from ..tools.session_project import SessionProject
from tools import constants


class RPC:
    @web.rpc('project_get_or_404', 'get_or_404')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def prj_or_404(self, project_id):
        return Project.query.get_or_404(project_id)

    @web.rpc('project_list', 'list')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def list_projects(self, **kwargs):
        return Project.list_projects(**kwargs)

    # @web.rpc('project_statistics', 'statistics')
    # @rpc_tools.wrap_exceptions(RuntimeError)
    # def get_project_statistics(self, project_id):
    #     return Statistic.query.filter_by(project_id=project_id).first().to_json()

    @web.rpc('projects_add_task_execution', 'add_task_execution')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def add_task_execution(self, project_id):
        try:
            statistic = Statistic.query.filter_by(project_id=project_id).first()
            setattr(statistic, 'tasks_executions', Statistic.tasks_executions + 1)
            statistic.commit()
        except AttributeError:
            ...

    @web.rpc('project_get_storage_space_quota', 'get_storage_space_quota')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_storage_quota(self, project_id):
        return Project.get_storage_space_quota(project_id=project_id)

    @web.rpc('project_check_quota', 'check_quota')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def check_quota(self, project_id, quota=None):
        return ProjectQuota.check_quota_json(project_id, quota)

    @web.rpc('project_get_id', 'get_id')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_id(self) -> Optional[int]:
        project_id = SessionProject.get()
        project = Project.query.get(project_id)
        if project:
            return project.id
        SessionProject.pop()
        return None
        # if not project_id:
        #     project_id = get_user_projects()[0]["id"]
        # return project

    # @web.rpc('project_set_active', 'set_active')
    # @rpc_tools.wrap_exceptions(RuntimeError)
    # def set_active(self, project_id: Union[str, int]):
    #     SessionProject.set(int(project_id))

    @web.rpc('increment_statistics', 'increment_statistics')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def increment_statistics(self, project_id, column: str, amount: int = 1):
        statistic = Statistic.query.filter_by(project_id=project_id).first()
        setattr(statistic, column, getattr(statistic, column) + amount)
        statistic.commit()

    @web.rpc('register_rabbit_queue', 'register_rabbit_queue')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def register_rabbit_queue(self, vhost, queue_name):
        _rc = redis.Redis(host=constants.REDIS_HOST, port=constants.REDIS_PORT, db=constants.REDIS_RABBIT_DB,
                          password=constants.REDIS_PASSWORD, username=constants.REDIS_USER)
        queues = _rc.get(name=vhost)
        queues = json.loads(queues) if queues else []
        if queue_name not in queues:
            queues.append(queue_name)
            _rc.set(name=vhost, value=json.dumps(queues))
            return f"Queue with name {queue_name} registered"
        return f"Queue with name {queue_name} already exist"

    @web.rpc('get_rabbit_queues', 'get_rabbit_queues')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_rabbit_queues(self, vhost: str, remove_internal: bool = False) -> list:
        _rc = redis.Redis(
            host=constants.REDIS_HOST, port=constants.REDIS_PORT, db=constants.REDIS_RABBIT_DB,
            password=constants.REDIS_PASSWORD, username=constants.REDIS_USER
        )
        try:
            # log.info('get_rabbit_queues vhost: [%s], RC.get %s', vhost, _rc.get(name=vhost))
            raw = _rc.get(name=vhost)
            log.info('get_rabbit_queues vhost: [%s], queues: [%s]', vhost, raw)
            queues = json.loads(raw)
        except TypeError:
            return []
        if remove_internal:
            try:
                queues.remove('__internal')
            except ValueError:
                ...
        return queues
