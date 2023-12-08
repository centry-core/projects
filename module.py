#   Copyright 2021 getcarrier.io
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

""" Module """

from collections import defaultdict
from queue import Empty

import flask

from pylon.core.tools import module, log  # pylint: disable=E0611,E0401
from pylon.core.tools.context import Context as Holder

from .models.project import Project
from sqlalchemy.exc import ProgrammingError
from tools import db_migrations, config as c  # pylint: disable=E0401
from .utils.rabbit_utils import fix_rabbit_vhost


class Module(module.ModuleModel):
    def __init__(self, context, descriptor):
        self.context = context
        self.descriptor = descriptor

        self.visitors = defaultdict(dict)  # use for creating personal projects for each user

    def init(self):
        """ Init module """
        log.info("Initializing module Projects")
        from . import constants as pc
        self.descriptor.register_tool('project_constants', {i: getattr(pc, i) for i in dir(pc) if not i.startswith('_')})

        # try:
        #     # Run DB migrations
        #     db_migrations.run_db_migrations(self, c.DATABASE_URI)
        # except ProgrammingError as e:
        #     log.info(e)

        from .tools import session_plugins, session_project, influx_tools
        self.descriptor.register_tool('session_plugins', session_plugins.SessionProjectPlugin)
        self.descriptor.register_tool('session_project', session_project.SessionProject)
        self.descriptor.register_tool('influx_tools', influx_tools)
        # self.descriptor.register_tool('rabbit_tools', rabbit_tools)

        from .init_db import init_db
        init_db()

        self.descriptor.init_api()
        self.descriptor.init_events()
        self.descriptor.init_rpcs()

        self.context.app.before_request(self._before_request_hook)

        try:
            self.create_scheduling()
        except Empty:
            ...
        # self.descriptor.register_tool('projects', self)

        # rabbit_tools.create_administration_user_and_vhost()

        for p in Project.query.all():
            try:
                fix_rabbit_vhost(p)
            except:
                log.warning('Couldn\'t fix rabbit for project %s', p)



    def deinit(self):  # pylint: disable=R0201
        """ De-init module """
        log.info("De-initializing module")

    def _before_request_hook(self):
        flask.g.project = Holder()
        flask.g.project.id = self.get_id()  # comes from RPC


    def create_scheduling(self):
        schedule_data = {
            'name': 'projects_create_personal_project',
            'cron': '*/5 * * * *',
            'rpc_func': 'projects_create_personal_project',
            'active': False
        }
        self.context.rpc_manager.timeout(5).scheduling_create_if_not_exists(schedule_data)
