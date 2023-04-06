import json
import re
from datetime import datetime
from queue import Empty
from typing import Optional, Union, Tuple
from flask_restful import Resource
from flask import request, g, make_response
from pylon.core.tools import log
from sqlalchemy import schema

from tools import auth, constants as c, VaultClient, TaskManager, db

from ...models.project import Project
from ...models.statistics import Statistic
from ...models.quota import ProjectQuota
from ...tools.influx_tools import create_project_databases, drop_project_databases
from ...tools.rabbit_tools import create_project_user_and_vhost
from ...tools.session_plugins import SessionProjectPlugin

PROJECT_ROLE_NAME = 'project'


class API(Resource):
    url_params = [
        '',
        '<int:project_id>',
    ]

    def __init__(self, module):
        self.module = module

    # @auth.decorators.check_api(['global_view'])
    def get(self, project_id: Optional[int] = None) -> Union[
        Tuple[dict, int], Tuple[list, int]]:
        log.info('g.auth.id %s', g.auth.id)
        if g.auth.id is None:
            return list(), 200
        #
        offset_ = request.args.get("offset")
        limit_ = request.args.get("limit")
        search_ = request.args.get("search")
        #
        return self.module.list_user_projects(
            g.auth.id, offset_=offset_, limit_=limit_, search_=search_
        ), 200

    @auth.decorators.check_api(['global_admin'])
    def post(self, project_id: Optional[int] = None) -> Tuple[dict, int]:
        log.info('request received')
        log.info('do we have an rpc? %s', self.module.context.rpc_manager)
        data = request.json

        #
        # Validate incoming data
        #
        errors = []
        try:
            name_ = data["name"]
            if not name_:
                errors.append('project_name')
        except KeyError:
            errors.append('project_name')
        try:
            project_admin_email = request.json['project_admin_email']
            if not project_admin_email:
                errors.append('project_admin_email')
            if not re.match(r"^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,4})+$",
                            project_admin_email):
                return {
                    "loc": ['project_admin_email', ],
                    "msg": "email is not valid",
                    "type": "value_error.not_allowed"
                }, 400
        except KeyError:
            errors.append('project_admin_email')
        if errors:
            return {
                "loc": errors,
                "msg": "field required",
                "type": "value_error.missing"
            }, 400

        # owner_ = data["owner"]
        owner_ = str(g.auth.id)
        vuh_limit = data["vuh_limit"]
        plugins = data["plugins"]
        storage_space_limit = data["storage_space_limit"]
        data_retention_limit = data["data_retention_limit"]
        # invitations = data['invitations']
        project = Project(
            name=name_,
            plugins=plugins,
            project_owner=owner_
        )
        project_secrets = {}
        project_hidden_secrets = {}
        project.insert()
        log.info('after project.insert()')

        SessionProjectPlugin.set(project.plugins)

        # Create project schema
        with db.with_project_schema_session(project.id) as tenant_db:
            tenant_db.execute(schema.CreateSchema(f"Project-{project.id}"))
            db.get_tenant_specific_metadata().create_all(bind=tenant_db.connection())
            tenant_db.commit()
        log.info("Project schema created")

        project_roles = auth.get_roles(mode=PROJECT_ROLE_NAME)
        project_permissions = auth.get_permissions(mode=PROJECT_ROLE_NAME)

        for role in project_roles:
            self.module.context.rpc_manager.call.add_role(project.id, role["name"])

        for permission in project_permissions:
            self.module.context.rpc_manager.call.set_permission_for_role(
                project.id, permission['name'], permission["permission"]
            )

        #
        # Auth: create project scope
        #
        scope_map = {item["name"]: item["id"] for item in auth.list_scopes()}
        scope_name = f"Project-{project.id}"
        #
        if scope_name not in scope_map:
            scope_id = auth.add_scope(scope_name, parent_id=1)
            log.info("Created project scope: %s -> %s", scope_name, scope_id)
        else:
            scope_id = scope_map[scope_name]

        #
        # Auth: create project admin
        #
        user_map = {item["name"]: item["id"] for item in auth.list_users()}
        if project_admin_email in user_map:
            self.module.context.rpc_manager.call.add_user_to_project(
                project.id, user_map[project_admin_email], 'admin'
            )
        else:
            token = self.module.context.rpc_manager.call.auth_manager_get_token()
            user_data = {
                "username": project_admin_email,
                "email": project_admin_email,
                "enabled": True,
                "totp": False,
                "emailVerified": False,
                "disableableCredentialTypes": [],
                "requiredActions": ["UPDATE_PASSWORD"],
                "notBefore": 0,
                "access": {
                    "manageGroupMembership": True,
                    "view": True,
                    "mapRoles": True,
                    "impersonate": True,
                    "manage": True
                },
                "credentials": [{
                    "type": "password",
                    "value": "11111111",
                    "temporary": True

                }, ]
            }
            user = self.module.context.rpc_manager.call.auth_manager_create_user_representation(
                user_data=user_data
            )
            self.module.context.rpc_manager.call.auth_manager_post_user(realm='carrier',
                                                                        token=token,
                                                                        entity=user
                                                                        )

            user_id = auth.add_user(project_admin_email, project_admin_email)
            #
            auth.add_user_provider(user_id, project_admin_email)
            auth.add_user_group(user_id, 1)
            self.module.context.rpc_manager.call.add_user_to_project(
                project.id, user_id, 'admin'
            )

        def create_project_user(project_id: int) -> int:
            # Auth: create project user
            user_map = {i["name"]: i["id"] for i in auth.list_users()}
            user_name = f":Carrier:Project:{project_id}:"
            user_email = f"{project_id}@special.carrier.project.user"
            #
            try:
                return user_map[user_name]
            except KeyError:
                user_id = auth.add_user(user_email, user_name)
                auth.add_user_permission(user_id, scope_id, "project_member")
                return user_id

        user_id = create_project_user(project_id=project.id)

        def add_project_token(user_id: int) -> str:
            # Auth: add project token
            all_tokens = auth.list_tokens(user_id)
            #
            if len(all_tokens) < 1:
                token_id = auth.add_token(
                    user_id, "api",
                    # expires=datetime.datetime.now()+datetime.timedelta(seconds=30),
                )
            else:
                token_id = all_tokens[0]["id"]
            #
            current_permissions = auth.resolve_permissions(
                scope_id, auth_data=g.auth
            )
            #
            for permission in current_permissions:
                try:
                    auth.add_token_permission(token_id, scope_id, permission)
                except:  # pylint: disable=W0702
                    pass
            #
            return auth.encode_token(token_id)

        token = add_project_token(user_id)

        # invite user to project here
        # self.module.context.rpc_manager.timeout(2).project_keycloak_group_handler(project).send_invitations(
        #     invitations)
        # try:
        #     self.module.context.rpc_manager.timeout(2).project_keycloak_group_handler(project).send_invitations(
        #         invitations)
        # except Empty:
        #     ...

        # permission_name = 'project_admin'
        # # permission_name = 'global_admin'
        # try:
        #     invited_user_id = \
        #         [i for i in auth.list_users() if i['email'] == project_admin_email][0]['id']
        # except IndexError:
        #     invited_user_id = auth.add_user(project_admin_email, '')
        # auth.add_user_permission(invited_user_id, scope_id, permission_name)

        # self.module.context.rpc_manager.call.add_user_to_project(
        #     project.id, invited_user_id, 'admin'
        # )

        # log.info('after invitations sent')

        # SessionProject.set(project.id)  # Looks weird, sorry :D
        ProjectQuota.create(project.id, vuh_limit, storage_space_limit, data_retention_limit)
        log.info('after quota created')
        statistic = Statistic(
            project_id=project.id,
            start_time=str(datetime.utcnow()),
            vuh_used=0,
            performance_test_runs=0,
            sast_scans=0,
            dast_scans=0,
            ui_performance_test_runs=0,
            public_pool_workers=0,
            tasks_executions=0
        )
        statistic.insert()
        log.info('after statistic created')

        project_secrets["galloper_url"] = c.APP_HOST
        project_secrets["project_id"] = project.id
        project_secrets["auth_token"] = token

        project_hidden_secrets["jmeter_db"] = f'jmeter_{project.id}'
        project_hidden_secrets["gatling_db"] = f'gatling_{project.id}'
        project_hidden_secrets["comparison_db"] = f'comparison_{project.id}'
        project_hidden_secrets["telegraf_db"] = f'telegraf_{project.id}'

        vault_client = VaultClient.from_project(project.id)
        try:
            project_vault_data = vault_client.init_project_space()
        except:
            project_vault_data = {
                "auth_role_id": "",
                "auth_secret_id": ""
            }
            log.warning("Vault is not configured")
        log.info('after init_project space')
        project.secrets_json = {
            "vault_auth_role_id": project_vault_data["auth_role_id"],
            "vault_auth_secret_id": project_vault_data["auth_secret_id"],
        }
        project.worker_pool_config_json = {
            "regions": ["default"]
        }
        project.commit()

        vault_client.set_project_secrets(project_secrets)
        log.info('after set_project_secrets')
        vault_client.set_project_hidden_secrets(project_hidden_secrets)
        log.info('after set_project_hidden_secrets')
        create_project_user_and_vhost(project.id)
        log.info('after create_project_user_and_vhost')
        create_project_databases(project.id)
        log.info('after create_project_databases')

        # self.module.context.rpc_manager.call.create_rabbit_schedule(
        #     f"rabbit_queue_scheduler_for_project_{project.id}",
        #     project.id
        # )

        # schedules = self.module.context.rpc_manager.call.get_schedules()
        # if "rabbit_public_queue_scheduler" not in [i.name for i in schedules]:
            # self.module.context.rpc_manager.call.check_rabbit_queues(
            #     project.id,
            #     rabbit_queue_checker.task_id
            # )
            # self.module.context.rpc_manager.call.create_rabbit_schedule(
            #     f"rabbit_public_queue_scheduler",
            #     project.id,
            #     rabbit_queue_checker.task_id
            # )

        # set_grafana_datasources(project.id)
        self.module.context.rpc_manager.timeout(3).check_rabbit_queues()
        self.module.context.rpc_manager.call.populate_backend_runners_table(project.id)
        return project.to_json(exclude_fields=Project.API_EXCLUDE_FIELDS), 201

    @auth.decorators.check_api(['global_admin'])
    def put(self, project_id: Optional[int] = None) -> Tuple[dict, int]:
        # data = self._parser_post.parse_args()
        data = request.json
        if not project_id:
            return {"message": "Specify project id"}, 400
        project = Project.get_or_404(project_id)
        if data["name"]:
            project.name = data["name"]
        if data["owner"]:
            project.project_owner = data["owner"]
        if data["plugins"]:
            project.plugins = data["plugins"]
        project.commit()
        return project.to_json(exclude_fields=Project.API_EXCLUDE_FIELDS), 200

    @auth.decorators.check_api(['global_admin'])
    def delete(self, project_id: int) -> Tuple[dict, int]:
        drop_project_databases(project_id)
        Project.apply_full_delete_by_pk(pk=project_id)
        vault_client = VaultClient.from_project(project_id)
        vault_client.remove_project_space()
        return {"message": f"Project with id {project_id} was successfully deleted"}, 204
