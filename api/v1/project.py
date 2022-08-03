import json
from datetime import datetime
from queue import Empty
from typing import Optional, Union, Tuple
from flask_restful import Resource
from flask import request, g, make_response
from pylon.core.tools import log

from tools import auth, constants as c, secrets_tools

from ...models.project import Project
from ...models.statistics import Statistic
from ...models.quota import ProjectQuota
from ...tools.influx_tools import create_project_databases, drop_project_databases
from ...tools.rabbit_tools import create_project_user_and_vhost


class API(Resource):
    url_params = [
        '',
        '<int:project_id>',
    ]

    def __init__(self, module):
        self.module = module

    # @auth.decorators.check_api(['global_view'])
    def get(self, project_id: Optional[int] = None) -> Union[Tuple[dict, int], Tuple[list, int]]:
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
        name_ = data["name"]
        # owner_ = data["owner"]
        owner_ = str(g.auth.id)
        vuh_limit = data["vuh_limit"]
        plugins = data["plugins"]
        storage_space_limit = data["storage_space_limit"]
        data_retention_limit = data["data_retention_limit"]
        invitations = data['invitations']
        project = Project(
            name=name_,
            plugins=plugins,
            project_owner=owner_
        )
        project_secrets = {}
        project_hidden_secrets = {}
        project.insert()
        log.info('after project.insert()')

        #
        # Auth: create project scope
        #
        scope_map = {item["name"]:item["id"] for item in auth.list_scopes()}
        scope_name = f"Project-{project.id}"
        #
        if scope_name not in scope_map:
            scope_id = auth.add_scope(scope_name, parent_id=1)
            log.info("Created project scope: %s -> %s", scope_name, scope_id)
        else:
            scope_id = scope_map[scope_name]

        #
        # Auth: create project user
        #
        user_map = {item["name"]:item["id"] for item in auth.list_users()}
        user_name = f":Carrier:Project:{project.id}:"
        user_email = f"{project.id}@special.carrier.project.user"
        #
        if user_name not in user_map:
            user_id = auth.add_user(user_email, user_name)
            auth.add_user_permission(user_id, scope_id, "project_member")
        else:
            user_id = user_map[user_name]

        #
        # Auth: add project token
        #
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
        token = auth.encode_token(token_id)

        try:
            self.module.context.rpc_manager.timeout(2).project_keycloak_group_handler(project).send_invitations(
                invitations)
        except Empty:
            ...

        log.info('after invitations sent')
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
        pp_args = {
            "funcname": "post_processor",
            "invoke_func": "lambda_function.lambda_handler",
            "runtime": "Python 3.7",
            "region": "default",
            "env_vars": json.dumps({
                "influx_host": "{{secret.influx_ip}}",
                "influx_user": "{{secret.influx_user}}",
                "influx_password": "{{secret.influx_password}}",
                "remove_row_data": "false",
                "jmeter_db": "{{secret.jmeter_db}}",
                "gatling_db": "{{secret.gatling_db}}",
                "comparison_db": "{{secret.comparison_db}}"
            })
        }
        pp = self.module.context.rpc_manager.call.task_create(project, c.POST_PROCESSOR_PATH, pp_args)
        log.info('after pp task created')
        cc_args = {
            "funcname": "control_tower",
            "invoke_func": "lambda.handler",
            "runtime": "Python 3.7",
            "region": "default",
            "env_vars": json.dumps({
                "token": "{{secret.auth_token}}",
                "galloper_url": "{{secret.galloper_url}}",
                "GALLOPER_WEB_HOOK": '{{secret.post_processor}}',
                "project_id": '{{secret.project_id}}',
                "loki_host": '{{secret.loki_host}}'
            })
        }
        cc = self.module.context.rpc_manager.call.task_create(project, c.CONTROL_TOWER_PATH, cc_args)
        log.info('after cc task created')
        rabbit_queue_checker_args = {
            "funcname": "rabbit_queue_checker",
            "invoke_func": "lambda.handler",
            "runtime": "Python 3.7",
            "region": "default",
            "env_vars": json.dumps({
                "token": "{{secret.auth_token}}",
                "galloper_url": "{{secret.galloper_url}}",
                "project_id": '{{secret.project_id}}',
                "rabbit_host": '{{secret.rabbit_host}}',
                "rabbit_project_user": '{{secret.rabbit_project_user}}',
                "rabbit_project_password": '{{secret.rabbit_project_password}}',
                "rabbit_project_vhost": '{{secret.rabbit_project_vhost}}',
                "AWS_LAMBDA_FUNCTION_TIMEOUT": 120
            })
        }
        rabbit_queue_checker = self.module.context.rpc_manager.call.task_create(project, c.RABBIT_TASK_PATH,
                                                                                rabbit_queue_checker_args)
        log.info('after rabbit_scheduler task created')
        project_secrets["galloper_url"] = c.APP_HOST
        project_secrets["project_id"] = project.id
        project_secrets["auth_token"] = token
        project_hidden_secrets["post_processor"] = f'{c.APP_HOST}{pp.webhook}'
        project_hidden_secrets["post_processor_id"] = pp.task_id
        project_hidden_secrets["redis_host"] = c.APP_IP
        project_hidden_secrets["loki_host"] = c.EXTERNAL_LOKI_HOST.replace("https://", "http://")
        project_hidden_secrets["influx_ip"] = c.APP_IP
        project_hidden_secrets["influx_port"] = c.INFLUX_PORT
        project_hidden_secrets["loki_port"] = c.LOKI_PORT
        project_hidden_secrets["redis_password"] = c.REDIS_PASSWORD
        project_hidden_secrets["rabbit_host"] = c.APP_IP
        project_hidden_secrets["rabbit_user"] = c.RABBIT_USER
        project_hidden_secrets["rabbit_password"] = c.RABBIT_PASSWORD
        project_hidden_secrets["control_tower_id"] = cc.task_id
        project_hidden_secrets["rabbit_queue_validator_id"] = rabbit_queue_checker.task_id
        project_hidden_secrets["influx_user"] = c.INFLUX_USER
        project_hidden_secrets["influx_password"] = c.INFLUX_PASSWORD
        project_hidden_secrets["jmeter_db"] = f'jmeter_{project.id}'
        project_hidden_secrets["gatling_db"] = f'gatling_{project.id}'
        project_hidden_secrets["comparison_db"] = f'comparison_{project.id}'
        project_hidden_secrets["telegraf_db"] = f'telegraf_{project.id}'
        project_hidden_secrets["gf_api_key"] = c.GF_API_KEY

        project_vault_data = {
            "auth_role_id": "",
            "auth_secret_id": ""
        }
        try:
            project_vault_data = secrets_tools.init_project_space(project.id)
        except:
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

        secrets_tools.set_project_secrets(project.id, project_secrets)
        log.info('after set_project_secrets')
        secrets_tools.set_project_hidden_secrets(project.id, project_hidden_secrets)
        log.info('after set_project_hidden_secrets')
        create_project_user_and_vhost(project.id)
        log.info('after create_project_user_and_vhost')
        create_project_databases(project.id)
        log.info('after create_project_databases')

        self.module.context.rpc_manager.call.create_rabbit_schedule(f"rabbit_queue_scheduler_for_project_{project.id}",
                                                                    project.id)
        schedules = self.module.context.rpc_manager.call.get_schedules()
        if "rabbit_public_queue_scheduler" not in [i.name for i in schedules]:
            self.module.context.rpc_manager.call.check_rabbit_queues(project.id, rabbit_queue_checker.task_id)
            self.module.context.rpc_manager.call.create_rabbit_schedule(f"rabbit_public_queue_scheduler", project.id,
                                                                        rabbit_queue_checker.task_id)

        # set_grafana_datasources(project.id)
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
        secrets_tools.remove_project_space(project_id)
        return {"message": f"Project with id {project_id} was successfully deleted"}, 204
