from flask import request
from pydantic import ValidationError

from tools import auth, db, api_tools, serialize

from ...models.pd.project_group import ProjectGroupModel
from ...models.project import ProjectGroup, Project


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["projects.projects.project_group.create"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": True},
            "default": {"admin": True, "viewer": False, "editor": True},
            "developer": {"admin": True, "viewer": False, "editor": True},
        }})
    def post(self, project_id: int, **kwargs) -> tuple[dict, int]:
        raw = dict(request.json)
        raw['project_id'] = project_id

        try:
            parsed = ProjectGroupModel.parse_obj(raw)
        except ValidationError:
            return {"error": "Can not validate data"}, 400

        with db.get_session() as session:
            project = session.query(Project).filter(
                Project.id == parsed.project_id
            ).first()
            if project is None:
                return {"error": "Project was not found"}, 400

            group = session.query(ProjectGroup).filter(
                ProjectGroup.name == parsed.name
            ).first()
            if group is None:
                group = ProjectGroup(name=parsed.name)
            if group not in project.groups:
                project.groups.append(group)

            session.commit()
            project_with_group = project.to_json(exclude_fields=Project.API_EXCLUDE_FIELDS)
            serialized = serialize(project_with_group)
        return serialized, 201

    @auth.decorators.check_api({
        "permissions": ["projects.projects.project_group.delete"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": True},
            "default": {"admin": True, "viewer": False, "editor": True},
            "developer": {"admin": True, "viewer": False, "editor": True},
        }})
    def delete(self, project_id: int, group_id: int):
        with db.get_session() as session:
            project = session.query(Project).filter_by(id=project_id).first()
            group = session.query(ProjectGroup).filter_by(id=group_id).first()

            if project and group:
                try:
                    project.groups.remove(group)
                    session.commit()
                except ValueError:
                    pass
            else:
                return {"error": "Project or Group not found"}, 400
        return {}, 204


class API(api_tools.APIBase):  # pylint: disable=R0903
    url_params = api_tools.with_modes([
        "<int:project_id>",
        "<int:project_id>/<int:group_id>",
    ])

    mode_handlers = {
        "prompt_lib": PromptLibAPI
    }
