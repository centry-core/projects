from typing import List, Literal

from sqlalchemy import not_
from ..models.pd.group import GroupListModel
from ..models.pd.monitoring import GroupMonitoringListModel, ProjectMonitoringListModel
from ..models.pd.project import ProjectListModel
from ..models.project import Project, ProjectGroup

from tools import rpc_tools, db, serialize, config as c
from pylon.core.tools import web, log


class RPC:
    @web.rpc('project_get_available_projects_in_group', 'get_available_projects_in_group')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_available_projects_in_group(self, user_id: int, group_id: int | Literal[c.NO_GROUP_NAME]) -> List[dict]:
        with db.get_session() as session:
            user_projects = self.list_user_projects(user_id)
            user_projects_ids = [i['id'] for i in user_projects]
            if group_id == c.NO_GROUP_NAME:
                projects = session.query(Project).filter(
                    Project.id.in_(user_projects_ids),
                    not_(Project.groups.any())
                ).all()
            else:
                projects = session.query(Project).filter(
                    Project.id.in_(user_projects_ids),
                    Project.groups.any(id=group_id)
                ).all()

            log.info(f'project_get_available_projects_in_group\n{[ProjectListModel.from_orm(i).dict() for i in projects]}')

            return [ProjectListModel.from_orm(i).dict() for i in projects]

    @web.rpc('project_get_available_groups', 'get_available_groups')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_available_groups(self, user_id: int) -> List[dict]:
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

    @web.rpc('project_get_all_groups', 'get_all_groups')
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_all_groups(self, name_filter: str = None) -> List[dict]:
        filters = list()
        if name_filter:
            filters.append(ProjectGroup.name.ilike(f"%{name_filter}%"))

        with (db.get_session() as session):
            query = session.query(ProjectGroup).all()

            if filters:
                query = query.filter(*filters)

            project_with_group = [
                serialize(GroupListModel.from_orm(group)) for group in query
            ]
        return project_with_group
