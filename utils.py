from typing import Tuple, Optional

from datetime import datetime
from sqlalchemy import schema

from .constants import INFLUX_DATABASES, PROJECT_USER_EMAIL_TEMPLATE, PROJECT_USER_NAME_TEMPLATE
from .models.pd.project import ProjectCreatePD
from .models.project import Project
from .models.statistics import Statistic
from .models.quota import ProjectQuota
from .tools.influx_tools import get_client
from .tools.rabbit_tools import create_project_user_and_vhost

from pylon.core.tools import log
from tools import VaultClient, auth, constants as c, db


def create_project_influx_databases(project_id: int) -> None:
    vault_client = VaultClient.from_project(project_id)
    secrets = vault_client.get_all_secrets()
    client = get_client(project_id)
    for i in INFLUX_DATABASES.keys():
        db_name = secrets.get(i)
        client.query(
            f"create database {db_name} with duration 180d replication 1 shard duration 7d name autogen")


def drop_project_influx_databases(project_id: int) -> None:
    vault_client = VaultClient.from_project(project_id)
    secrets = vault_client.get_all_secrets()
    client = get_client(project_id)
    for i in INFLUX_DATABASES.keys():
        db_name = secrets.get(i)
        client.query(f"drop database {db_name}")


def get_project_user(project_id: int) -> Optional[dict]:
    user_email = PROJECT_USER_EMAIL_TEMPLATE.format(project_id)
    for i in auth.list_users():
        if i['email'] == user_email:
            return i
    return


def create_project_user(project_id: int) -> int:
    # Auth: create project user
    user = get_project_user(project_id)
    if user:
        return user['id']
    user_name = PROJECT_USER_NAME_TEMPLATE.format(project_id)
    user_email = PROJECT_USER_EMAIL_TEMPLATE.format(project_id)
    user_id = auth.add_user(user_email, user_name)
    auth.assign_user_to_role(user_id, "system", mode='administration')
    return user_id


def delete_project_user(project_id: int) -> int:
    user = get_project_user(project_id)
    assert user, f'project user {project_id} not found'
    auth.auth_delete_user(user['id'])
    return user['id']


def create_project_token(user_id: int) -> str:
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
    return auth.encode_token(token_id)


def delete_project_token(user_id: int) -> None:
    for i in auth.list_tokens(user_id):
        auth.delete_token(i['id'])


def generate_project_secrets(project_id: int) -> Tuple[dict, dict]:
    project_secrets = {
        'galloper_url': c.APP_HOST,
        'project_id': project_id,
    }

    project_hidden_secrets = {
        k: v.format(project_id) for k, v in INFLUX_DATABASES.items()
    }

    return project_secrets, project_hidden_secrets


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


def create_project_schema(project_id: int) -> None:
    with db.with_project_schema_session(project_id) as tenant_db:
        tenant_db.execute(schema.CreateSchema(f"Project-{project_id}"))
        db.get_tenant_specific_metadata().create_all(bind=tenant_db.connection())
        tenant_db.commit()
    log.info("Project schema created")


def create_project_secrets(vault_client: 'VaultClient', auth_token: str):
    project_secrets, project_hidden_secrets = generate_project_secrets(vault_client.project_id)
    project_secrets["auth_token"] = auth_token

    vault_client.set_project_secrets(project_secrets)
    log.info('after set_project_secrets')
    vault_client.set_project_hidden_secrets(project_hidden_secrets)
    log.info('after set_project_hidden_secrets')
    create_project_user_and_vhost(vault_client.project_id)
    log.info('after create_project_user_and_vhost')
    create_project_influx_databases(vault_client.project_id)
    log.info('after create_project_influx_databases')
