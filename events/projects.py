from pylon.core.tools import web, log


class Event:

    @web.event(f"auth_visitor")
    def personal_project(self, context, event, payload):
        self.visitors[(payload.get('id'), payload.get('type'))] = payload

    @web.event(f"delete_project")
    def delete_project(self, context, event, payload):
        project_id = payload.get('project_id')
        user_ids = self.context.rpc_manager.call.admin_get_users_ids_in_project(project_id)
        self.clear_user_projects_cache(
            user_ids
        )
