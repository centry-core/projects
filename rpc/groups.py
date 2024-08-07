from typing import List

from ..models.pd.monitoring import GroupMonitoringListModel, ProjectMonitoringListModel
from ..models.pd.project import ProjectListModel
from ..models.project import Project, ProjectGroup

from tools import rpc_tools, db, serialize
from pylon.core.tools import web, log


class RPC:
    @web.rpc('project_get_available_projects_in_group', 'get_available_projects_in_group')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_available_projects_in_group(self, user_id: int, group_id: int) -> List[dict]:
        with db.get_session() as session:
            user_projects = self.list_user_projects(user_id)
            user_projects_ids = [i['id'] for i in user_projects]
            projects = session.query(Project).filter(
                Project.id.in_(user_projects_ids)
            ).filter(
                Project.groups.any(id=group_id)
            ).all()
            return [ProjectListModel.from_orm(i).dict() for i in projects]

    @web.rpc('project_get_available_groups', 'get_available_groups')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_available_groups(self, user_id: int):
        user_projects = self.list_user_projects(user_id)
        user_projects_ids = set(i['id'] for i in user_projects)

        with db.get_session() as session:
            groups = session.query(ProjectGroup).join(
                ProjectGroup.projects
            ).filter(Project.id.in_(user_projects_ids)).all()

            return [
                dict(
                    GroupMonitoringListModel.from_orm(g).dict(),
                    projects=[
                        ProjectMonitoringListModel.from_orm(p).dict()
                        for p in g.projects.all()
                        if p.id in user_projects_ids
                    ]
                ) for g in groups
            ]
