from flask import request
from tools import auth, db, api_tools, serialize

from pydantic.v1 import ValidationError
from ...models.pd.group import GroupModifyModel
from ...models.pd.project import ProjectListModel
from ...models.project import ProjectGroup, Project


class PromptLibAPI(api_tools.APIModeHandler):
    ...


class API(api_tools.APIBase):  # pylint: disable=R0903
    url_params = api_tools.with_modes([
        "",
        "<int:project_id>",
    ])

    mode_handlers = {
        "prompt_lib": PromptLibAPI
    }

    def get(self, **kwargs):
        q = request.args.get('query')
        project_with_group = self.module.get_all_groups(name_filter=q)
        return project_with_group, 200

    @auth.decorators.check_api({
        "permissions": ["projects.projects.groups.edit"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": True},
            "default": {"admin": True, "viewer": False, "editor": True},
            "developer": {"admin": True, "viewer": False, "editor": True},
        }})
    def put(self, project_id: int, **kwargs) -> tuple[dict, int]:
        raw = dict(request.json)
        raw['project_id'] = project_id

        try:
            parsed = GroupModifyModel.parse_obj(raw)
        except ValidationError:
            return {"error": "Can not validate data"}, 400

        with db.get_session() as session:
            project = session.query(Project).filter(
                Project.id == parsed.project_id
            ).first()
            if project is None:
                return {"error": "Project was not found"}, 400

            groups = session.query(ProjectGroup).filter(
                ProjectGroup.name.in_(parsed.groups)
            ).all()

            group_names = {group.name for group in groups}
            new_group_names = set(parsed.groups) - group_names
            new_groups = [ProjectGroup(name=name) for name in new_group_names]
            if new_groups:
                session.add_all(new_groups)
                session.commit()
                groups.extend(new_groups)

            old_group_names = {g.name for g in project.groups}
            project.groups = groups

            session.commit()
            serialized = serialize(ProjectListModel.from_orm(project))

            if old_group_names != group_names:
                self.module.clear_user_projects_cache(
                    self.module.context.rpc_manager.call.admin_get_users_ids_in_project(project_id)
                )

        return serialized, 200
