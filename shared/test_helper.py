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

    csv_table = neo4j_manager.get_statistics()
    
    print(csv_table[0:2000])

    #csv_file = open("out.csv", "w")
    #csv_file.write(csv_table)
    #csv_file.close()
  
  
# __main__ function 
if __name__=="__main__": 
    main() 