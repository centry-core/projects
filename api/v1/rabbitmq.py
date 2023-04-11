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
        return self.module.get_rabbit_queues(vhost), 200

    def post(self, vhost, **kwargs):
        data = request.json
        res = self.module.register_rabbit_queue(vhost, data["name"])
        return res, 200

    def put(self, vhost, **kwargs):
        log.info('PUT DATA %s', request.json)
        _rc = redis.Redis(
            host=c.REDIS_HOST, port=c.REDIS_PORT, db=4,
            password=c.REDIS_PASSWORD, username=c.REDIS_USER
        )
        for k, v in request.json.items():
            # self.module.update_rabbit_queues(k, json.dumps(v))
            log.info('SETTING REDIS QUEUES FOR [%s], [%s]', k, v)
            _rc.set(name=k, value=json.dumps(v))
        return None, 200

    def patch(self, **kwargs):
        if kwargs.get('mode') == 'administration':
            return list(i[0] for i in Project.query.with_entities(Project.id).all()), 200
        return None, 403
