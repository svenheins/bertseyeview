## test curating the annotations in neo4j
## in case one entity is wrongly annotated, change it to the ocrrect 
## annotation
import json
from helper.neo4j_helper import Neo4j_Manager
import configparser
from datetime import datetime

## main function
def main():
    config_path = 'input/als/config.ini'
    ## general config
    config = configparser.ConfigParser()
    config.read(config_path)
    project_name = config['GENERAL-settings']['project_name']
    db_hostname = config['NEO4J-settings']['neo4j_hostname']
    neo4j_bolt = 'bolt://localhost:7687'
    neo4j_user = config['NEO4J-settings']['neo4j_user']
    neo4j_password = config['NEO4J-settings']['neo4j_password']

    neo4j_manager = Neo4j_Manager(neo4j_bolt, neo4j_user, neo4j_password)

    ## run the curation
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print(str(current_time) + ": run global curations")
    ## global curation file
    test_json = "input/global/curate_annotations.json"
    # open the global json-file and perform the curation
    with open(test_json) as json_file:
        curate_data = json.load(json_file)
        for dict_curate_entry in curate_data:
            ## validate structure
            if set(["name", "description", "from_keys", "to_keys", \
                    "from_values", "to_values"]) == \
                        set(curate_data[dict_curate_entry].keys()):
                from_keys = curate_data[dict_curate_entry]["from_keys"]
                from_values = curate_data[dict_curate_entry]["from_values"]
                to_keys = curate_data[dict_curate_entry]["to_keys"]
                to_values = curate_data[dict_curate_entry]["to_values"]
                ## execute the curation
                response = neo4j_manager.merge_nodes(from_keys, from_values, to_keys, to_values)
                print(response)
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print(str(current_time) + ": DONE running the currations")

# __main__ function 
if __name__=="__main__": 
    main() 