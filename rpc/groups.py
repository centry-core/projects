from typing import List

from ..models.pd.project import ProjectListModel
from ..models.project import Project

from tools import rpc_tools, db
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
