import time
from collections import defaultdict
import re
from traceback import format_exc

from tools import auth
from tools import rpc_tools
from tools import db
from tools import context
from pylon.core.tools import web
from pylon.core.tools import log

import cachetools
from ..api.v1.project import delete_project
from ..models.project import Project
from ..models.pd.project import ProjectCreatePD
from ..utils.project_steps import create_project
from ..constants import (
    PROJECT_PERSONAL_NAME_TEMPLATE,
    PROJECT_USER_EMAIL_TEMPLATE,
    PROJECT_USER_NAME_PREFIX
)


def create_keycloak_user(user_email: str, *, rpc_manager, default_password: str = "11111111") -> None:
    if "auth_manager" not in context.module_manager.modules:
        return
    #
    keycloak_token = rpc_manager.call.auth_manager_get_token()
    user_data = {
        "username": user_email,
        "email": user_email,
        "enabled": True,
        "totp": False,
        "emailVerified": False,
        "disableableCredentialTypes": [],
        "requiredActions": ["UPDATE_PASSWORD"],
        "notBefore": 0,
        "access": {
            "manageGroupMembership": True,
            "view": True,
            "mapRoles": True,
            "impersonate": True,
            "manage": True
        },
        "credentials": [{
            "type": "password",
            "value": default_password,
            "temporary": True
        }, ]
    }
    log.info('creating keycloak entry')
    user = rpc_manager.call.auth_manager_create_user_representation(
        user_data=user_data
    )
    rpc_manager.call.auth_manager_post_user(
        realm='carrier', token=keycloak_token, entity=user
    )
    log.info('after keycloak')


def create_personal_project(user_id: int,
                            module,
                            plugins: list = ('configuration', 'models'),
                            roles: list = ('editor', 'viewer')
                            ):
    project_name = PROJECT_PERSONAL_NAME_TEMPLATE.format(user_id=user_id)
    with db.with_project_schema_session(None) as session:
        p = session.query(Project).where(Project.name == project_name).first()
    if not p:
        project_model = ProjectCreatePD(
            name=project_name,
            project_admin_email=module.context.rpc_manager.call.auth_get_user(user_id)['email'],
            plugins=list(plugins)
        )

        context = {
            'project_model': project_model,
            'owner_id': user_id,
            'roles': list(roles)
        }

        try:
            create_project(module, context)
            log.info(f'Personal project {project_name} created')
        except Exception:
            log.critical(format_exc())


def is_system_user(email: str) -> bool:
    system_user_email = PROJECT_USER_EMAIL_TEMPLATE.format(r'(\d+)')
    match = re.match(rf"^{system_user_email}$", email)
    return bool(match)


user_projects_cache = cachetools.LRUCache(maxsize=128)


class RPC:
    @web.rpc("list_user_projects", "list_user_projects")
    @rpc_tools.wrap_exceptions(RuntimeError)
    @cachetools.cached(cache=user_projects_cache)
    def list_user_projects(self, user_id: int, **kwargs) -> list:
        all_projects = self.list(**kwargs)
        #
        user_projects = []
        check_ids = []
        project_map = {}
        #
        for project in all_projects:
            check_ids.append(project["id"])
            project_map[project["id"]] = project
        #
        user_in_ids = self.context.rpc_manager.call.admin_check_user_in_projects(check_ids, user_id)
        #
        for project_id in user_in_ids:
            user_projects.append(project_map[project_id])
        #
        time.sleep(3)
        return user_projects

    @web.rpc("clear_user_projects_cache", "clear_user_projects_cache")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def clear_user_projects_cache(self, user_ids):
        for cached_key in list(user_projects_cache.keys()):
            cached_func, cached_user_id = cached_key
            if cached_user_id in user_ids:
                user_projects_cache.pop(cached_key)

    @web.rpc("add_user_to_project_or_create", "add_user_to_project_or_create")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def add_user_to_project_or_create(
            self,
            user_email: str,
            project_id: int,
            roles: list[str],
    ):
        user = None
        user_email = user_email.lower()
        for i in auth.list_users():
            if i['email'] == user_email:
                user = i
                break
        if user:
            project_users = self.context.rpc_manager.call.admin_get_users_ids_in_project(project_id)
            user_exists = False
            for user_id in project_users:
                if user['id'] == user_id:
                    user_exists = True
                    break
            if user_exists:
                return {
                    'msg': f'user {user["email"]} already exists in project {project_id}',
                    'status': 'error',
                    'email': user["email"]
                }
            log.info('user %s found. adding to project', user)
            self.context.rpc_manager.call.admin_add_user_to_project(
                project_id, user['id'], roles
            )
            return {
                'msg': f'user {user["email"]} added to project {project_id}',
                'status': 'ok',
                'id': user['id'],
                'email': user["email"]
            }
        else:
            log.info('user %s not found. creating user', user_email)
            try:
                create_keycloak_user(user_email, rpc_manager=self.context.rpc_manager)
            except Exception as e:
                log.warning(f'Keycloak user cannot be created {e}')

            user_id = auth.add_user(user_email)
            # auth.add_user_provider(user_id, user_name)
            auth.add_user_provider(user_id, user_email)
            auth.add_user_group(user_id, 1)

            self.context.rpc_manager.call.admin_add_user_to_project(
                project_id, user_id, roles
            )
            return {
                'msg': f'user {user_email} created and added to project {project_id}',
                'status': 'ok',
                'id': user_id,
                'email': user_email
            }

    @web.rpc("projects_create_personal_project", "create_personal_project")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def create_personal_project_from_visitors(self) -> None:
        for user_data in self.visitors.values():
            if not isinstance(user_data.get('id', ''), int):
                continue

            user_id = user_data['id']
            if user_data.get('type', '') == 'token':
                try:
                    user_id = self.context.rpc_manager.call.auth_get_token(user_data['id'])['user_id']
                    user_name = self.context.rpc_manager.call.auth_get_user(user_id)['name']
                    if user_name.startswith(PROJECT_USER_NAME_PREFIX):
                        log.warning(f"Skipping to create personal project for {user_name}")
                        continue
                except:
                    log.exception("Failed to get user from token. Skipping")
                    continue

            create_personal_project(user_id=user_id, module=self)
        self.visitors = defaultdict(dict)

    @web.rpc("projects_fix_create_personal_projects", "fix_create_personal_projects")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def fix_create_personal_projects(self) -> None:
        for user in auth.list_users():
            # log.info(f'{user=}')
            # log.info(f'{is_system_user(user["email"])=}')
            if not is_system_user(user["email"]):
                project_name = PROJECT_PERSONAL_NAME_TEMPLATE.format(user_id=user['id'])
                with db.with_project_schema_session(None) as session:
                    project = session.query(Project).where(Project.name == project_name).first()
                    if not project:
                        create_personal_project(user_id=user['id'], module=self)
                    elif not project.create_success:
                        delete_project(project_id=project.id, module=self)
                        create_personal_project(user_id=user['id'], module=self)
                    else:
                        ...

    @web.rpc("projects_get_personal_project_id", "get_personal_project_id")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_personal_project_id(self, user_id: int) -> int | None:
        if not user_id:
            return
        project_name = PROJECT_PERSONAL_NAME_TEMPLATE.format(user_id=user_id)
        with db.with_project_schema_session(None) as session:
            project = session.query(Project).where(Project.name == project_name).first()

            if project and self.context.rpc_manager.call.admin_check_user_in_project(project.id, user_id):
                return project.id

            if not project:
                if user := auth.get_user(user_id=user_id):
                    system_user_email = PROJECT_USER_EMAIL_TEMPLATE.format(r'(\d+)')
                    match = re.match(rf"^{system_user_email}$", user['email'])
                    if match:
                        return int(match.groups()[0])

    @web.rpc("projects_get_personal_project_ids", "get_personal_project_ids")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_personal_project_ids(self) -> list[int]:
        projects_name = PROJECT_PERSONAL_NAME_TEMPLATE.format(user_id='%')
        projects = Project.query.with_entities(Project.id).filter(
            Project.name.like(projects_name)).all()
        return [project_data[0] for project_data in projects]

    @web.rpc()
    @rpc_tools.wrap_exceptions(RuntimeError)
    def create_project(self, project_name, plugins, admin_email, owner_id, roles):
        project_model = ProjectCreatePD(
            name=project_name,
            project_admin_email=admin_email,
            plugins=plugins,
        )
        #
        project_context = {
            "project_model": project_model,
            "owner_id": owner_id,
            "roles": roles,
        }
        #
        try:
            create_project(self, project_context)
        except:  # pylint: disable=W0702
            log.exception("Failed to create public project")
            return None
        #
        project = Project.query.filter(Project.name == project_name).first()
        #
        if project:
            return project.id
        #
        return None
