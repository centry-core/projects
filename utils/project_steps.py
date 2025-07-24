from datetime import datetime
from typing import Optional

from pylon.core.tools import log
from sqlalchemy import schema
from sqlalchemy.exc import NoResultFound
from tools import db, VaultClient, auth, constants as c, MinioClient

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


class ProjectModel(ProjectCreationStep):
    name = 'project_model'

    def create(self, project_model: ProjectCreatePD, owner_id: int, session, **kwargs) -> dict[str, Project]:
        project = Project(
            name=project_model.name,
            plugins=project_model.plugins,
            owner_id=owner_id
        )
        session.add(project)
        session.commit()
        log.info('after project.insert')
        quota = ProjectQuota(
            project_id=project.id,
            data_retention_limit=project_model.data_retention_limit,
            test_duration_limit=project_model.test_duration_limit,
            cpu_limit=project_model.cpu_limit,
            memory_limit=project_model.memory_limit,
            vcu_hard_limit=project_model.vcu_hard_limit,
            vcu_soft_limit=project_model.vcu_soft_limit,
            vcu_limit_total_block=project_model.vcu_limit_total_block,
            storage_hard_limit=project_model.storage_hard_limit,
            storage_soft_limit=project_model.storage_soft_limit,
            storage_limit_total_block=project_model.storage_limit_total_block
        )
        session.add(quota)
        session.commit()
        log.info('after quota created')

        statistic = Statistic(
            project_id=project.id,
            start_time=str(datetime.utcnow()),
        )
        session.add(statistic)
        session.commit()
        log.info('after statistic created')
        return {'project': project}

    def delete(self, project: Project, session, **kwargs) -> None:
        session.query(Statistic).filter(Statistic.project_id == project.id).delete()
        session.commit()
        log.info('statistic deleted')

        session.query(ProjectQuota).filter(ProjectQuota.project_id == project.id).delete()
        session.commit()
        log.info('quota deleted')

        # session.query(Project).where(Project.id == project.id).delete()
        session.delete(project)
        session.commit()
        log.info('project deleted')


class MinioBuckets(ProjectCreationStep):
    name = 'minio_buckets'

    def create(self, project: Project, **kwargs) -> None:
        mc = MinioClient(project)
        mc.create_bucket(bucket='reports', bucket_type='system')
        mc.create_bucket(bucket='tasks', bucket_type='system')

    def delete(self, project: Project, **kwargs) -> None:
        mc = MinioClient(project)
        mc.remove_bucket('reports')
        mc.remove_bucket('tasks')


class ProjectSchema(ProjectCreationStep):
    name = 'project_schema'

    def create(self, project: Project, **kwargs) -> None:
        with db.with_project_schema_session(project.id) as tenant_db:
            tenant_db.execute(schema.CreateSchema(PROJECT_SCHEMA_TEMPLATE.format(project.id)))
            db.get_tenant_specific_metadata().create_all(bind=tenant_db.connection())
            tenant_db.commit()

    def delete(self, project: Project, **kwargs) -> None:
        try:
            with db.with_project_schema_session(project.id) as tenant_db:
                tenant_db.execute(schema.DropSchema(PROJECT_SCHEMA_TEMPLATE.format(project.id), cascade=True))
                tenant_db.commit()
        except Exception as e:
            log.warning(f'Drop schema exception {e}')


class ProjectPermissions(ProjectCreationStep):
    name = 'project_permissions'

    def create(self, project: Project, **kwargs) -> None:
        project_roles = auth.get_roles(mode='default')
        project_permissions = auth.get_permissions(mode='default')
        self.module.context.rpc_manager.call.admin_add_role(project.id, [i["name"] for i in project_roles])
        for permission in project_permissions:
            self.module.context.rpc_manager.call.admin_set_permission_for_role(
                project.id, permission['name'], permission["permission"]
            )

    def delete(self, **kwargs) -> None:
        ...


class SystemUser(ProjectCreationStep):
    name = 'system_user'

    def create(self, project: Project, **kwargs) -> dict:
        # Auth: create project user
        try:
            user = get_project_user(project.id)
            return user['id']
        except (NoResultFound, RuntimeError):
            ...
        user_name = PROJECT_USER_NAME_TEMPLATE.format(project.id)
        user_email = PROJECT_USER_EMAIL_TEMPLATE.format(project.id)
        user_id = auth.add_user(user_email, user_name)
        auth.assign_user_to_role(
            user_id=user_id,
            role_name='system',
            mode=c.DEFAULT_MODE,
            project_id=project.id
        )
        return {'system_user_id': user_id}

    def delete(self, system_user_id: int, **kwargs) -> None:
        auth.delete_user(system_user_id)


class SystemToken(ProjectCreationStep):
    name = 'system_token'

    def create(self, system_user_id: int, **kwargs) -> dict:
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
        return {'system_token': auth.encode_token(token_id)}

    def delete(self, system_user_id: Optional[int] = None, **kwargs) -> None:
        if system_user_id:
            for i in auth.list_tokens(user_id=system_user_id):
                auth.delete_token(token_id=i['id'])


class ProjectSecrets(ProjectCreationStep):
    name = 'project_secrets'

    def create(self, project: Project, system_token: str, session, **kwargs) -> dict[str, VaultClient]:
        vault_client = VaultClient.from_project(project)
        project_vault_data = vault_client.create_project_space()
        project.secrets_json = project_vault_data.dict(by_alias=True)
        session.add(project)
        session.commit()

        project_secrets = {
            # 'backend_performance_results_retention': vault_client.get_all_secrets().get(
            #     'backend_performance_results_retention',
            #     c.BACKEND_PERFORMANCE_RESULTS_RETENTION
            # )
        }

        project_hidden_secrets = {
            k: v.format(project.id) for k, v in INFLUX_DATABASES.items()
        }
        project_hidden_secrets['project_id'] = project.id
        project_secrets["auth_token"] = system_token

        vault_client.set_secrets(project_secrets)
        vault_client.set_hidden_secrets(project_hidden_secrets)

        return {'vault_client': VaultClient.from_project(project)}

    def delete(self, project: Project, **kwargs) -> None:
        VaultClient.from_project(project).remove_project_space()


class RabbitVhost(ProjectCreationStep):
    name = 'rabbit_vhost'

    def create(self, vault_client: VaultClient, **kwargs) -> None:
        if c.ARBITER_RUNTIME != "rabbitmq":
            return

        all_secrets = vault_client.get_all_secrets()

        # prepare user credentials
        user = PROJECT_RABBIT_USER_TEMPLATE.format(vault_client.project_id)
        password = password_generator()
        vhost = PROJECT_RABBIT_VHOST_TEMPLATE.format(vault_client.project_id)

        create_rabbit_user_and_vhost(
            rabbit_admin_url=c.RABBIT_ADMIN_URL,
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
        if c.ARBITER_RUNTIME != "rabbitmq":
            return
        all_secrets = vault_client.get_all_secrets()
        secrets = vault_client.get_secrets()
        delete_rabbit_user_and_vhost(
            rabbit_admin_url=c.RABBIT_ADMIN_URL,
            rabbit_admin_auth=(all_secrets["rabbit_user"], all_secrets["rabbit_password"]),
            user=secrets["rabbit_project_user"],
            vhost=secrets["rabbit_project_vhost"]
        )


class InfluxDatabases(ProjectCreationStep):
    name = 'influx_databases'

    def create(self, vault_client: VaultClient, **kwargs) -> None:
        if not c.CENTRY_USE_INFLUX:
            return
        # vault_client = VaultClient.from_project(project_id)
        secrets = vault_client.get_all_secrets()
        client = get_client(vault_client.project_id, secrets=secrets)
        for i in INFLUX_DATABASES.keys():
            db_name = secrets.get(i)
            client.query(
                f"create database {db_name} with duration 180d replication 1 shard duration 7d name autogen"
            )

    def delete(self, vault_client: VaultClient, **kwargs) -> None:
        if not c.CENTRY_USE_INFLUX:
            return
        # vault_client = VaultClient.from_project(project_id)
        secrets = vault_client.get_all_secrets()
        client = get_client(vault_client.project_id, secrets=secrets)
        for i in INFLUX_DATABASES.keys():
            db_name = secrets.get(i)
            client.query(f"drop database {db_name}")


class ProjectAdmin(ProjectCreationStep):
    name = 'project_admin'

    def create(self, project_model: ProjectCreatePD, project: Project, roles: list[str], **kwargs) -> None:
        self.module.add_user_to_project_or_create(
            # user_name=project_model.project_admin_email,
            user_email=project_model.project_admin_email,
            project_id=project.id,
            roles=roles
        )

    def delete(self, **kwargs) -> None:
        ...


# class Invitations(ProjectCreationStep):
#     name = 'invitations'
#
#     def create(self, project_model: ProjectCreatePD, **kwargs) -> None:
#         if project_model.invitation_integration:
#             log.info(f'sending invitation {project_model.invitation_integration=}')
#             invitation_integration = json.loads(
#                 project_model.invitation_integration.replace("'", '"').replace('None', 'null'))
#             if invitation_integration:
#                 try:
#                     email_integration = self.module.context.rpc_manager.timeout(1).integrations_get_by_id(
#                         invitation_integration['smtp_integration']['project_id'],
#                         invitation_integration['smtp_integration']['id'],
#                     )
#                     try:
#                         from tools import TaskManager
#                         TaskManager(mode='administration').run_task([{
#                             'recipients': [project_model.project_admin_email],
#                             'subject': 'Invitation to a Centry project',
#                             'template': invitation_integration['template'],
#                         }], email_integration.task_id)
#                     except ImportError:
#                         ...
#                 except Empty:
#                     ...
#
#     def delete(self, **kwargs) -> None:
#         ...


# We initialize classes to form project creation sequence


def get_steps(module=None, reverse: bool = False):
    steps = [
        ProjectModel,
        MinioBuckets,
        ProjectSchema,
        ProjectPermissions,
        SystemUser,
        SystemToken,
        ProjectSecrets,
        RabbitVhost,
        InfluxDatabases,
        ProjectAdmin,
        # Invitations
    ]
    if reverse:
        steps = reversed(steps)
    for step in steps:
        yield step(module)


class ProjectCreateError(Exception):
    def __init__(self, progress: list, rollback_progress: Optional[list] = None):
        self.progress = progress
        self.rollback_progress = rollback_progress or []


def create_project(module, context: dict, rollback_on_error: bool = True) -> list:
    progress = []
    with db.with_project_schema_session(None) as session:
        context['session'] = session
        try:
            for step in get_steps(module):
                progress.append(step)
                step_result = step.create(**context)
                if step_result is not None:
                    if isinstance(step_result, dict):
                        context.update(step_result)
                    else:
                        context[step.name] = step_result
        except Exception as e:
            log.exception('create_project')
            session.rollback()
            rollback_progress = []
            if rollback_on_error:
                for step in reversed(progress):
                    step.delete(**context)
                    rollback_progress.append(step)
            raise ProjectCreateError(progress, rollback_progress)
        context['project'].create_success = True
        session.commit()
        module.context.event_manager.fire_event('project_created', context['project'].to_json())
    return progress
