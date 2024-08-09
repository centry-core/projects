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
        user_projects_ids = set(i['id'] for i in user_projects)

        with db.get_session() as session:
            db_groups = session.query(ProjectGroup).join(
                ProjectGroup.projects
            ).filter(Project.id.in_(user_projects_ids)).all()

            groups = []
            projects_with_group = set()

            for g in db_groups:
                g_projects = []
                for p in g.projects.all():
                    if p.id in user_projects_ids:
                        g_projects.append(
                            ProjectMonitoringListModel.from_orm(p).dict()
                        )
                        projects_with_group.add(p.id)
                groups.append(
                    dict(
                        GroupMonitoringListModel.from_orm(g).dict(),
                        projects=g_projects
                    )
                )

            not_grouped_projects_ids = user_projects_ids - projects_with_group
            not_grouped_projects = session.query(Project).filter(Project.id.in_(not_grouped_projects_ids)).all()

            no_group = dict(
                name='no_group',
                projects=[ProjectMonitoringListModel.from_orm(p).dict() for p in not_grouped_projects]
            )
            groups.append(no_group)

            return serialize({
                'projects': [ProjectMonitoringListModel.parse_obj(p).dict() for p in user_projects],
                'groups': groups
            }), 200
