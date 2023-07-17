from typing import Optional

from tools import auth
from tools import rpc_tools
from pylon.core.tools import web
from pylon.core.tools import log


class RPC:
    @web.rpc("list_user_projects", "list_user_projects")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def list_user_projects(self, user_id, **kwargs):
        all_projects = self.list(**kwargs)
        #
        log.info(f"projects {user_id=} {all_projects=}")
        user_projects = list()
        for project in all_projects:
            project_users = self.context.rpc_manager.call.get_users_ids_in_project(
                project["id"])
            #
            log.info("Project users: %s", project_users)
            #
            if user_id in {user["auth_id"] for user in project_users}:
                user_projects.append(project)

        #
        return user_projects

    @web.rpc("add_user_to_project_or_create", "add_user_to_project_or_create")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def add_user_to_project_or_create(
        self, 
        user_email: str,
        project_id: int,
        roles: list,
    ):
        user = None
        user_email = user_email.lower()
        for i in auth.list_users():
            if i['email'] == user_email:
                user = i
                break
        if user:
            project_users = self.context.rpc_manager.call.get_users_ids_in_project(project_id)
            if user['id'] in [u['auth_id'] for u in project_users]:
                return {
                    'msg': f'user {user["email"]} already exists in project {project_id}', 
                    'status': 'error',
                    'email': user["email"]
                    }
            log.info('user %s found. adding to project', user)
            for role in roles:
                self.context.rpc_manager.call.add_user_to_project(
                    project_id, user['id'], role
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
                    
                },]
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
            
            for role in roles:
                self.context.rpc_manager.call.add_user_to_project(
                    project_id, user_id, role
                    )
            return {
                'msg': f'user {user_email} created and added to project {project_id}', 
                'status': 'ok',
                'email': user_email
                }
