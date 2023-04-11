#   Copyright 2019 getcarrier.io
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
from typing import Optional

from influxdb import InfluxDBClient
from tools import VaultClient


def get_client(project_id: int, db_name: Optional[str] = None):
    vault_client = VaultClient.from_project(project_id)
    all_secrets = vault_client.get_all_secrets()
    secrets = vault_client.get_project_secrets()
    influx_host = secrets.get("influx_ip") if "influx_ip" in secrets else all_secrets.get("influx_ip", "")
    influx_user = secrets.get("influx_user") if "influx_user" in secrets else all_secrets.get("influx_user", "")
    influx_password = secrets.get("influx_password") if "influx_password" in secrets else \
        all_secrets.get("influx_password", "")

    return InfluxDBClient(influx_host, 8086, influx_user, influx_password, db_name)


def create_project_databases(project_id: int):
    vault_client = VaultClient.from_project(project_id)
    hidden_secrets = vault_client.get_project_hidden_secrets()
    from pylon.core.tools import log
    log.info('create_project_databases hidden_secrets %s', hidden_secrets)
    db_list = [
        hidden_secrets.get("jmeter_db"),
        hidden_secrets.get("gatling_db"),
        hidden_secrets.get("comparison_db"),
        hidden_secrets.get("telegraf_db")
    ]
    client = get_client(project_id)
    for each in db_list:
        client.query(f"create database {each} with duration 180d replication 1 shard duration 7d name autogen")


def drop_project_databases(project_id: int):
    vault_client = VaultClient.from_project(project_id)
    hidden_secrets = vault_client.get_project_hidden_secrets()
    db_list = [
        hidden_secrets.get("jmeter_db"),
        hidden_secrets.get("gatling_db"),
        hidden_secrets.get("comparison_db"),
        hidden_secrets.get("telegraf_db")
    ]
    client = get_client(project_id)
    for each in db_list:
        client.query(f"drop database {each}")
