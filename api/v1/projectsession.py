#     Copyright 2020 getcarrier.io
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
from typing import Optional, Tuple

# from ...shared.utils.restApi import RestResource
# from ...shared.utils.api_utils import build_req_parser
# from ...shared.connectors.auth import (SessionProject, SessionUser)
from flask import make_response
from flask_restful import Resource

from ...models.project import Project
from ...tools.session_project import SessionProject


class API(Resource):
    def __init__(self, module):
        self.module = module
    # post_rules = (
    #     dict(name="username", type=str, required=True, location="json"),
    #     dict(name="groups", type=list, required=True, location="json")
    # )
    #
    # def __init__(self):
    #     super().__init__()
    #     self.__init_req_parsers()
    #
    # def __init_req_parsers(self):
    #     self._parser_post = build_req_parser(rules=self.post_rules)

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
