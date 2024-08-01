from tools import auth, db, api_tools, serialize

from ...models.project import ProjectGroup


class PromptLibAPI(api_tools.APIModeHandler):
    ...


class API(api_tools.APIBase):  # pylint: disable=R0903
    url_params = api_tools.with_modes([
        "",
    ])

    mode_handlers = {
        "prompt_lib": PromptLibAPI
    }

    def get(self, **kwargs) -> tuple[dict, int]:
        user_id = auth.current_user().get('id')
        user_projects = self.module.list_user_projects(user_id)
        with db.get_session() as session:
            groups = session.query(ProjectGroup).where(
                ProjectGroup.projects.in_(list(set(i['id'] for i in user_projects)))
            ).all()

            return {
                'projects': user_projects,
                'groups': groups
            }, 200

