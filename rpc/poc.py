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
        user_name: str, 
        user_email: str, 
        project_id: int, 
        roles: list
        ):
        user_map = {item["name"]: item["id"] for item in auth.list_users()}
        if user_name in user_map:
            for role in roles:
                self.context.rpc_manager.call.add_user_to_project(
                    project_id, user_map[user_name], role
                )
            return f'user {user_name} added to project {project_id}'
        else:
            token = self.context.rpc_manager.call.auth_manager_get_token()
            user_data = {
                "username": user_name,
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
            user = self.context.rpc_manager.call.auth_manager_create_user_representation(
                user_data=user_data)
            self.context.rpc_manager.call.auth_manager_post_user(
                realm='carrier', token=token, entity=user)            
            
            user_id = auth.add_user(user_name, user_email)
            auth.add_user_provider(user_id, user_name)
            auth.add_user_group(user_id, 1)
            
            for role in roles:
                self.context.rpc_manager.call.add_user_to_project(
                    project_id, user_id, role
                    )
            return f'user {user_name} created and added to project {project_id}'
