#!/bin/bash

project_name=abc
use_https=0
jupyter_port=0
api_port=5000
use_traefik=0
use_basicauth=0
use_letsencrypt=0
deploy_frontend=1
project_domain=abc.def
project_frontend_port=8501


while getopts ":n:s:j:a:t:b:l:f:p:d:" opt; do
  case $opt in
    n) project_name="$OPTARG"
    ;;
    s) use_https="$OPTARG"
    ;;
    j) jupyter_port="$OPTARG"
    ;;
    a) api_port="$OPTARG"
    ;;
    t) use_traefik="$OPTARG"
    ;;
    b) use_basicauth="$OPTARG"
    ;;
    l) use_letsencrypt="$OPTARG"
    ;;
    f) deploy_frontend="$OPTARG"
    ;;
    p) project_frontend_port="$OPTARG"
    ;;
    d) project_domain="$OPTARG"
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    ;;
  esac
done

printf " -n: Argument project_name is %s\n" "$project_name"
printf " -s: Argument use_https is %s\n" "$use_https"
printf " -j: Argument jupyter_port is %s\n" "$jupyter_port"
printf " -a: Argument api_port is %s\n" "$api_port"
printf " -t: Argument use_traefik is %s\n" "$use_traefik"
printf " -b: Argument use_basicauth is %s\n" "$use_basicauth"
printf " -l: Argument use_letsencrypt is %s\n" "$use_letsencrypt"
printf " -f: Argument deploy_frontend is %s\n" "$deploy_frontend"
printf " -p: Argument project_frontend_port is %s\n" "$project_frontend_port"
printf " -d: Argument project_domain is %s\n" "$project_domain"


while true; do
    read -p "Are you sure that you want to create the above project "$project_name"? (y / n) " yn
    case $yn in
        [Yy]* ) echo "OK, creating the project "$project_name" now.";
                break;;
        [Nn]* ) echo "Exiting project creation";
                exit 1;;
        * ) echo "Please answer yes or no.";;
    esac
done

cp ./templates/.env.template .env.$project_name

sed -i 's/## do not change this file!//' .env.$project_name

echo "copied the .env.$project_name template"
sed -i 's/<replace_project_name>/'$project_name'/' .env.$project_name
sed -i 's/<replace_use_https>/'$use_https'/' .env.$project_name
sed -i 's/<replace_jupyter_port>/'$jupyter_port'/' .env.$project_name
sed -i 's/<replace_api_port>/'$api_port'/' .env.$project_name
sed -i 's/<replace_use_traefik>/'$use_traefik'/' .env.$project_name
sed -i 's/<replace_use_basicauth>/'$use_basicauth'/' .env.$project_name
sed -i 's/<replace_use_letsencrypt>/'$use_letsencrypt'/' .env.$project_name
sed -i 's/<replace_deploy_frontend>/'$deploy_frontend'/' .env.$project_name
sed -i 's/<replace_project_domain>/'$project_domain'/' .env.$project_name
sed -i 's/<replace_frontend_port>/'$project_frontend_port'/' .env.$project_name

echo "DONE replacing the arguments in the .env.$project_name template"

mkdir -p ./data/$project_name/neo4j/var/lib/neo4j/import/data/
mkdir -p ./data/$project_name/neo4j/data
touch ./data/$project_name/neo4j/var/lib/neo4j/import/data/citations.csv
mkdir ./notebooks/$project_name
mkdir ./input/$project_name
mkdir ./output/$project_name
touch ./output/$project_name/knowledge-graph-neo4j-helper.log

cp -r ./templates/config/* ./input/$project_name/
sed -i 's/<replace_project_name>/'$project_name'/' ./input/$project_name/config.ini
echo "now prepare the placeholders for the frontend"
sed -i 's/<replace_project_name>/'${project_name^^}'/' ./input/$project_name/runtimeConfig.json
sed -i 's/<replace_base_api_url>/'$base_api_url'/' ./input/$project_name/runtimeConfig.json
sed -i 's/<replace_project_name>/'${project_name}'/' ./input/$project_name/home.md
#sed -i 's/<replace_base_api_url>/'${base_api_url}'/' ./input/$project_name/home.md
sed -i 's/<replace_project_domain>/'${project_domain}'/' ./input/$project_name/home.md

cp ./templates/*.ipynb ./notebooks/$project_name/
cp ./templates/.gitkeep ./output/$project_name
