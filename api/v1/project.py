import json
from queue import Empty
from traceback import format_exc
from typing import Optional, Tuple, List
from flask import request, g
from pylon.core.tools import log

from pydantic import ValidationError

from tools import auth, VaultClient, TaskManager, db, api_tools, db_tools

from sqlalchemy.exc import NoResultFound
from ...models.pd.project import ProjectCreatePD
from ...models.project import Project

from ...utils import get_project_user
from ...utils.project_steps import create_project, get_steps


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["projects.projects.project.view"],
        "recommended_roles": {
            "default": {"admin": True, "viewer": True, "editor": True},
            "developer": {"admin": True, "viewer": True, "editor": True},
        }})
    def get(self, **kwargs) -> tuple[dict, int] | tuple[list, int]:
        user_id = auth.current_user().get("id")
        if not user_id:
            return list(), 200
        #
        offset_ = request.args.get("offset")
        limit_ = request.args.get("limit")
        search_ = request.args.get("search")
        #
        check_public_role = request.args.get("check_public_role")
        projects = self.module.list_user_projects(
            user_id, offset_=offset_, limit_=limit_, search_=search_
        )

        if check_public_role:
            vault_client = VaultClient()
            secrets = vault_client.get_all_secrets()
            try:
                public_project = int(secrets['ai_project_id'])
                public_admin = secrets['ai_public_admin']
                filtered_ids = list()
                for project in projects:
                    if project['id'] == public_project:
                        roles = [role['name'] for role in self.module.context.rpc_manager.timeout(
                            2
                        ).admin_get_user_roles(
                            public_project, user_id
                        )]
                        if public_admin in roles:
                            filtered_ids.append(project['id'])
                projects = [p for p in projects if p['id'] in filtered_ids]
            except KeyError as e:
                log.error(e)
            except Empty as e:
                log.error(e)
        return projects, 200


class AdminAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["projects.projects.project.view"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": True, "editor": True},
        }})
    def get(self, **kwargs) -> tuple[dict, int] | tuple[list, int]:
        user_id = auth.current_user().get("id")
        if not user_id:
            return list(), 200
        #
        offset_ = request.args.get("offset")
        limit_ = request.args.get("limit")
        search_ = request.args.get("search")
        #
        return self.module.list_user_projects(
            user_id, offset_=offset_, limit_=limit_, search_=search_
        ), 200

    @auth.decorators.check_api({
        "permissions": ["projects.projects.project.create"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": False},
            "default": {"admin": False, "viewer": False, "editor": False},
            "developer": {"admin": False, "viewer": False, "editor": False},
        }})
    def post(self, **kwargs) -> tuple[dict, int]:
        # Validate incoming data
        status_code = 201
        try:
            project_model = ProjectCreatePD.parse_obj(request.json)
        except ValidationError as e:
            return e.errors(), 400

        # steps = list(get_steps(self.module))
        context = {
            'project_model': project_model,
            'owner_id': g.auth.id,
            'roles': ['admin', ]
        }
        
        try:
            progress = create_project(self.module, context)

        except Exception as e:
            log.critical(format_exc())
            status_code = 400
        statuses: List[dict] = [step.status['created'] for step in progress]
        return {'steps': statuses}, status_code

    @auth.decorators.check_api({
        "permissions": ["projects.projects.project.edit"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": False},
            "default": {"admin": False, "viewer": False, "editor": False},
            "developer": {"admin": False, "viewer": False, "editor": False},
        }})
    def put(self, project_id: Optional[int] = None) -> Tuple[dict, int]:
        # data = self._parser_post.parse_args()
        data = request.json
        if not project_id:
            return {"message": "Specify project id"}, 400
        project = Project.query.get_or_404(project_id)
        if data["name"]:
            project.name = data["name"]
        if data["owner"]:
            project.owner = data["owner"]
        if data["plugins"]:
            project.plugins = data["plugins"]
        project.commit()
        return project.to_json(exclude_fields=Project.API_EXCLUDE_FIELDS), 200

    @auth.decorators.check_api({
        "permissions": ["projects.projects.project.delete"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": False},
            "default": {"admin": False, "viewer": False, "editor": False},
            "developer": {"admin": False, "viewer": False, "editor": False},
        }})
    def delete(self, project_id: int):
        project = Project.query.get_or_404(project_id)
        try:
            system_user_id = get_project_user(project.id)['id']
        except (RuntimeError, KeyError, NoResultFound):
            system_user_id = None

        context = {
            'project': project,
            'vault_client': VaultClient.from_project(project),
            'system_user_id': system_user_id
        }

        statuses: List[dict] = []
        for step in get_steps(self.module, reverse=True):
            try:
                step.delete(**context)
            except Exception as e:
                log.warning('%s error %s', repr(step), e)
            statuses.append(step.status['deleted'])

        return {'steps': statuses}, 200


class API(api_tools.APIBase):  # pylint: disable=R0903
    url_params = [
        "",
        "<string:mode>",
        "<string:mode>/<int:project_id>",
    ]

    mode_handlers = {
        'administration': AdminAPI,
        'default': ProjectAPI,
    }
