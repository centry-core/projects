from typing import Union


from ..models.project import Project, get_user_projects
from ..models.quota import ProjectQuota
from ..models.statistics import Statistic

from tools import rpc_tools
from pylon.core.tools import web

from ..tools.session_project import SessionProject


class RPC:
    @web.rpc('project_get_or_404', 'get_or_404')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def prj_or_404(self, project_id):
        return Project.get_or_404(project_id)

    @web.rpc('project_list', 'list')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def list_projects(self):
        return Project.list_projects()

    @web.rpc('project_statistics', 'statistics')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_project_statistics(self, project_id):
        return Statistic.query.filter_by(project_id=project_id).first().to_json()

    @web.rpc('add_task_execution', 'add_task_execution')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def add_task_execution(self, project_id):
        statistic = Statistic.query.filter_by(project_id=project_id).first()
        setattr(statistic, 'tasks_executions', Statistic.tasks_executions + 1)
        statistic.commit()

    @web.rpc('project_get_storage_space_quota', 'get_storage_space_quota')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_storage_quota(self, project_id):
        return Project.get_storage_space_quota(project_id=project_id)

    @web.rpc('project_check_quota', 'check_quota')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def check_quota(self, project_id, quota=None):
        return ProjectQuota.check_quota_json(project_id, quota)

    @web.rpc('get_project_id', 'get_project_id')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_project_id(self):
        project_id = SessionProject.get()
        if not project_id:
            project_id = get_user_projects()[0]["id"]
        return project_id

    @web.rpc('set_active_project', 'set_active_project')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def set_active_project(self, project_id: Union[str, int]):
        SessionProject.set(int(project_id))
