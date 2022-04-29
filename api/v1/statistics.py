from flask import make_response
from flask_restful import Resource

from ...models.statistics import Statistic
from ...models.quota import ProjectQuota


class API(Resource):
    url_params = [
        '<int:project_id>',
    ]

    def __init__(self, module):
        self.module = module

    def get(self, project_id: int):
        statistic = Statistic.query.filter_by(project_id=project_id).first().to_json()
        quota = ProjectQuota.query.filter_by(project_id=project_id).first().to_json()
        stats = {}
        for each in ["performance_test_runs", "ui_performance_test_runs", "sast_scans", "dast_scans", "storage_space",
                     "tasks_count", "tasks_executions"]:

            stats[each] = {"current": statistic[each], "quota": quota[each]}
        stats["data_retention_limit"] = {"current": 0, "quota": quota["data_retention_limit"]}
        return make_response(stats, 200)
