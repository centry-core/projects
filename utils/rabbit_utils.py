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
from typing import Tuple

from ..constants import PROJECT_RABBIT_USER_TEMPLATE, PROJECT_RABBIT_VHOST_TEMPLATE
from rabbitmq_admin import AdminAPI
import random
import string
from pylon.core.tools import log

from ..models.project import Project
from tools import VaultClient
from tools import config as c


def password_generator(length=16):
    # create alphanumerical from string constants
    letters = string.ascii_letters
    numbers = string.digits
    printable = f'{letters}{numbers}'

    # convert printable from string to list and shuffle
    printable = list(printable)
    random.shuffle(printable)

    # generate random password and convert to string
    random_password = random.choices(printable, k=length)
    random_password = ''.join(random_password)
    return random_password


def create_rabbit_user_and_vhost(rabbit_admin_url: str, rabbit_admin_auth: Tuple[str, str],
                                 user: str, password: str, vhost: str) -> None:
    if c.ARBITER_RUNTIME != "rabbitmq":
        return

    # connect to RabbitMQ management api
    rabbit_client = AdminAPI(url=rabbit_admin_url, auth=rabbit_admin_auth)

    # create project user and vhost
    rabbit_client.create_vhost(vhost)
    rabbit_client.create_user(user, password)
    rabbit_client.create_user_permission(user, vhost)


def delete_rabbit_user_and_vhost(rabbit_admin_url: str, rabbit_admin_auth: Tuple[str, str],
                                 user: str, vhost: str, **kwargs) -> None:
    if c.ARBITER_RUNTIME != "rabbitmq":
        return

    # connect to RabbitMQ management api
    rabbit_client = AdminAPI(url=rabbit_admin_url, auth=rabbit_admin_auth)

    # delete project user and vhost
    # rabbit_client.delete_user_permission(user, vhost)
    rabbit_client.delete_user(user)
    rabbit_client.delete_vhost(vhost)


def fix_rabbit_vhost(project: Project) -> None:
    if c.ARBITER_RUNTIME != "rabbitmq":
        return
    log.info('Fixing rabbit queues for project %s', project.id)
    vc = VaultClient(project)
    all_secrets = vc.get_all_secrets()

    create_rabbit_user_and_vhost(
        rabbit_admin_url=c.RABBIT_ADMIN_URL,
        rabbit_admin_auth=(all_secrets["rabbit_user"], all_secrets["rabbit_password"]),
        user=all_secrets['rabbit_project_user'],
        password=all_secrets['rabbit_project_password'],
        vhost=all_secrets['rabbit_project_vhost']
    )
