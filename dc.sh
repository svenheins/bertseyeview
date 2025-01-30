#!/bin/bash

project_name=als
command="up -d"

docker network create traefik
docker network create jupyterhub

while getopts ":n:c:" opt; do
  case $opt in
    n) project_name="$OPTARG"
    ;;
    c) command="$OPTARG"
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    ;;
  esac
done

printf " -n: Argument project_name is %s\n" "$project_name"
printf " -c: Argument command is %s\n" "$command"

while true; do
    echo "The command is 'docker compose "$command"' on project "$project_name
    read -p "Are you sure that you want run this command? (y / n) " yn
    case $yn in
        [Yy]* ) echo "OK, running docker compose "$command" on project "$project_name" now.";
                break;;
        [Nn]* ) echo "Exiting script (no docker-compose "$command" is executed)";
                exit 1;;
        * ) echo "Please answer yes or no.";;
    esac
done


FILE=./.env.$project_name
if [ -f "$FILE" ]; then
    echo "$FILE exists. Continue with dockerc ompose "$command
    export $(cat .env.$project_name)
    export USER_ID=$(id -u)
    export GROUP_ID=$(id -g)
    ## run some preparation in case the data folder is empty or the project has never been initialized
    mkdir -p ./data/${COMPOSE_PROJECT_NAME}/neo4j/var/lib/neo4j/import/data/
    touch ./data/$project_name/neo4j/var/lib/neo4j/import/data/citations.csv
    ADD_DOCKER_COMPOSE_YML=""
    if [ $PROJECT_JUPYTER_PORT -gt 0 ]; then
      ADD_DOCKER_COMPOSE_YML=$ADD_DOCKER_COMPOSE_YML" -f docker-compose.jupyter.yml" 
    fi
    if [ $PROJECT_API_PORT -gt 0 ]; then
      ADD_DOCKER_COMPOSE_YML=$ADD_DOCKER_COMPOSE_YML" -f docker-compose.open-api.yml" 
    fi
    if [ $PROJECT_NEO4J_HTTP_PORT -gt 0 -a $PROJECT_NEO4J_HTTPS_PORT -gt 0 -a $PROJECT_NEO4J_BOLT_PORT -gt 0 ]; then
      ADD_DOCKER_COMPOSE_YML=$ADD_DOCKER_COMPOSE_YML" -f docker-compose.open-neo4j.yml" 
    fi
    if [ $PROJECT_USE_TRAEFIK -gt 0 ]; then
      ADD_DOCKER_COMPOSE_YML=$ADD_DOCKER_COMPOSE_YML" -f docker-compose.traefik.yml" 
    fi
    if [ $PROJECT_USE_BASICAUTH -gt 0 ]; then
      ADD_DOCKER_COMPOSE_YML=$ADD_DOCKER_COMPOSE_YML" -f docker-compose.traefik-basicauth.yml" 
    fi
    if [ $PROJECT_USE_LETSENCRYPT -gt 0 ]; then
      ADD_DOCKER_COMPOSE_YML=$ADD_DOCKER_COMPOSE_YML" -f docker-compose.traefik-letsencrypt.yml" 
    fi
    if [ $PROJECT_DEPLOY_FRONTEND -gt 0 ]; then
      mkdir ./temp
      ADD_DOCKER_COMPOSE_YML=$ADD_DOCKER_COMPOSE_YML" -f docker-compose.frontend.yml"
    fi
    if [ $PROJECT_FRONTEND_HTTP_PORT -gt 0 ]; then
      ADD_DOCKER_COMPOSE_YML=$ADD_DOCKER_COMPOSE_YML" -f docker-compose.frontend-open-port.yml" 
    fi
    echo "The following yml-files will be attached to the docker-compose command: "$ADD_DOCKER_COMPOSE_YML
    env $(cat .env.$project_name) docker compose -f docker-compose.yml $ADD_DOCKER_COMPOSE_YML $command
else 
    echo "$FILE does not exist. Exiting..."
fi
