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

import flask  # pylint: disable=E0401
import jinja2  # pylint: disable=E0401

from pylon.core.tools import log  # pylint: disable=E0611,E0401
from pylon.core.tools import module  # pylint: disable=E0611,E0401
from pylon.core.tools.context import Context as Holder
from sqlalchemy.exc import ProgrammingError
from tools import db_migrations, db  # pylint: disable=E0401
#
# from tools import config


class Module(module.ModuleModel):
    """ Galloper module """

    def __init__(self, context, descriptor):
        self.context = context
        self.descriptor = descriptor

    def init(self):
        """ Init module """
        log.info("Initializing module Projects")
        try:
            # Run DB migrations
            db_migrations.run_db_migrations(self, db.url)
        except ProgrammingError as e:
            log.info(e)

        from .tools import session_plugins, session_project, influx_tools, grafana_tools, secrets_tools, rabbit_tools
        self.descriptor.register_tool('session_plugins', session_plugins.SessionProjectPlugin)
        self.descriptor.register_tool('session_project', session_project.SessionProject)
        self.descriptor.register_tool('influx_tools', influx_tools)
        self.descriptor.register_tool('grafana_tools', grafana_tools)
        self.descriptor.register_tool('secrets_tools', secrets_tools)
        self.descriptor.register_tool('rabbit_tools', rabbit_tools)

        from .init_db import init_db
        init_db()

        self.descriptor.init_api()

        self.descriptor.init_rpcs()

        self.context.app.before_request(self._before_request_hook)

        # self.descriptor.register_tool('projects', self)

    def deinit(self):  # pylint: disable=R0201
        """ De-init module """
        log.info("De-initializing module")

    def _before_request_hook(self):
        flask.g.project = Holder()
        flask.g.project.id = self.get_id()  # comes from RPC
