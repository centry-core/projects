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


from tools import VaultClient


def get_client(
        project_id: int, db_name: Optional[str] = None,
        vault_client: Optional[VaultClient] = None,
        secrets: Optional[dict] = None,
        **kwargs
):
    if secrets:
        all_secrets = secrets
    elif vault_client:
        all_secrets = vault_client.get_all_secrets()
    else:
        all_secrets = VaultClient.from_project(project_id).get_all_secrets()
    influx_host = all_secrets.get("influx_ip", "")
    influx_port = all_secrets.get("influx_port", 8086)
    influx_user = all_secrets.get("influx_user", "")
    influx_password = all_secrets.get("influx_password", "")
    from influxdb import InfluxDBClient
    return InfluxDBClient(influx_host, influx_port, influx_user, influx_password, db_name, **kwargs)
