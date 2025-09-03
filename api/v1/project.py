from queue import Empty
from typing import Optional, Tuple, List
from flask import request, g
from pylon.core.tools import log

import cachetools
from pydantic.v1 import ValidationError

from tools import auth, VaultClient, db, api_tools, db_tools, rpc_tools

from sqlalchemy.exc import NoResultFound
from ...models.pd.project import ProjectCreatePD
from ...models.project import Project

from ...utils import get_project_user
from ...utils.project_steps import create_project, get_steps, ProjectCreateError


def delete_project(project_id: int, module) -> List[dict]:
    with db.with_project_schema_session(None) as session:
        project = session.query(Project).where(Project.id == project_id).first()
        if not project:
            return None, 404
        try:
            system_user_id = get_project_user(project.id)['id']
        except (RuntimeError, KeyError, NoResultFound):
            system_user_id = None

        context = {
            'project': project,
            'vault_client': VaultClient.from_project(project),
            'system_user_id': system_user_id,
            'session': session
        }

        statuses: List[dict] = []
        for step in get_steps(module, reverse=True):
            try:
                step.delete(**context)
                session.commit()
            except Exception as e:
                log.warning('step exc %s %s', repr(step), e)
            statuses.append(step.status['deleted'])

        module.context.event_manager.fire_event('project_deleted', context['project'].to_json())
        return statuses


@cachetools.cached(cache=cachetools.TTLCache(maxsize=20480, ttl=300))
def filter_for_check_public_role(user_id):
    check_public_project_allowed = None
    rpc_timeout = rpc_tools.RpcMixin().rpc.timeout

    vault_client = VaultClient()
    secrets = vault_client.get_all_secrets()
    try:
        public_project_id = int(secrets['ai_project_id'])
        public_admin_role = secrets['ai_public_admin_role']

        def check_public_project_allowed(project) -> bool:
            if project['id'] == public_project_id:
                roles = {role['name'] for role in rpc_timeout(
                    2
                ).admin_get_user_roles(public_project_id, user_id)}
                return public_admin_role in roles
            return True
    except KeyError as e:
        log.info('public_project_id or public_admin_role secrets are not set')
    except Empty as e:
        log.error(e)

    return check_public_project_allowed


def do_project_list(user_id, offset_, limit_, search_, check_public_role, module):
    projects = module.list_user_projects(
        user_id, offset_=offset_, limit_=limit_, search_=search_
    )

    if check_public_role:
        check_public_project_allowed = filter_for_check_public_role(user_id)
        if check_public_project_allowed:
            projects = list(filter(check_public_project_allowed, projects))

    return projects


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

        projects = do_project_list(user_id, offset_, limit_, search_, check_public_role, self.module)
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

        progress = []
        rollback_progress = []
        try:
            progress = create_project(self.module, context)
        except ProjectCreateError as e:
            log.exception('project create')
            status_code = 400
            progress = e.progress
            rollback_progress = e.rollback_progress
        except Exception as e:
            log.exception('project create')
            status_code = 400
        statuses: List[dict] = [step.status['created'] for step in progress]
        rollback_steps: List[dict] = [step.status['deleted'] for step in rollback_progress]
        return {'steps': statuses, 'rollback_steps': rollback_steps}, status_code

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
        user_ids = self.module.context.rpc_manager.call.admin_get_users_ids_in_project(project_id)
        self.module.context.event_manager.fire_event(
            "delete_project", {'project_id': project_id, 'user_ids': user_ids},
        )
        statuses = delete_project(project_id=project_id, module=self.module)
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
