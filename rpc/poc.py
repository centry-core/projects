from collections import defaultdict
import re
from traceback import format_exc
from typing import Optional

from tools import auth
from tools import rpc_tools
from tools import config as c
from pylon.core.tools import web
from pylon.core.tools import log

from ..models.project import Project
from ..models.pd.project import ProjectCreatePD
from ..utils.project_steps import create_project
from ..constants import PROJECT_PERSONAL_NAME_TEMPLATE, PROJECT_USER_EMAIL_TEMPLATE


class RPC:
    @web.rpc("list_user_projects", "list_user_projects")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def list_user_projects(self, user_id: int, **kwargs) -> list:
        all_projects = self.list(**kwargs)
        # log.info(f"projects {user_id=} {all_projects=}")
        user_projects = list()
        for project in all_projects:
            if self.context.rpc_manager.call.admin_check_user_in_project(project["id"], user_id):
                user_projects.append(project)
        return user_projects

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
                'email': user["email"]
            }
        else:
            log.info('user %s not found. creating user', user_email)
            keycloak_token = self.context.rpc_manager.call.auth_manager_get_token()
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
                    "value": "11111111",
                    "temporary": True

                }, ]
            }
            log.info('creating keycloak entry')
            user = self.context.rpc_manager.call.auth_manager_create_user_representation(
                user_data=user_data
            )
            self.context.rpc_manager.call.auth_manager_post_user(
                realm='carrier', token=keycloak_token, entity=user
            )
            log.info('after keycloak')

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
                'email': user_email
            }

    @web.rpc("projects_create_personal_project", "create_personal_project")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def create_personal_project(self) -> None:
        for user_data in self.visitors.values():
            if not isinstance(user_data.get('id', ''), int):
                continue

            user_id = user_data['id']
            if user_data.get('type', '') == 'token':
                user_id = self.context.rpc_manager.call.auth_get_token(user_data['id'])['user_id']

            project_name = PROJECT_PERSONAL_NAME_TEMPLATE.format(user_id=user_id)
            projects = Project.list_projects()
            if any(project['name'] == project_name for project in projects):
                continue

            project_model = ProjectCreatePD(
                name=project_name,
                project_admin_email=self.context.rpc_manager.call.auth_get_user(user_id)['email'],
                plugins=['configuration', 'models']
            )

            context = {
                'project_model': project_model,
                'owner_id': user_id,
                'roles': ['editor', 'viewer']
            }

            try:
                create_project(self, context)
                log.info(f'Personal project {project_name} created')

            except Exception:
                log.critical(format_exc())

        self.visitors = defaultdict(dict)

    @web.rpc("projects_get_personal_project_id", "get_personal_project_id")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def get_personal_project_id(self, user_id: int) -> None:
        if not user_id:
            return
        project_name = PROJECT_PERSONAL_NAME_TEMPLATE.format(user_id=user_id)
        project = Project.query.filter(Project.name == project_name).first()

        if project and self.context.rpc_manager.call.admin_check_user_in_project(project.id, user_id):
            return project.id

        if not project:
            if user:= auth.get_user(user_id=user_id):
                system_user_email = PROJECT_USER_EMAIL_TEMPLATE.format(r'(\d+)')
                match = re.match(rf"^{system_user_email}$", user['email'])
                if match:
                    return int(match.groups()[0])
