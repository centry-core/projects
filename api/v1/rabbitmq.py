from flask import request
from flask_restful import Resource

from pylon.core.tools import web, log


class API(Resource):
    url_params = [
        '<string:vhost>',
    ]

    def __init__(self, module):
        self.module = module

    def get(self, vhost):
        return self.module.get_rabbit_queues(vhost), 200

    def post(self, vhost):
        data = request.json
        res = self.module.register_rabbit_queue(vhost, data["name"])
        return res, 200

    def put(self, vhost):
        data = request.json
        res = self.module.update_rabbit_queues(vhost, data["queues"])
        return res, 200
