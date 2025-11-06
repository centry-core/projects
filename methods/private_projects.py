#!/usr/bin/python3
# coding=utf-8

#   Copyright 2025 EPAM Systems
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

""" Method """

import queue
import threading

import cachetools  # pylint: disable=E0401

from pylon.core.tools import log  # pylint: disable=E0611,E0401,W0611
from pylon.core.tools import web  # pylint: disable=E0611,E0401,W0611

from ..constants import PROJECT_USER_NAME_PREFIX
from ..rpc.poc import create_personal_project


class Method:  # pylint: disable=E1101,R0903,W0201
    """
        Method Resource

        self is pointing to current Module instance

        web.method decorator takes zero or one argument: method name
        Note: web.method decorator must be the last decorator (at top)
    """

    @web.init()
    def private_projects(self):
        """ Method """
        self.visitors_queue = queue.SimpleQueue()
        self.visitors_queue_get_timeout = 1
        #
        self.visitors_cache = cachetools.TTLCache(maxsize=20480, ttl=300)
        #
        self.visitors_processor_thread = threading.Thread(
            target=self.visitors_processor,
            daemon=True,
        )
        self.visitors_processor_thread.start()

    @web.method()
    def visitors_processor(self):
        """ Method """
        log.info("Visitors processor thread started")
        #
        while not self.context.stop_event.is_set():
            try:
                visitor = self.visitors_queue.get(timeout=self.visitors_queue_get_timeout)
                #
                self.process_visitor(visitor)
            except queue.Empty:
                pass
            except:  # pylint: disable=W0702
                log.exception("Error during visitor processing, skipping")

    @web.method()
    def process_visitor(self, visitor):
        """ Method """
        if not isinstance(visitor.get("id", ""), int):
            return
        #
        user_id = visitor["id"]
        #
        with self.projects_lock:
            if user_id in self.visitors_cache:
                return
            #
            self.visitors_cache[user_id] = visitor
        #
        if visitor.get("type", "") == "token":
            try:
                user_id = self.context.rpc_manager.call.auth_get_token(user_id)["user_id"]
                user_name = self.context.rpc_manager.call.auth_get_user(user_id)["name"]
                #
                if user_name.startswith(PROJECT_USER_NAME_PREFIX):
                    log.warning(f"Skipping to create personal project for {user_name}")
                    return
            except:  # pylint: disable=W0702
                log.exception("Failed to get user from token. Skipping")
                return
        #
        project_created = False
        #
        with self.projects_lock:
            log.info("Creating private project for user ID (if not exists): %s", user_id)
            #
            if create_personal_project(user_id=user_id, module=self) is True:
                self.invalidate_user_caches(user_id)
                project_created = True
        #
        if project_created:
            project_id = self.get_personal_project_id(user_id)
            #
            self.context.event_manager.event_manager.fire_event(
                "notifications_stream", {
                    "project_id": project_id,
                    "user_id": user_id,
                    "meta": {},
                    "event_type": "private_project_created",
                }
            )
