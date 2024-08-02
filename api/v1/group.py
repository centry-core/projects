from flask import request
from pydantic import ValidationError

from tools import auth, db, api_tools, serialize

from ...models.pd.project import ProjectListModel
from ...models.pd.group import GroupModifyModel
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
                groups.extend(new_groups)

            for group in groups:
                if group not in project.groups:
                    project.groups.append(group)

            session.commit()
            serialized = serialize(ProjectListModel.from_orm(project))
        return serialized, 201

    @auth.decorators.check_api({
        "permissions": ["projects.projects.project_group.delete"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": True},
            "default": {"admin": True, "viewer": False, "editor": True},
            "developer": {"admin": True, "viewer": False, "editor": True},
        }})
    def delete(self, project_id: int):
        raw = dict(request.json)
        raw['project_id'] = project_id

        try:
            parsed = GroupModifyModel.parse_obj(raw)
        except ValidationError:
            return {"error": "Can not validate data"}, 400

        with db.get_session() as session:
            project = session.query(Project).filter_by(id=project_id).first()
            groups = session.query(ProjectGroup).filter(
                ProjectGroup.name.in_(parsed.groups)
            ).all()

            if project and groups:
                for group in groups:
                    try:
                        if group in project.groups:
                            project.groups.remove(group)
                    except ValueError:
                        pass
                session.commit()
            else:
                return {"error": "Project or Group not found"}, 400
        return {}, 204


class API(api_tools.APIBase):  # pylint: disable=R0903
    url_params = api_tools.with_modes([
        "<int:project_id>",
    ])

    mode_handlers = {
        "prompt_lib": PromptLibAPI
    }
