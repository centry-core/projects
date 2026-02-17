import json

from flask import request

import redis
from pylon.core.tools import web, log
from tools import api_tools, constants as c

from ...models.project import Project


class API(api_tools.APIBase):
    url_params = [
        '<string:vhost>',
        '<string:mode>/<string:vhost>',
    ]

    def get(self, vhost, **kwargs):
        log.warning("Endpoint disabled")
        return "Endpoint disabled", 410

    def post(self, vhost, **kwargs):
        log.warning("Endpoint disabled")
        return "Endpoint disabled", 410

    def put(self, vhost, **kwargs):
        log.warning("Endpoint disabled")
        return "Endpoint disabled", 410

    def patch(self, **kwargs):
        log.warning("Endpoint disabled")
        return "Endpoint disabled", 410
