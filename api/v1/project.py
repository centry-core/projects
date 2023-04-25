from datetime import datetime
from typing import Optional, Tuple
from flask import request, g
from pylon.core.tools import log

from pydantic import ValidationError
from sqlalchemy import schema

from tools import auth, VaultClient, TaskManager, db, api_tools, db_tools

from ...models.pd.project import ProjectCreatePD
from ...models.project import Project
from ...models.statistics import Statistic
from ...models.quota import ProjectQuota
from ...utils import create_project_influx_databases, drop_project_influx_databases, generate_project_secrets, \
    add_project_token, create_project_user
from ...tools.rabbit_tools import create_project_user_and_vhost
from ...tools.session_plugins import SessionProjectPlugin

PROJECT_ROLE_NAME = 'default'


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["projects.projects.project.view"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": False},
            "default": {"admin": True, "viewer": False, "editor": False},
            "developer": {"admin": True, "viewer": False, "editor": False},
        }})
    def get(self, project_id: int | None = None) -> tuple[dict, int] | tuple[list, int]:
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


class AdminAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["projects.projects.project.view"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": False},
            "default": {"admin": False, "viewer": False, "editor": False},
            "developer": {"admin": False, "viewer": False, "editor": False},
        }})
    def get(self, project_id: int | None = None) -> tuple[dict, int] | tuple[list, int]:
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

    @auth.decorators.check_api({
        "permissions": ["projects.projects.project.create"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": False},
            "default": {"admin": False, "viewer": False, "editor": False},
            "developer": {"admin": False, "viewer": False, "editor": False},
        }})
    def post(self, **kwargs) -> tuple[dict, int]:
        # log.info('do we have an rpc? %s', self.module.context.rpc_manager)
        # Validate incoming data
        try:
            project_model = ProjectCreatePD.parse_obj(request.json)
        except ValidationError as e:
            return e.errors(), 400

        # with db_tools.session.begin():
        # sp = db_tools.session.begin_nested()
        def create_project_model(pd_model: ProjectCreatePD, owner_id: int) -> Project:
            project = Project(
                name=pd_model.name,
                plugins=pd_model.plugins,
                owner_id=owner_id
            )
            project.insert()
            log.info('after project.insert()')
            ProjectQuota.create(
                project_id=project.id,
                vuh_limit=pd_model.vuh_limit,
                storage_space=pd_model.storage_space_limit,
                data_retention_limit=pd_model.data_retention_limit
            )
            log.info('after quota created')

            statistic = Statistic(
                project_id=project.id,
                start_time=str(datetime.utcnow()),
            )
            statistic.insert()
            log.info('after statistic created')
            return project

        project = create_project_model(project_model, g.auth.id)
        # pid = str(project.id)

        # sp.rollback()
        # return f'Project {pid} should not be in db', 400

        SessionProjectPlugin.set(project.plugins)  # this looks bad

        def create_project_schema(project_id: int) -> None:
            with db.with_project_schema_session(project_id) as tenant_db:
                tenant_db.execute(schema.CreateSchema(f"Project-{project_id}"))
                db.get_tenant_specific_metadata().create_all(bind=tenant_db.connection())
                tenant_db.commit()
            log.info("Project schema created")

        # Create project schema
        create_project_schema(project.id)
        project_roles = auth.get_roles(mode=PROJECT_ROLE_NAME)
        project_permissions = auth.get_permissions(mode=PROJECT_ROLE_NAME)
        log.info('after permissions received')

        for role in project_roles:
            self.module.context.rpc_manager.call.add_role(project.id, role["name"])
        log.info('after roles added')

        for permission in project_permissions:
            self.module.context.rpc_manager.call.set_permission_for_role(
                project.id, permission['name'], permission["permission"]
            )
        log.info('after permissions set for roles')

        # #
        # # Auth: create project scope
        # #
        # scope_map = {item["name"]: item["id"] for item in auth.list_scopes()}
        # scope_name = f"Project-{project.id}"
        # #
        # if scope_name not in scope_map:
        #     scope_id = auth.add_scope(scope_name, parent_id=1)
        #     log.info("Created project scope: %s -> %s", scope_name, scope_id)
        # else:
        #     scope_id = scope_map[scope_name]

        #
        # Auth: create project admin
        #
        log.info('adding project admin')
        ROLES = ['admin', ]
        self.module.add_user_to_project_or_create(
            # user_name=project_model.project_admin_email,
            user_email=project_model.project_admin_email,
            project_id=project.id,
            roles=ROLES
        )

        vault_client = VaultClient.from_project(project.id)
        try:
            project_vault_data = vault_client.init_project_space()
        except:
            project_vault_data = {
                "auth_role_id": "",
                "auth_secret_id": ""
            }
            log.warning("Vault is not configured")
        log.info('after vault init_project space')
        project.secrets_json = {
            "vault_auth_role_id": project_vault_data["auth_role_id"],
            "vault_auth_secret_id": project_vault_data["auth_secret_id"],
        }
        # project.worker_pool_config_json = {
        #     "regions": ["default"]
        # }
        project.commit()
        log.info('after project secrets_json set')

        user_id = create_project_user(project_id=project.id)
        log.info('after project tech user is created')
        token = add_project_token(user_id)
        log.info('after tech token issued')
        project_secrets, project_hidden_secrets = generate_project_secrets(project.id)
        project_secrets["auth_token"] = token

        vault_client.set_project_secrets(project_secrets)
        log.info('after set_project_secrets')
        vault_client.set_project_hidden_secrets(project_hidden_secrets)
        log.info('after set_project_hidden_secrets')
        create_project_user_and_vhost(project.id)
        log.info('after create_project_user_and_vhost')
        create_project_influx_databases(project.id)
        log.info('after create_project_influx_databases')

        self.module.context.rpc_manager.timeout(3).check_rabbit_queues()
        log.info('after run rabbit task')
        # self.module.context.rpc_manager.call.populate_backend_runners_table(project.id)

        # Send invitations here
        if project_model.invitation_integration:
            # self.module.context.rpc_manager.timeout(3).handle_invitations(project.id, )
            TaskManager(mode='administration').run_task([{
                'one_recipient': project_model.project_admin_email,
                'one_role': ROLES[0],
                'subject': 'Invitation to a Centry project',
                'debug_sleep': '1'
            }], project_model.invitation_integration)

        return project.to_json(exclude_fields=Project.API_EXCLUDE_FIELDS), 201

    @auth.decorators.check_api({
        "permissions": ["projects.projects.project.edit"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": False},
            "default": {"admin": False, "viewer": False, "editor": False},
            "developer": {"admin": False, "viewer": False, "editor": False},
        }})
    def put(self, project_id: Optional[int] = None) -> Tuple[dict, int]:
        # data = self._parser_post.parse_args()
        data = request.json
        if not project_id:
            return {"message": "Specify project id"}, 400
        project = Project.get_or_404(project_id)
        if data["name"]:
            project.name = data["name"]
        if data["owner"]:
            project.owner = data["owner"]
        if data["plugins"]:
            project.plugins = data["plugins"]
        project.commit()
        return project.to_json(exclude_fields=Project.API_EXCLUDE_FIELDS), 200

    @auth.decorators.check_api({
        "permissions": ["projects.projects.project.delete"],
        "recommended_roles": {
            "administration": {"admin": True, "viewer": False, "editor": False},
            "default": {"admin": False, "viewer": False, "editor": False},
            "developer": {"admin": False, "viewer": False, "editor": False},
        }})
    def delete(self, project_id: int) -> Tuple[dict, int]:
        drop_project_influx_databases(project_id)
        Project.apply_full_delete_by_pk(pk=project_id)
        vault_client = VaultClient.from_project(project_id)
        vault_client.remove_project_space()
        return {"message": f"Project with id {project_id} was successfully deleted"}, 204


class API(api_tools.APIBase):  # pylint: disable=R0903
    url_params = [
        "",
        "<string:mode>",
        "<string:mode>/<int:project_id>",
    ]

    mode_handlers = {
        'administration': AdminAPI,
        'default': ProjectAPI,
    }
