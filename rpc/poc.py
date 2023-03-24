from tools import auth
from tools import rpc_tools
from pylon.core.tools import web
from pylon.core.tools import log


class RPC:
    @web.rpc("list_user_projects", "list_user_projects")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def list_user_projects(self, user_id, **kwargs):
        all_projects = self.list(**kwargs)
        root_permissions = auth.get_user_permissions(user_id, 1)
        scope_map = {item["name"]:item["id"] for item in auth.list_scopes()}
        #
        user_projects = list()
        #
        for project in all_projects:
            project_scope_id = scope_map.get(f"Project-{project['id']}", 1)
            project_permissions = auth.get_user_permissions(user_id, project_scope_id)
            #
            log.info("Project scope id: %s", project_scope_id)
            log.info("Project permissions: %s", project_permissions)
            #
            if "global_admin" in root_permissions or "project_member" in project_permissions or 'project_admin' in project_permissions:
                user_projects.append(project)
        #
        return user_projects
