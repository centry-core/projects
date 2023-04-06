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

from rabbitmq_admin import AdminAPI
import random
import string
from pylon.core.tools import log

from tools import VaultClient, constants as c


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
    # connect to RabbitMQ management api
    rabbit_client = AdminAPI(url=rabbit_admin_url, auth=rabbit_admin_auth)

    # create project user and vhost
    rabbit_client.create_vhost(vhost)
    rabbit_client.create_user(user, password)
    rabbit_client.create_user_permission(user, vhost)


def create_project_user_and_vhost(project_id: int):
    vault_client = VaultClient.from_project(project_id)
    all_secrets = vault_client.get_all_secrets()
    log.info('create_project_user_and_vhost all_secrets %s', all_secrets)

    # # connect to RabbitMQ management api
    # rabbit_api = AdminAPI(url=f'http://carrier-rabbit:15672',
    #                       auth=(hidden_secrets["rabbit_user"], hidden_secrets["rabbit_password"]))

    # prepare user credentials
    user = f"rabbit_user_{project_id}"
    password = password_generator()
    vhost = f"project_{project_id}_vhost"

    create_rabbit_user_and_vhost(
        rabbit_admin_url=f'http://{c.RABBIT_HOST}:15672',
        rabbit_admin_auth=(all_secrets["rabbit_user"], all_secrets["rabbit_password"]),
        user=user, password=password, vhost=vhost
    )

    # set project secrets
    secrets = vault_client.get_project_secrets()
    secrets["rabbit_project_user"] = user
    secrets["rabbit_project_password"] = password
    secrets["rabbit_project_vhost"] = vhost
    vault_client.set_project_secrets(secrets)


# def create_administration_user_and_vhost():
#     vault_client = VaultClient()
#     secrets = vault_client.get_secrets()
#
#     # prepare user credentials
#     user = 'rabbit_user_administration'
#     password = password_generator()
#     vhost = "administration_vhost"
#
#     create_rabbit_user_and_vhost(
#         rabbit_admin_url=f'http://{c.RABBIT_HOST}:15672',
#         rabbit_admin_auth=(secrets["rabbit_user"], secrets["rabbit_password"]),
#         user=user, password=password, vhost=vhost
#     )
#
#     # set secrets
#     secrets = vault_client.get_project_secrets()
#     secrets["rabbit_administration_user"] = user
#     secrets["rabbit_administration_password"] = password
#     secrets["rabbit_administration_vhost"] = vhost
#     vault_client.set_secrets(secrets)
