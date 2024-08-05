from tools import auth, db, api_tools, serialize

from ...models.pd.monitoring import GroupMonitoringListModel, ProjectMonitoringListModel
from ...models.project import ProjectGroup, Project


class PromptLibAPI(api_tools.APIModeHandler):
    ...


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        "",
    ])

    mode_handlers = {
        "prompt_lib": PromptLibAPI
    }

    def get(self, **kwargs) -> tuple[dict, int]:
        user_id = auth.current_user().get('id')
        user_projects = self.module.list_user_projects(user_id)
        user_projects_ids = list(set(i['id'] for i in user_projects))

        with db.get_session() as session:
            groups = session.query(ProjectGroup).join(
                ProjectGroup.projects
            ).filter(Project.id.in_(user_projects_ids)).all()

            return serialize({
                'projects': [ProjectMonitoringListModel.parse_obj(p).dict() for p in user_projects],
                'groups': [
                    dict(
                        GroupMonitoringListModel.from_orm(g).dict(),
                        projects=[ProjectMonitoringListModel.from_orm(p).dict() for p in g.projects.all()
                                  if p.id in user_projects_ids]
                    ) for g in groups
                ]
            }), 200
