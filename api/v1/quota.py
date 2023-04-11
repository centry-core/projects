from flask import request, make_response
from flask_restful import Resource

from ...models.quota import ProjectQuota
from ...models.project import Project


class API(Resource):
    url_params = [
        '<int:project_id>',
    ]

    def __init__(self, module):
        self.module = module

    def get(self, project_id: int):
        project = Project.get_or_404(project_id)
        args = request.args
        return make_response(ProjectQuota.check_quota_json(project.id, args.get("quota")), 200)

