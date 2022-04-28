from typing import Optional

from flask import make_response
from flask_restful import Resource

from ...models.project import Project
from ...tools.session_project import SessionProject


class API(Resource):
    def __init__(self, module):
        self.module = module

    def get(self, project_id: Optional[int] = None):
        if not project_id:
            project_id = SessionProject.get()
        if project_id:
            project = Project.get_or_404(project_id, exclude_fields=Project.API_EXCLUDE_FIELDS)
            return make_response(project.to_json(), 200)
        return make_response({"message": "No project selected in session"}, 404)

    def post(self, project_id: int):
        project = Project.get_or_404(project_id)
        SessionProject.set(project.id)
        return make_response(project.id, 200)

    def delete(self, project_id: int):
        project = Project.get_or_404(project_id)
        if SessionProject.get() == project.id:
            SessionProject.pop()
        return make_response('ok', 204)
