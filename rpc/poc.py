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
            project_users = self.context.rpc_manager.call.get_users_in_project(
                project["id"])
            #
            log.info("Project users: %s", project_users)
            #
            if user_id in {user["auth_id"] for user in project_users}:
                user_projects.append(project)

        #
        return user_projects
