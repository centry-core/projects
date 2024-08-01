from flask import request
from tools import auth, db, api_tools, serialize

from ...models.pd.project_group import ProjectGroupListModel
from ...models.project import ProjectGroup


class PromptLibAPI(api_tools.APIModeHandler):
    def get(self, **kwargs):
        filters = list()
        q = request.args.get('query')
        if q:
            filters.append(ProjectGroup.name.ilike(f"%{q}%"))

        with (db.get_session() as session):
            query = session.query(ProjectGroup).all()

            if filters:
                query = query.filter(*filters)

            project_with_group = [
                serialize(ProjectGroupListModel.from_orm(group)) for group in query
            ]
        return project_with_group, 201


class API(api_tools.APIBase):  # pylint: disable=R0903
    url_params = api_tools.with_modes([
        "",
    ])

    mode_handlers = {
        "prompt_lib": PromptLibAPI
    }
