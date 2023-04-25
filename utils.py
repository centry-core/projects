from typing import Tuple

from pylon.core.tools import log

from .constants import INFLUX_DATABASES
from .tools.influx_tools import get_client

from tools import VaultClient, auth, constants as c


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
        # auth.add_user_permission(user_id, scope_id, "project_member") #  do we need this?
        return user_id


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
    #
    auth.assign_role_to_token(token_id, 'system', mode='administration')

    #
    return auth.encode_token(token_id)


def generate_project_secrets(project_id: int) -> Tuple[dict, dict]:
    project_secrets = {
        'galloper_url': c.APP_HOST,
        'project_id': project_id,
    }

    project_hidden_secrets = {
        k: v.format(project_id) for k, v in INFLUX_DATABASES.items()
    }

    return project_secrets, project_hidden_secrets
