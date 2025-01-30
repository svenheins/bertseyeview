## test neo4j
# in order to execute this, you need to setup i.e. a conda environment
# and then install the neo4j_helper.py package (see script on the 
# root directory of this project)

from helper.neo4j_helper import Neo4j_Manager
from helper.graph_classes import Node_Factory
import configparser
import os
import logging
import pandas as pd

import plotly
import plotly.express as px

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
    #neo4j_bolt = config['NEO4J-settings']['neo4j_bolt']
    neo4j_bolt = 'bolt://localhost:7687'
    neo4j_user = config['NEO4J-settings']['neo4j_user']
    neo4j_password = config['NEO4J-settings']['neo4j_password']

    #neo4j_manager = Neo4j_Manager(neo4j_bolt+"-"+project_name, neo4j_user, neo4j_password)
    neo4j_manager = Neo4j_Manager(neo4j_bolt, neo4j_user, neo4j_password, logging = logging)

    cytoscape_query = "main-diseases-2"
    query_input_path ="./input/"+project_name+"/"
    query_output_path ="./output/"+project_name+"/"

    #query = "CALL {        MATCH (d:disease)--(:Article)        WITH count(d) as count_entities, d        RETURN d        ORDER BY count_entities DESC LIMIT 5    }    WITH COLLECT(d) as diseases    CALL {        WITH diseases        MATCH (subset_articles_1:Article)-->(g:disease)        WHERE g in diseases        WITH count(subset_articles_1) AS count_subset_articles_1,             collect(subset_articles_1) AS subset_list_1        CALL {            WITH count_subset_articles_1, subset_list_1            MATCH (mentions_all:Article)-->(mentions_subset_1_target:Article)            WHERE mentions_subset_1_target IN subset_list_1            WITH count_subset_articles_1, mentions_subset_1_target,                count(mentions_all) AS count_all            RETURN mentions_subset_1_target, count_all        }            WITH count_subset_articles_1, subset_list_1, mentions_subset_1_target, count_all         CALL {             WITH count_subset_articles_1, subset_list_1, mentions_subset_1_target, count_all            MATCH (mentions_subset_1:Article)-->(mentions_subset_1_target)            WHERE mentions_subset_1 IN subset_list_1             WITH count(mentions_subset_1) AS count_target            RETURN count_target        }        UNWIND [mentions_subset_1_target.age_in_months, 1] AS age_to_one         WITH mentions_subset_1_target as article, count_all, count_target, max(age_to_one) AS age_norm,            (count_all + 100 * count_target) as count_metric,            (toFloat(count_all + 100 * count_target) / max(age_to_one)) as count_metric_age_norm        RETURN article ORDER BY count_metric_age_norm DESC LIMIT 100    }    WITH diseases, COLLECT(article) as literature    CALL {        WITH diseases, literature        MATCH (d1:disease)--(a1:Article)--(g:gene)        WHERE d1 IN diseases AND g.taxid = '9606' AND a1 in literature        WITH DISTINCT d1, g        CALL apoc.create.vRelationship(g,'GENE_DISEASE', {from:g.name, to:d1.name} ,d1) YIELD rel as rel1        RETURN COLLECT (g) as genes, COLLECT(rel1) as rels1    }    CALL {        WITH genes        MATCH (g1)--(p:pathway_kegg)        WHERE g1 in genes        CALL apoc.create.vRelationship(p, 'KEGG_HAS_GENE', {from:p.name, to:g1.name}, g1) YIELD rel AS rel_p_g        RETURN COLLECT(p) as kegg_pathways, COLLECT(rel_p_g) as rels_p_g    }    CALL {        WITH diseases, literature        MATCH (d1:disease)--(b)--(c:chemical)        WHERE d1 IN diseases AND b in literature        WITH DISTINCT d1, c        CALL apoc.create.vRelationship(c, 'CHEMICAL_DISEASE', {from:c.name, to:d1.name}, d1) YIELD rel AS rel2        RETURN COLLECT(c) as chemicals, COLLECT(rel2) as rels2    }    CALL {        WITH diseases, literature        MATCH (d1:disease)--(b)--(s:species)        WHERE d1 IN diseases AND b in literature        WITH DISTINCT d1, s        CALL apoc.create.vRelationship(s, 'SPECIES_DISEASE', {from:s.name, to:d1.name}, d1) YIELD rel AS rel3        RETURN COLLECT(s) as species, COLLECT(rel3) as rels3    }    WITH diseases + genes + kegg_pathways + chemicals + species AS list_nodes, rels1 + rels2 + rels3 + rels_p_g AS list_relations    RETURN {nodes:list_nodes, edges:list_relations}"

    query = '''CALL {
MATCH (d:disease)--(:Article)
WITH count(d) as count_entities, d
RETURN d
ORDER BY count_entities 
DESC LIMIT 50    
}    
WITH COLLECT(d) as diseases    
CALL {
WITH diseases
MATCH (subset_articles_1:Article)-->(g:disease)
WHERE g in diseases
WITH count(subset_articles_1) AS count_subset_articles_1,
     collect(subset_articles_1) AS subset_list_1

CALL {
    
WITH count_subset_articles_1, subset_list_1
MATCH (mentions_all:Article)-->(mentions_subset_1_target:Article)
WHERE mentions_subset_1_target IN subset_list_1
WITH count_subset_articles_1, mentions_subset_1_target,
	count(mentions_all) AS count_all
RETURN mentions_subset_1_target, count_all
}    
WITH count_subset_articles_1, subset_list_1, mentions_subset_1_target, count_all     
CALL {
     
WITH count_subset_articles_1, subset_list_1, mentions_subset_1_target, count_all    
MATCH (mentions_subset_1:Article)-->(mentions_subset_1_target)

WHERE mentions_subset_1 IN subset_list_1      
WITH count(mentions_subset_1) AS count_target      
RETURN count_target     
}   

UNWIND [mentions_subset_1_target.age_in_months, 1] AS age_to_one    
WITH mentions_subset_1_target as article, count_all, count_target, max(age_to_one) AS age_norm, 
   (count_all + 100 * count_target) as count_metric,     
   (toFloat(count_all + 100 * count_target) / max(age_to_one)) as count_metric_age_norm    
RETURN article ORDER BY count_metric_age_norm DESC LIMIT 3000  
}   

WITH diseases, COLLECT(article) as literature
CALL {
WITH diseases, literature
MATCH (d1:disease)--(a1:Article)--(g:gene)
WHERE d1 IN diseases AND g.taxid = '9606' AND a1 in literature
WITH DISTINCT d1, g, a1
CALL apoc.create.vRelationship(a1,'LITERATURE_GENE', {from:a1.name, to:g.name}, g) YIELD rel as rel12
CALL apoc.create.vRelationship(a1,'LITERATURE_DISEASE', {from:a1.name, to:d1.name}, d1) YIELD rel as rel13
RETURN COLLECT (g) as genes,
    COLLECT(rel12) as rels12, COLLECT(rel13) as rels13
}    

CALL {
WITH genes
MATCH (g1)--(p:pathway_kegg)
WHERE g1 in genes
CALL apoc.create.vRelationship(p, 'KEGG_HAS_GENE', {from:p.name, to:g1.name}, g1) 
YIELD rel AS rel_p_g
RETURN COLLECT(p) as kegg_pathways, 
COLLECT(rel_p_g) as rels_p_g    
}      

CALL {
WITH diseases, literature
MATCH (d1:disease)--(b)--(c:chemical)
WHERE d1 IN diseases AND b in literature
WITH DISTINCT d1, c, b
CALL apoc.create.vRelationship(b,'LITERATURE_CHEMICAL', {from:b.name, to:c.name}, c) YIELD rel as rel22
RETURN COLLECT(c) as chemicals,
    COLLECT (rel22) as rels22
}  
  
CALL {
WITH diseases, literature
MATCH (d1:disease)--(b)--(s:species)
WHERE d1 IN diseases AND b in literature
WITH DISTINCT d1, s, b
CALL apoc.create.vRelationship(b,'LITERATURE_SPECIES', {from:b.name, to:s.name}, s) YIELD rel as rel32
RETURN COLLECT(s) as species, COLLECT(rel32) as rels32
}    

WITH diseases + genes + kegg_pathways 
  + chemicals + species + literature
  AS list_nodes, 
  rels_p_g + rels12 + rels13 + rels22 + rels32
  AS list_relations    
RETURN {nodes:list_nodes, edges:list_relations}
'''

    result = neo4j_manager.neo4j_response_to_json(query_string = query, base_path = query_input_path)
    row_list = []

    for nodes in result:
        if 'data' in nodes and "group" in nodes and "position" in nodes:
            if nodes["group"] == "nodes":
                node = nodes["data"]
                position = nodes["position"]
                description = ""
                if (node['node_class'] == "Article"):
                    description = node['tooltip']['Title']
                if (node['node_class'] == "disease"):
                    description = node['tooltip']['Disease MESH']
                if (node['node_class'] == "chemical"):
                    description = node['tooltip']['Chemical MESH']
                if (node['node_class'] == "gene"):
                    description = node['tooltip']['Name']
                if (node['node_class'] == "species"):
                    description = node['tooltip']['name']
                if (node['node_class'] == "pathway_kegg"):
                    description = node['tooltip']['label']
                row_list.append([node["id"], node["label"], node["node_class"], position['x'], position['y'], description])

    df_nodes = pd.DataFrame(row_list)
    df_nodes.columns = ["id", "name", "class", "x", "y", "description"]

    fig = px.scatter(df_nodes, x="x", y="y", color="class",
                 hover_data=['name', 'description', 'class', 'id'],
                 width=800, height=800,
                 title="Node embedding")

    #fig.show(renderer="iframe")
    #fig.show()
    plotly.offline.plot(fig, filename='./output/als/plot_embedding_literature_undirected_big2.html')

    #print(result)

  
# __main__ function 
if __name__=="__main__": 
    main() 
