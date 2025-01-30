## test neo4j
# in order to execute this, you need to setup i.e. a conda environment
# and then install the neo4j_helper.py package (see script on the 
# root directory of this project)

from helper.neo4j_helper import Neo4j_Manager
from helper.graph_classes import Node_Factory
import configparser
import os
import logging

# Defining main function 
def main(): 

    project_name = "als"
    ## setup the logger to print to stdout and to the file
    log_path = "./output/"+project_name
    log_file_name = "knowledge-graph-neo4j-helper-new.log"
    log_file_path = os.path.join(log_path, log_file_name)

    log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] \
                                    %(message)s")
    logging.basicConfig(filename = log_file_path, filemode='a', 
                        format='%(asctime)s [%(levelname)s] %(message)s', 
                        level=logging.INFO)
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(log_formatter)
    logging.getLogger().addHandler(consoleHandler)
    logging.info("initialized the logger")

    config_path = 'input/'+project_name+'/config.ini'
    ## general config
    config = configparser.ConfigParser()
    config.read(config_path)
    project_name = config['GENERAL-settings']['project_name']
    db_hostname = config['NEO4J-settings']['neo4j_hostname']
    neo4j_bolt = 'bolt://localhost:7687'
    neo4j_user = config['NEO4J-settings']['neo4j_user']
    neo4j_password = config['NEO4J-settings']['neo4j_password']

    neo4j_manager = Neo4j_Manager(neo4j_bolt, neo4j_user, neo4j_password, logging = logging)

    goal_entity_label = "gene"
    goal_entity_attribute = None
    goal_entity_operator = None
    goal_entity_value = None
    list_filter_entity_labels_1 = ["disease"]
    list_filter_entity_attributes_1 = ["name"]
    list_filter_entity_operators_1 = ["="]
    list_filter_entity_values_1 = ["Disease:MESH:D015209"]
    list_filter_entity_labels_2 = ["disease"]
    list_filter_entity_attributes_2 = ["name"]
    list_filter_entity_operators_2 = ["="]
    list_filter_entity_values_2 = ["Disease:MESH:D065626"]
    goal_entity_min_mentions = 10
    sort_string = "score DESC"
    options= None

    result = neo4j_manager.get_label_abundance(goal_entity_label, 
            goal_entity_attribute,
            goal_entity_operator,
            goal_entity_value,
            list_filter_entity_labels_1,
            list_filter_entity_attributes_1,
            list_filter_entity_operators_1,
            list_filter_entity_values_1,
            list_filter_entity_labels_2,
            list_filter_entity_attributes_2,
            list_filter_entity_operators_2,
            list_filter_entity_values_2,
            goal_entity_min_mentions,
            sort_string,
            options
            ) 

    print(result)

  
# __main__ function 
if __name__=="__main__": 
    main() 
