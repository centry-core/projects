from flask import request, make_response
from flask_restful import Resource

from ...models.quota import ProjectQuota
from ...models.project import Project

from tools import auth


class API(Resource):
    url_params = [
        '<int:project_id>',
    ]

    def __init__(self, module):
        self.module = module

    @auth.decorators.check_api(["projects.projects.project.view"])
    def get(self, project_id: int):
        project = Project.get_or_404(project_id)
        args = request.args
        return make_response(ProjectQuota.check_quota_json(project.id, args.get("quota")), 200)


    @auth.decorators.check_api(["projects.projects.project.edit"])
    def put(self, project_id: int):
        usage_type = request.args.get('usage_type').lower()
        if usage_type == 'vcu':
            vcu_hard_limit = request.json.get('vcu_hard_limit')
            vcu_soft_limit = request.json.get('vcu_soft_limit')
            vcu_limit_total_block = request.json.get('vcu_limit_total_block')
            project_quota = ProjectQuota.query.filter_by(project_id=project_id).first()
            project_quota.update_vcu_limits(vcu_hard_limit, vcu_soft_limit, vcu_limit_total_block)
            return project_quota.to_json(), 200
        if usage_type == 'storage':
            storage_hard_limit = request.json.get('storage_hard_limit')
            storage_soft_limit = request.json.get('storage_soft_limit')
            storage_limit_total_block = request.json.get('storage_limit_total_block')
            project_quota = ProjectQuota.query.filter_by(project_id=project_id).first()
            project_quota.update_storage_limits(storage_hard_limit, storage_soft_limit, storage_limit_total_block)
            return project_quota.to_json(), 200
