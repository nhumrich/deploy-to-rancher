# deploy-to-rancher
A deployment script for deploying containers to Rancher (rancher.com)

This repo contains a deployment script to deploy a container to rancher. 
The deployment will automatically deploy a service to rancher, doing an in-place rolling upgrade.
The upgrade will upgrade one container at a time, with 20 seconds inbetween each container. 

The script will also check the status of the container while deploying, and will automatically rollback if the
container every goes unhealthy during deployment.
If a rollback occurs, the container logs will be displayed.

This script requires python 3.5. You can either run the script directly, or inside the provided docker container.


##
using:

In order to use this script, you need the following environment variables set:

```
RANCHER_ACCESS_KEY
RANCHER_SECRET_KEY
RANCHER_URL   # must include path to the "environment" (project), you get this on the api page for the env
RANCHER_STACK_NAME  # stack name of the service you want to deploy


```bash
deploy-to-rancher.py --service-name foobar --docker-image 'nhumrich/foobar' --docker-tag sometag
```

Alternate environment variables:

```
DOCKER_IMAGE_NAME  # the base name of the docker image you want to deploy, can be used instead of --docker-image


## using on wercker
If you are using this on wercker, the service name is assumed from the environment variable `WERCKER_APPLICATION_NAME` which wercker provides. So if your service is the same as your repository name, you get that for free.
I also recommend pushing your docker container with the tag as the git SHA `$WERCKER_GIT_COMMIT`, then you can use `--docker-tag "$WERCKER_GIT_COMMIT"`.  You can also add a new pipeline for deploying, and simply use the container `nhumrich/deploy-to-rancher` and everything should work. 

