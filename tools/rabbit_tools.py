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

from .secrets_tools import get_project_hidden_secrets, get_project_secrets, set_project_secrets
from rabbitmq_admin import AdminAPI
import random
import string
from pylon.core.tools import log


def create_project_user_and_vhost(project_id):
    secrets = get_project_secrets(project_id)
    hidden_secrets = get_project_hidden_secrets(project_id)

    # connect to RabbitMQ management api
    rabbit_api = AdminAPI(url=f'http://carrier-rabbit:15672',
                          auth=(hidden_secrets["rabbit_user"], hidden_secrets["rabbit_password"]))

    # prepare user credentials
    user = f"rabbit_user_{project_id}"
    password = password_generator()
    vhost = f"project_{project_id}_vhost"
    # create project user and vhost
    rabbit_api.create_vhost(vhost)
    rabbit_api.create_user(user, password)
    rabbit_api.create_user_permission(user, vhost)

    # set project secrets
    secrets["rabbit_project_user"] = user
    secrets["rabbit_project_password"] = password
    secrets["rabbit_project_vhost"] = vhost
    set_project_secrets(project_id, secrets)


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