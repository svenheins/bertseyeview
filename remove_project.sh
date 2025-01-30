#!/bin/bash

project_name=abc

while getopts ":n:" opt; do
  case $opt in
    n) project_name="$OPTARG"
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    ;;
  esac
done

printf " -n: Argument project_name is %s\n" "$project_name"



while true; do
    read -p "Are you sure that you want to remove project "$project_name"? (y / n) " yn
    case $yn in
        [Yy]* ) rm .env.$project_name;
		rm -rf ./data/$project_name;
		rm -rf ./notebooks/$project_name;
		rm -rf ./input/$project_name;
    rm -rf ./output/$project_name;
		break;;
        [Nn]* ) exit;;
        * ) echo "Please answer yes or no.";;
    esac
done
