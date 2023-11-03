from pylon.core.tools import web, log


class Event:

    @web.event(f"auth_visitor")
    def personal_project(self, context, event, payload):
        self.visitors[(payload.get('id'), payload.get('type'))] = payload
