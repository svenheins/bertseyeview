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

    ## setup the logger to print to stdout and to the file
    log_path = "./output/als"
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


    config_path = 'input/als/config.ini'
    ## general config
    config = configparser.ConfigParser()
    config.read(config_path)
    project_name = config['GENERAL-settings']['project_name']
    db_hostname = config['NEO4J-settings']['neo4j_hostname']
    #neo4j_bolt = config['NEO4J-settings']['neo4j_bolt']
    neo4j_bolt = 'bolt://localhost:7687'
    neo4j_user = config['NEO4J-settings']['neo4j_user']
    neo4j_password = config['NEO4J-settings']['neo4j_password']

    #neo4j_manager = Neo4j_Manager(neo4j_bolt+"-"+project_name, neo4j_user, neo4j_password)
    neo4j_manager = Neo4j_Manager(neo4j_bolt, neo4j_user, neo4j_password, logging = logging)


    concept_label = "disease"
    concept_field = "name"
    search_operator = "="
    norm_by_age_str = True
    top_n = 10
    terms = "Disease:MESH:D000690"
    format = "csv"

    #result = neo4j_manager.get_top_n_articles_for_label(
    #                    concept_label=concept_label, concept_field=concept_field,
    #                    search_operator=search_operator, term=terms, 
    #                    metric_norm=norm_by_age_str, top_n = top_n, format = format)
    
    #print(result[0:2000])
    node_label = "Article"
    node_attribute = "name"
    node_value = "34791079"
    attribute_name = "primary"
    attribute_value = "false"
    

    result = neo4j_manager.set_node_attribute(node_label = node_label, 
                        node_attribute = node_attribute, 
                        node_value = node_value,
                        attribute_name = attribute_name, 
                        attribute_value = attribute_value)

    #csv_file = open("out.csv", "w")
    #csv_file.write(csv_table)
    #csv_file.close()
  
  
# __main__ function 
if __name__=="__main__": 
    main() 