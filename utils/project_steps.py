from datetime import datetime

from sqlalchemy import schema
from sqlalchemy.exc import NoResultFound
from . import get_project_user
from .helpers import ProjectCreationStep
from .rabbit_utils import password_generator, create_rabbit_user_and_vhost, \
    delete_rabbit_user_and_vhost
from ..constants import INFLUX_DATABASES, PROJECT_SCHEMA_TEMPLATE, PROJECT_USER_NAME_TEMPLATE, \
    PROJECT_USER_EMAIL_TEMPLATE, PROJECT_RABBIT_USER_TEMPLATE, PROJECT_RABBIT_VHOST_TEMPLATE

from ..models.pd.project import ProjectCreatePD
from ..models.project import Project
from ..models.quota import ProjectQuota
from ..models.statistics import Statistic

from ..tools.influx_tools import get_client

from pylon.core.tools import log
from tools import db, VaultClient, auth, constants as c


class ProjectModel(ProjectCreationStep):
    name = 'project_model'

    def create(self, pd_model: ProjectCreatePD, owner_id: int) -> Project:
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

    def delete(self, project_id: int, **kwargs) -> None:
        Statistic.query.filter(Statistic.project_id == project_id).delete()
        Statistic.commit()
        log.info('statistic deleted')

        ProjectQuota.query.filter(ProjectQuota.project_id == project_id).delete()
        ProjectQuota.commit()
        log.info('quota deleted')

        Project.query.get(project_id).delete()
        Project.commit()
        log.info('project deleted')


class ProjectSchema(ProjectCreationStep):
    name = 'project_schema'

    def create(self, project_id: int) -> None:
        with db.with_project_schema_session(project_id) as tenant_db:
            tenant_db.execute(schema.CreateSchema(PROJECT_SCHEMA_TEMPLATE.format(project_id)))
            db.get_tenant_specific_metadata().create_all(bind=tenant_db.connection())
            tenant_db.commit()

    def delete(self, project_id: int, **kwargs) -> None:
        with db.with_project_schema_session(project_id) as tenant_db:
            # db.get_tenant_specific_metadata().drop_all(bind=tenant_db.connection())
            tenant_db.execute(schema.DropSchema(PROJECT_SCHEMA_TEMPLATE.format(project_id), cascade=True))
            tenant_db.commit()


class SystemUser(ProjectCreationStep):
    name = 'system_user'

    def create(self, project_id: int) -> int:
        # Auth: create project user
        try:
            user = get_project_user(project_id)
            return user['id']
        except (NoResultFound, RuntimeError):
            ...
        user_name = PROJECT_USER_NAME_TEMPLATE.format(project_id)
        user_email = PROJECT_USER_EMAIL_TEMPLATE.format(project_id)
        user_id = auth.add_user(user_email, user_name)
        auth.assign_user_to_role(user_id, "system", mode='administration')
        return user_id

    def delete(self, system_user_id: int, **kwargs):
        auth.delete_user(system_user_id)


class SystemToken(ProjectCreationStep):
    name = 'system_token'

    def create(self, system_user_id: int) -> str:
        # Auth: add project token
        all_tokens = auth.list_tokens(system_user_id)
        #
        if len(all_tokens) < 1:
            token_id = auth.add_token(
                system_user_id, "api",
                # expires=datetime.datetime.now()+datetime.timedelta(seconds=30),
            )
        else:
            token_id = all_tokens[0]["id"]
        #
        return auth.encode_token(token_id)

    def delete(self, system_user_id: int, **kwargs) -> None:
        for i in auth.list_tokens(system_user_id):
            auth.delete_token(i['id'])


class ProjectSecrets(ProjectCreationStep):
    name = 'project_secrets'

    def create(self, project: Project, system_token: str) -> VaultClient:
        vault_client = VaultClient.from_project(project)
        project_vault_data = vault_client.create_project_space()
        log.info('after vault init_project space')
        project.secrets_json = project_vault_data.dict(by_alias=True)
        project.commit()
        log.info('after project secrets_json set')

        project_secrets = {
            'backend_performance_results_retention': vault_client.get_all_secrets().get(
                'backend_performance_results_retention',
                c.BACKEND_PERFORMANCE_RESULTS_RETENTION
            )
        }

        project_hidden_secrets = {
            k: v.format(project.id) for k, v in INFLUX_DATABASES.items()
        }
        project_hidden_secrets['project_id'] = project.id
        project_secrets["auth_token"] = system_token

        vault_client.set_secrets(project_secrets)
        log.info('after set_secrets')
        vault_client.set_hidden_secrets(project_hidden_secrets)
        log.info('after set_hidden_secrets')

        return VaultClient.from_project(project)

    def delete(self, project: Project, **kwargs) -> None:
        VaultClient.from_project(project).remove_project_space()


class RabbitVhost(ProjectCreationStep):
    name = 'rabbit_vhost'

    def create(self, vault_client: VaultClient) -> None:
        all_secrets = vault_client.get_all_secrets()

        # prepare user credentials
        user = PROJECT_RABBIT_USER_TEMPLATE.format(vault_client.project_id)
        password = password_generator()
        vhost = PROJECT_RABBIT_VHOST_TEMPLATE.format(vault_client.project_id)

        create_rabbit_user_and_vhost(
            rabbit_admin_url='http://carrier-rabbit:15672',
            rabbit_admin_auth=(all_secrets["rabbit_user"], all_secrets["rabbit_password"]),
            user=user,
            password=password,
            vhost=vhost
        )

        # set project secrets
        secrets = vault_client.get_secrets()
        secrets["rabbit_project_user"] = user
        secrets["rabbit_project_password"] = password
        secrets["rabbit_project_vhost"] = vhost
        vault_client.set_secrets(secrets)

    def delete(self, vault_client: VaultClient, **kwargs) -> None:
        all_secrets = vault_client.get_all_secrets()
        secrets = vault_client.get_secrets()
        delete_rabbit_user_and_vhost(
            rabbit_admin_url='http://carrier-rabbit:15672',
            rabbit_admin_auth=(all_secrets["rabbit_user"], all_secrets["rabbit_password"]),
            user=secrets["rabbit_project_user"],
            vhost=secrets["rabbit_project_vhost"]
        )


class InfluxDatabases(ProjectCreationStep):
    name = 'influx_databases'

    def create(self, vault_client: VaultClient) -> None:
        # vault_client = VaultClient.from_project(project_id)
        secrets = vault_client.get_all_secrets()
        client = get_client(vault_client.project_id, secrets=secrets)
        for i in INFLUX_DATABASES.keys():
            db_name = secrets.get(i)
            client.query(
                f"create database {db_name} with duration 180d replication 1 shard duration 7d name autogen"
            )

    def delete(self, vault_client: VaultClient, **kwargs) -> None:
        # vault_client = VaultClient.from_project(project_id)
        secrets = vault_client.get_all_secrets()
        client = get_client(vault_client.project_id, secrets=secrets)
        for i in INFLUX_DATABASES.keys():
            db_name = secrets.get(i)
            client.query(f"drop database {db_name}")


# We initialize classes to form project creation sequence
steps = [
    ProjectModel(),
    ProjectSchema(),
    SystemUser(),
    SystemToken(),
    ProjectSecrets(),
    RabbitVhost(),
    InfluxDatabases(),
]
