#!/usr/bin/env python3
import os
import ssl
import sys
import time
from datetime import datetime

import asyncio
import click
import requests
import websockets

from requests.auth import HTTPBasicAuth


def getenv(var, default=None):
    v = os.getenv(var)
    if v is None:
        v = default
    if v is None:
        raise ValueError('{} is a required environment variable'.format(var))
    return v


async def get_logs(url):
    ssl_context = ssl._create_unverified_context()
    async with websockets.connect(url, ssl=ssl_context) as ws:
        try:
            while True:
                print(await ws.recv(), end='')
        except websockets.exceptions.ConnectionClosed:
            pass


class RancherDeploy:
    def __init__(self, service_name, docker_image, docker_tag):
        self.access_key = getenv('RANCHER_ACCESS_KEY')
        self.secret_key = getenv('RANCHER_SECRET_KEY')
        self.rancher_url = getenv('RANCHER_URL')
        self.rancher_stack_name = getenv('RANCHER_STACK_NAME')

        if not service_name:
            service_name = os.getenv('WERCKER_APPLICATION_NAME')
            if not service_name:
                raise ValueError('Not a wercker environment. '
                                 'Must provide service name')
            else:
                print('info: Service name not provided, assuming '
                      'wercker application name')

        if not docker_image:
            docker_image = os.getenv('DOCKER_IMAGE_NAME')

        if not self.rancher_url.startswith('http'):
            self.rancher_url = 'https://' + self.rancher_url

        self.service_name = service_name
        self.docker_image = docker_image
        self.docker_tag = docker_tag
        self.stack_id = self._get_stack_id()
        self.service_id = self._get_service_id()

    def _get_stack_id(self):
        response = self._api_get('/environments/?name={stack}'
                                 .format(stack=self.rancher_stack_name))

        return response.json().get('data')[0].get('id')

    def _get_service_id(self):
        response = self._api_get('/environments/{id}/services/?name={name}'
                                 .format(id=self.stack_id,
                                         name=self.service_name))

        services = response.json().get('data')
        service_id = None
        for s in services:
            # we have to check names ourselves since there is a bug in rancher api
            name = s.get('name')
            if name == self.service_name:
                service_id = s.get('id')
                self.launch_config = s.get('launchConfig')

        if service_id is None:
            raise ValueError('Service {} not found'.format(self.service_name))
        return service_id

    def _api_get(self, path):
        return requests.get(
            self.rancher_url + path,
            auth=HTTPBasicAuth(self.access_key, self.secret_key)
        )

    def _api_post(self, path, data):
        return requests.post(
            self.rancher_url + path,
            json=data,
            auth=HTTPBasicAuth(self.access_key, self.secret_key)
        )

    def get_container_logs(self):
        print('info: container logs as follows:')
        # get container
        response = self._api_get('/services/{sid}/instances'
                                 .format(url=self.rancher_url,
                                         sid=self.service_id))

        # get an active container
        container_id = None
        for instance in response.json().get('data'):
            if (instance.get('type') == 'container' and
                        instance.get('state') == 'running'):
                container_id = instance.get('id')
                break

        if container_id is None:
            # no running containers, nothing we can do
            return

        response = self._api_post(
            '/containers/{id}/?action=logs'.format(id=container_id),
            {'follow': False, 'lines': 100}
        )
        value = response.json()
        url = value.get('url') + '?token=' + value.get('token')
        asyncio.get_event_loop().run_until_complete(get_logs(url))

    def wait_for_healthy(self):
        unhealthy_count = 0
        url = '/services/{sid}'.format(sid=self.service_id)
        while True:
            response = self._api_get(url)
            body = response.json()
            health = body.get('healthState')
            print('DEBUG:', health, '  --', datetime.now(), flush=True)
            if body.get('transitioning') == 'no':
                print('DEBUG: no longer transitioning')
                return health
            if health == 'unhealthy':
                unhealthy_count += 1
                # Container has gone bad, we should rollback
                if unhealthy_count == 7:
                    self.cancel()
            time.sleep(3)

    def cancel(self):
        print('\033[1mUnhealty container, canceling deploy\033[0m')
        # first, print container logs
        self.get_container_logs()

        response = self._api_post(
            '/services/{}/?action=cancelupgrade'.format(self.service_id),
            {'action': 'cancelupgrade'})


    def deploy(self):
        self.launch_config['imageUuid'] = 'docker:{image}:{tag}'.format(
            image=self.docker_image, tag=self.docker_tag
        )
        request_body = {
            'inServiceStrategy': {
                'batchSize': 1,
                'intervalMillis': 20000,
                'startFirst': True,
                'launchConfig': self.launch_config,
            }
        }

        print('--Starting deploy--')
        response = self._api_post(
            '/services/{id}?action=upgrade'.format(id=self.service_id),
            request_body)

        result = response.json()
        if (response.status_code == 422 and
                    result.get('code') == 'ActionNotAvailable'):
            raise ValueError('Deployment already in progress.')
        health = self.wait_for_healthy()
        if health == 'healthy':
            action = 'finishupgrade'
        else:
            print('info: final health:', health)
            action = 'rollback'
            self.get_container_logs()

        response = self._api_post('/services/{sid}/?action={action}'
                                  .format(sid=self.service_id,
                                          action=action),
                                  {'action': action})

        print()
        if action == 'rollback':
            raise ValueError('Service was unhealthy, a rollback occurred.')
        else:
            print('Deployment successful!')


@click.command()
@click.option('--service-name', default=None,
              help='name of sofe service')
@click.option('--docker-image', default=None,
              help='name of docker repo')
@click.option('--docker-tag', default=None,
              help='docker container tag to deploy', required=True)
def rancherdeploy(service_name, docker_image, docker_tag):
    deployment = RancherDeploy(service_name, docker_image, docker_tag)
    deployment.deploy()

if __name__ == '__main__':
    try:
        rancherdeploy()
    except ValueError as e:
        print('\033[0m', e, '\033[0m')
        sys.exit(1)


