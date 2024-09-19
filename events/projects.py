from pylon.core.tools import web, log


class Event:

    @web.event(f"auth_visitor")
    def personal_project(self, context, event, payload):
        self.visitors[(payload.get('id'), payload.get('type'))] = payload

    @web.event(f"delete_project")
    def delete_project(self, context, event, payload):
        project_id, user_ids = payload.get('project_id'), payload.get('user_ids')
        self.clear_user_projects_cache(
            user_ids
        )

    @web.event(f"user_added_to_project")
    def user_added_to_project(self, context, event, payload):
        project_id, user_ids = payload.get('project_id'), payload.get('user_ids')
        self.clear_user_projects_cache(
            user_ids
        )

    @web.event(f"user_removed_from_project")
    def user_removed_from_project(self, context, event, payload):
        project_id, user_ids = payload.get('project_id'), payload.get('user_ids')
        self.clear_user_projects_cache(
            user_ids
        )
