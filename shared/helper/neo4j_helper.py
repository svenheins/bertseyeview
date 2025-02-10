## neo4j_api
## base class for accessing and querying neo4j
import json
from logging import Logger
import os
import time
import traceback
import sys
import mygene
import requests
import urllib.request
from datetime import datetime 
from neo4j import exceptions
from neo4j import GraphDatabase
from typing import List, Set, Dict, Tuple
from pathlib import Path
from helper.graph_classes import Node_Factory
import pandas as pd

import matplotlib.pyplot as plt
import networkx as nx
from node2vec import Node2Vec
import numpy as np
from sklearn.manifold import TSNE
import pandas as pd
import seaborn as sns

## request something followed by a delay (pubmed allows 3 requests per second)
def request_with_delay(url, api_delay = 0.0, my_timeout = 8.0):#= 0.35):
    try:
        response = requests.get(url, timeout=my_timeout)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError)\
            as err:
        return None#'Server taking too long. Try again later'
    else:
        time.sleep(api_delay)
        return response  

def get_ensembl_genelist(entry: object) -> List[str]:
    ## if dict create list of dict -> [dict]
    if (isinstance(entry, dict)):
        entry_list = [entry]
    elif (isinstance(entry, list)):
        entry_list = entry
    else:
        raise Exception("wrong data type: expected: list or dict, but got: "\
                        + str(type(entry)))
    ensembl_genelist = []
    for entry_key in entry_list:
        if (isinstance(entry_key, dict)):
            if 'gene' in entry_key:
                ensembl_genelist.append(entry_key['gene'])
            else:
                raise Exception("no gene key found in ensembl entry "+str(entry_key))  
        else:
            raise Exception("wrong data type: expected: dict, but got: " \
                            + str(type(entry_key)))  
    
    return ensembl_genelist

def add_quotes(str_in: str) -> str:
    return "\'"+replace_quotes(str_in)+"\'"

def replace_quotes(str_in: str) -> str:
    return str(str_in).replace("\\", "/").replace("'", "\\'")

def is_attribute_string(attribute):
    bool_return = True
    if attribute in ["age_in_days"]:
        bool_return = False
    return bool_return

def is_convertible_to_float(value: str) -> bool:
  try:
    float(value)
    return True
  except:
    return False

def neo4j_create_entities_command(bioconcepts: str) -> str:
        ret_string = ""
        anno_index = 0
        for entity_class in bioconcepts.split(","):
            str_anno_index = str(anno_index)
            str_anno_index_plus_one = str(anno_index+1)
            ret_string += "FOREACH (annotation" + str_anno_index + \
                " in split(line.article_"+entity_class+ \
                ", ',') | MERGE(a"+str_anno_index+":" + entity_class + \
                " { name:split(annotation"+str_anno_index+",\";\")[0] })"\
                " ON CREATE SET a"+str_anno_index+".label=split(annotation"\
                + str_anno_index+",\";\")[1] MERGE (p1)-[:has_named_entity]"\
                "->(a" + str_anno_index + ") ) \n" + \
                "FOREACH (annotation"+str_anno_index_plus_one+" in split(line."\
                "reference_" + entity_class + ", ',') | MERGE(a" \
                + str_anno_index_plus_one + ":" + entity_class + \
                " { name:split(annotation" + str_anno_index_plus_one \
                + ",\";\")[0] }) ON CREATE SET a" + str_anno_index_plus_one \
                + ".label=split(annotation" + str_anno_index_plus_one \
                + ",\";\")[1] MERGE (p2)-[:has_named_entity]->(a" \
                + str_anno_index_plus_one + ") ) \n"
            anno_index += 2
        return ret_string

def get_color_for_label(label: str = ""):
    color = "grey"
    if label == "chemical":
        color = "green"
    if label == "gene":
        color = "orange"
    if label == "Article":
        color = "blue"
    return color

## main Neo4j_Manager class
class Neo4j_Manager:
    success_response = "successfully ran the method (200)"

    def __init__(self, uri: str, user: str, password: str,
            logging: Logger = None) -> None:
        self.logging = logging
        self.mg = mygene.MyGeneInfo()
        while True:
            try:
                self.driver = GraphDatabase.driver(uri, auth=(user, password))
            except exceptions.ServiceUnavailable:
                time.sleep(1)
                continue
            break

    def close(self) -> None:
        self.driver.close()
            
    def create_citation_graph(self, bioconcepts: str) -> None:
        with self.driver.session() as session:
            session.write_transaction(self._create_citation_graph, 
                                      bioconcepts)
    
    def clear_graph(self) -> None:
        with self.driver.session() as session:
            session.write_transaction(self._clear_graph)
    
    def cleanup_null_nodes(self) -> None:
        with self.driver.session() as session:
            session.write_transaction(self._cleanup_null_nodes)

    def cleanup_duplicated_edges(self) -> None:
        with self.driver.session() as session:
            session.write_transaction(self._cleanup_duplicated_edges)

    def setup_index(self) -> None:
        with self.driver.session() as session:
            session.write_transaction(self._setup_index)

    def calculate_and_write_article_rank(self) -> None:
        with self.driver.session() as session:
            session.write_transaction(self._calculate_and_write_article_rank)
   
    ## send query to neo4j and return response
    def query(self, query: str, db=None, log_queries = True) -> list:
        assert self.driver is not None, "Driver not initialized!"
        session = None
        response = None
        try: 
            if (log_queries == True):
                self.logging.info("cypher-query = \n" + query)
            session = self.driver.session(database=db) if db is not None \
                else self.driver.session() 
            response = list(session.run(query))
        except Exception as e:
            self.logging.info("Query failed: ", e)
        finally: 
            if session is not None:
                session.close()
        return response

    ## create a neo4j where clause for the normal search
    def get_where_clause(self, entity_id: str = None, 
                         entity_fields: List[str] = None, 
                         search_operators: List[str] = None,
                         search_terms: List[str] = None) -> str:
        where_clause = "WHERE "
        ## filter for search id
        if entity_id:
            where_clause += "ID(a) = "+entity_id
        ## filter for search term (in entity_fields)
        if search_terms and isinstance(entity_fields, list):
            if entity_id:
                where_clause += " AND "
            where_clause += "("

            if isinstance(search_operators, list):
                if len(search_operators) == len(entity_fields) \
                        and len(search_operators) == len(search_terms) :
                    for index, search_field in enumerate(entity_fields):
                        where_clause += "toLower(a."+search_field+") " \
                                        + search_operators[index] +" "\
                                        "toLower(\""+search_terms[index]+"\")"
                        if index < (len(entity_fields)-1):
                            where_clause += " OR "
                    where_clause += ")"
                else:
                    raise Exception("search operator length != entity fields length")
        return where_clause

    ## create a neo4j where clause for the neighbor search
    def get_where_clause_neighbors(self, entity_id = None):
        ## filter only applies on id of entity a
        where_clause = "WHERE ID(a)="+entity_id
        return where_clause

    ## check server status
    def get_status(self, uri: str, user: str, password: str) -> int:
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
        except exceptions.AuthError:
            return 401
        except exceptions.ValueError:
            return 404
        except Exception:
            exc_info = sys.exc_info()
            return ''.join(traceback.format_exception(*exc_info))
        return 200

    def get_statistics(self) -> List[dict]:
        ## define and run the final query
        query_string = '''
        CALL apoc.meta.stats() YIELD labels
        RETURN labels
        '''
        response = self.query(query_string)
        response_list = [{'message':'no result found'}]
        ## create list from reponse, if the response exists
        if (response):
            if len(response) > 0:
                response_list = [dict(_) for _ in response]
        return response_list#jsonify(results = response_list)

    def get_predefined_label_abundance(self, query: str = None) -> str:
        label_abundance_json = "/input/label_abundance_queries.json"
        response = None
        with open(label_abundance_json) as label_abundance_file:
            query_dict = json.load(label_abundance_file)
            ## return cached result if exists
            if query in query_dict:
                label_query_object = query_dict[query]

                if "list_filter_entity_labels_2" in label_query_object and \
                    "list_filter_entity_attributes_2" in label_query_object and \
                    "list_filter_entity_operators_2" in label_query_object and \
                    "list_filter_entity_values_2" in label_query_object:
                    list_filter_entity_labels_2 = label_query_object["list_filter_entity_labels_2"]
                    list_filter_entity_attributes_2 = label_query_object["list_filter_entity_attributes_2"]
                    list_filter_entity_operators_2 = label_query_object["list_filter_entity_operators_2"]
                    list_filter_entity_values_2 = label_query_object["list_filter_entity_values_2"]
                else:
                    list_filter_entity_labels_2 = list_filter_entity_attributes_2 = \
                        list_filter_entity_operators_2 = list_filter_entity_values_2 = None
                        
                response = self.get_label_abundance(
                    label_query_object["goal_entity_label"],
                    label_query_object["goal_entity_attribute"],
                    label_query_object["goal_entity_operator"],
                    label_query_object["goal_entity_value"],
                    label_query_object["list_filter_entity_labels"],
                    label_query_object["list_filter_entity_attributes"],
                    label_query_object["list_filter_entity_operators"],
                    label_query_object["list_filter_entity_values"],
                    list_filter_entity_labels_2,
                    list_filter_entity_attributes_2,
                    list_filter_entity_operators_2,
                    list_filter_entity_values_2,
                    label_query_object["goal_entity_min_mentions"],
                    label_query_object["sort_string"],
                    )
            ## else run query and save result in cache
            else:
                response = None
                ##error no result
        

        self.logging.info("DONE runnig the predefined label abundance query: "+query)
        return response


    def get_article_where_clause(self, article_variable, article_attributes, article_operators, article_values):
        return_where_clause = ""
        for index, attribute in enumerate(article_attributes):
            if index > 0:
                return_where_clause += " and"
            return_where_clause += f" toLower({article_variable}.{attribute}) {article_operators[index]} \'{article_values[index].lower()}\'"
        return return_where_clause

    ## calculate gene abundance and return string (csv format)
    def get_label_abundance(self, goal_entity_label: str = None, 
            goal_entity_attribute: str = None, 
            goal_entity_operator: str = None, 
            goal_entity_value: str = None,
            list_filter_entity_labels_1: List[str] = None, 
            list_filter_entity_attributes_1: List[str] = None, 
            list_filter_entity_operators_1: List[str] = None, 
            list_filter_entity_values_1: List[str] = None, 
            list_filter_entity_labels_2: List[str] = None, 
            list_filter_entity_attributes_2: List[str] = None, 
            list_filter_entity_operators_2: List[str] = None, 
            list_filter_entity_values_2: List[str] = None, 
            list_article_attributes: List[str] = None, 
            list_article_operators: List[str] = None, 
            list_article_values: List[str] = None,
            goal_entity_min_mentions: int = 10,
            sort_string: str = "score DESC",
            options: str = None
            ) -> str:

        ## required parameters: goal_entity_label and s1_entity_label
        if (goal_entity_label != None):
            return_attributes = "entity.name AS name,entity.label AS label"
            goal_entity_where_clause = ""
            goal_jump_entity = ""
            score_normalization = ""

            score_name = "score_1 as score"
            #sort_string = "score"
            #if (sort_by_internal_ratio):
            #    sort_string = "relative_subset_mentions_1"

            if goal_entity_label.lower() == "article":
                goal_entity_label = "Article"
                return_attributes = "entity.name AS pubmed_id, entity.pmc_id AS pmc_id, " \
                                    "entity.label AS label, entity.b_title AS title, " \
                                    "entity.age_in_days AS age_in_days, "\
                                    "entity.epubdate AS epubdate, entity.journal AS journal, "\
                                    "entity.authors AS authors, entity.date_integration AS date_integration, "\
                                    "entity.name AS db_name"
                if options != None:
                    if "normalize_by_age" in options.split(","):
                        score_normalization = "/ (toFloat(entity.age_in_days) / 365) "
                sort_string = sort_string + ", epubdate "
            if goal_entity_label == "gene":
                return_attributes = "entity.entrezgene AS entrez_gene,entity.label AS label,"\
                                    "entity.symbol AS symbol,entity.ensembl_ids "\
                                    "AS ensembl_ids, entity.name AS "\
                                    "db_name, entity.alias AS alias"
            if goal_entity_label == "chemical":
                return_attributes = "entity.name AS mesh_chemical,entity.label AS label,"\
                                    "entity.name AS db_name"
            if goal_entity_label == "disease":
                return_attributes = "entity.name AS mesh_disease,entity.label AS label,"\
                                    "entity.name AS db_name"                        
            if goal_entity_label in ["GO_BP", "GO_CC", "GO_MF", 
                                     "pathway_reactome",
                                     "pathway_wikipathways", "pathway_kegg",
                                     "pathway_netpath", "pathway_biocarta",
                                     "pathway_pid"]:
                ## pathways / GO terms are only indirectly connected
                ## -> take genes as jump node
                goal_jump_entity = "-->(:gene)"
                if goal_entity_label in ["GO_BP", "GO_CC", "GO_MF"]:
                    return_attributes = "entity.name AS name,entity.term AS term,"\
                                    "entity.evidence AS evidence, entity.qualifier  "\
                                    "AS qualifier, entity.gocategory AS gocategory"
                else:
                    return_attributes = "entity.name AS name,entity.label AS label,"\
                                    "entity.id AS id  "
            if goal_entity_label == "drug":
                return_attributes = "entity.name AS name,entity.label AS label, "\
                                    "entity.approved AS approved"
                ## drugs are only indirectly connected
                ## -> take genes as jump node
                goal_jump_entity = "-->(:gene)"

            if (goal_entity_attribute != None 
                    and goal_entity_operator != None
                    and goal_entity_value != None):

                if (len(goal_entity_attribute) > 0 
                    and len(goal_entity_operator) > 0
                    ):
                    if not goal_entity_operator.lower() in \
                        ["=", "<", ">", ">=",
                        ">=", "<=", "<>", "is null", 
                        "is not null", "starts with", 
                        "ends with", "contains"]:
                        return f'''error: wrong goal_entity_operator (not supported): {goal_entity_operator}'''

                    if is_attribute_string(goal_entity_attribute):
                        goal_entity_value = f''' '{goal_entity_value}' '''
                    if (len(goal_entity_attribute) > 0
                            and len(goal_entity_operator) > 0):
                        goal_entity_where_clause = f'''
                            and entity.{goal_entity_attribute} \
                                {goal_entity_operator} \
                                {goal_entity_value} '''

            subset_articles_query_1=""
            if list_filter_entity_labels_1 != None:
                if len(list_filter_entity_labels_1) > 0:
                    for index, filter_entity_label in \
                            enumerate(list_filter_entity_labels_1):
                        filter_entity_match_clause = f"MATCH (s_1_{str(index)}:\
                            {filter_entity_label})<--\
                                (subset_articles_1:Article)"
                        filter_entity_where_clause = f"WHERE toLower(s_1_{str(index)}.\
                            {list_filter_entity_attributes_1[index]}) \
                            {list_filter_entity_operators_1[index]} \
                                '{list_filter_entity_values_1[index].lower()}'"
                        if list_article_attributes != None:
                            if len(list_article_attributes) > 0:
                                filter_entity_where_clause += " and " + self.get_article_where_clause( \
                                    "subset_articles_1",
                                    list_article_attributes, 
                                    list_article_operators, 
                                    list_article_values)
                        subset_articles_query_1 += (
                            filter_entity_match_clause \
                            + filter_entity_where_clause )
                else:
                    subset_articles_query_1 = f"MATCH \
                        (subset_articles_1:Article)"
                    if list_article_attributes != None:
                        if len(list_article_attributes) > 0:
                            subset_articles_query_1 += " WHERE "
                            subset_articles_query_1 += self.get_article_where_clause( \
                                "subset_articles_1",
                                list_article_attributes, 
                                list_article_operators, 
                                list_article_values)
            
            subset_articles_query_2=""

            if list_filter_entity_labels_2 != None:
                if len(list_filter_entity_labels_2) > 0:
                    for index, filter_entity_label in \
                            enumerate(list_filter_entity_labels_2):
                        filter_entity_match_clause = f"MATCH (s_2_{str(index)}:\
                            {filter_entity_label})<--\
                                (subset_articles_2:Article)"
                        filter_entity_where_clause = f"WHERE toLower(s_2_{str(index)}.\
                            {list_filter_entity_attributes_2[index]}) \
                            {list_filter_entity_operators_2[index]} \
                                '{list_filter_entity_values_2[index].lower()}'"
                        if list_article_attributes != None:
                            if len(list_article_attributes) > 0:
                                filter_entity_where_clause += " and " + self.get_article_where_clause( \
                                    "subset_articles_2",
                                    list_article_attributes, 
                                    list_article_operators, 
                                    list_article_values)
                        subset_articles_query_2 += (
                            filter_entity_match_clause \
                            + filter_entity_where_clause )
                else:
                    subset_articles_query_2 = f"MATCH \
                        (subset_articles_2:Article)"
                    if list_article_attributes != None:
                        if len(list_article_attributes) > 0:
                            subset_articles_query_2 += " WHERE "
                            subset_articles_query_2 += self.get_article_where_clause( \
                                "subset_articles_2",
                                list_article_attributes, 
                                list_article_operators, 
                                list_article_values)
                create_subset_2 = f'''
                    // subset_2: create subset, count its articles and collect 
                    // those articles
                    {subset_articles_query_2}
                    WITH count_articles, count_subset_articles_1, subset_list_1,
                        count(subset_articles_2) AS count_subset_articles_2, 
                        collect(subset_articles_2) AS subset_list_2
                    '''

                subset_2_with_clause = "count_subset_articles_2, subset_list_2, "

                calculate_subset_2 = f'''
                    // subset_2: determine observed mentions for the goal entity in context of 
                    // the subgraph (i.e. ALS + homo sapiens)
                    MATCH (entity){goal_jump_entity}<--(mentions_subset_2)
                    WHERE mentions_subset_2 IN subset_list_2 and absolute_mentions > {goal_entity_min_mentions}
                    WITH entity, absolute_mentions, expected_mentions, absolute_subset_mentions_1, relative_subset_mentions_1, score_1,
                        count(mentions_subset_2) AS absolute_subset_mentions_2, 
                        (toFloat(count(mentions_subset_2)) / count_subset_articles_2) 
                            AS relative_subset_mentions_2, 
                        round(((toFloat(count(mentions_subset_2)) / count_subset_articles_2)
                            /expected_mentions {score_normalization}), 4) as score_2,
                        (((toFloat(count(mentions_subset_2)) / count_subset_articles_2)
                            /expected_mentions) / score_1) AS score
                    '''

                score_name = "score"
                sort_string = "score"
                return_subset_2 = ", absolute_subset_mentions_2, relative_subset_mentions_2"
            else:
                create_subset_2 = ""
                calculate_subset_2 = ""
                subset_2_with_clause = ""
                return_subset_2 = ""

            a_article_where = ""
            b_article_where = ""
            if list_article_attributes != None:
                if len(list_article_attributes) > 0:
                    a_article_where += " and "
                    a_article_where += self.get_article_where_clause( \
                        "a",
                        list_article_attributes, 
                        list_article_operators, 
                        list_article_values)
                    b_article_where += " WHERE "
                    b_article_where += self.get_article_where_clause( \
                        "b",
                        list_article_attributes, 
                        list_article_operators, 
                        list_article_values)

            
            ## define and run the final query
            query_string = f'''
            // count all articles
            WITH "MATCH (b:Article)
            {b_article_where}
            WITH count(b) AS count_articles

            // subset_1: create subset, count its articles and collect 
            // those articles
            {subset_articles_query_1}
            WITH count_articles, 
                count(subset_articles_1) AS count_subset_articles_1, 
                collect(subset_articles_1) AS subset_list_1

            {create_subset_2}

            // determine expected mentions for the goal entity
            MATCH (entity:{goal_entity_label}){goal_jump_entity}<--(a:Article)
            WHERE 1=1 {goal_entity_where_clause} {a_article_where}
            WITH count_articles, count_subset_articles_1, subset_list_1, {subset_2_with_clause}
                entity,
                count(a) AS absolute_mentions, 
                (toFloat(count(a)) / count_articles) AS expected_mentions

            // subset_1: determine observed mentions for the goal entity in context of 
            // the subgraph (i.e. ALS + homo sapiens)
            MATCH (entity){goal_jump_entity}<--(mentions_subset_1)
            WHERE mentions_subset_1 IN subset_list_1 and absolute_mentions > {goal_entity_min_mentions}
            WITH entity, absolute_mentions, expected_mentions, {subset_2_with_clause}
                count(mentions_subset_1) AS absolute_subset_mentions_1, 
                (toFloat(count(mentions_subset_1)) / count_subset_articles_1) 
                    AS relative_subset_mentions_1, 
                round(((toFloat(count(mentions_subset_1)) / count_subset_articles_1)
                    /expected_mentions {score_normalization}), 4) as score_1

            {calculate_subset_2}
            
            RETURN {score_name}, {return_attributes}, absolute_mentions, expected_mentions,
                absolute_subset_mentions_1, relative_subset_mentions_1, ID(entity) as db_id
                {return_subset_2}
            ORDER BY {sort_string};
            " AS query''' + '''
            CALL apoc.export.csv.query(query, null, {stream: true})
            YIELD file, nodes, relationships, properties, data
            RETURN data;
            '''
            response = self.query(query_string)
            response_string = "message':'no result found'"
            ## create list from reponse, if the response exists
            if (response):
                if len(response) > 0:
                    response_string = ""
                    for response_part in response:
                        response_string = response_string + response_part.data()['data']
                    #response_string = response[0]
                    #response_string = response_string.data()['data']
                    response_string = response_string.replace('","', '|').\
                                        replace('"', '').replace(";", ",").\
                                        replace("|",";")
        else: # goal_entity_label == None OR s1_entity_label == None
            response_string = "message':'no goal_entity_label or "\
                              "s1_entity_label (subset 1 entity label) "\
                              "provided'"

        return response_string

    def search(self, entity_id: str = None, entity_label: str = None, 
               entity_fields: List[str] = ["label"], 
               search_operators:  List[str] = ["contains"],
               search_terms: List[str] = None,
               sort_by: str = None,
               sort_descending: bool = True,
               result_limit: int = None,
               format: str = "json") -> List[dict]:
        class_string = ""
        where_clause = ""
        return_fields = "ID(a), count_links, apoc.map.removeKeys(a, ['embedding', 'embedding_global_x', 'embedding_global_y'] ) AS a "            

        ## filter on specific type / class of entity (disease, article, 
        # gene, ...)
        if entity_label:
            ## special format for the article type string
            if entity_label.lower() == "article":
                entity_label = "Article"
                attributes = ["name", "pmc_id", "label", "b_title", "epubdate", "journal"]
                attributes_labels = ["pubmed_id", "pmc_id", "label", "title", "epubdate", "journal"]
                #return_fields = return_fields + ", a.journal as \
                # journal_name, a.iso_sortpubdate AS publication_date "
            elif entity_label.lower() == "disease":
                attributes = ["name", "label"]
                attributes_labels = ["mesh_disease", "label"]
            elif entity_label.lower() == "gene":
                attributes = ["name", "label", "entrezgene", "symbol"]
                attributes_labels = ["name", "label", "entrez_gene", "symbol"]
            elif entity_label.lower() == "chemical":
                attributes = ["name", "label"]
                attributes_labels = ["mesh_chemical", "label"]
            elif entity_label.lower() == "drug":
                attributes = ["name", "label"]
            else:
                attributes = ["name", "label"]
                attributes_labels = attributes

            class_string = ":"+entity_label
            ## now filter for search_terms and / or id
            if (search_terms or entity_id):
                where_clause = self.get_where_clause(entity_id, entity_fields,
                                                     search_operators, search_terms)
        else:
            ## no type defined -> just filter for search_terms and / or id
            if (search_terms or entity_id):
                where_clause = self.get_where_clause(
                    entity_id, entity_fields, search_operators, search_terms)
        
        sort_statement = ""
        sort_desc_str = "DESC" if sort_descending else "ASC"
        result_limit_str = "" if result_limit == None else " LIMIT " +str(result_limit)
        if sort_by != None:
            if sort_by == "count_links":
                sort_statement = f'''ORDER BY {sort_by} {sort_desc_str} {result_limit_str}'''
            else:
                sort_statement = f'''ORDER BY a.{sort_by} {sort_desc_str} {result_limit_str}'''

        ## define and run the final query
        query_string = f'''
        MATCH (a{class_string})--(b)
        {where_clause}
        WITH count(b) as count_links, a
        RETURN {return_fields} {sort_statement}'''

        response = self.query(query_string)
        response_list = [{'message':'no result found'}]
        ## create list from reponse, if the response exists
        if (response):
            if len(response) > 0:
                dict_all_results = [dict(_) for _ in response]

                if format == "csv":
                    csv_df = pd.DataFrame(columns = attributes_labels)
                    csv_df.index.name = "index"
                    for i, dict_single in enumerate(dict_all_results):
                        fill_values = [ str(dict_single["a"][attribute]).replace(";", ",") \
                                if attribute in dict_single["a"] else "NA" \
                                for attribute in attributes ]
                        csv_df.loc[i] = fill_values
                            
                    response_list = csv_df.to_csv(sep = ";", index=False)
                elif format == "json":
                    response_list = dict_all_results
        return response_list

    ## get neighbors (if a certain type (entity_label)) of a given 
    # entity with id
    def get_neighbors(self, entity_id: str, entity_label: str) -> List[dict]:
        type_string = ""
        where_clause = ""
        return_fields = "ID(entity), entity{.*} "

        if entity_id:
            ## filter for a given desired entity type / class
            if entity_label:
                if entity_label == "article" or entity_label == "Article":
                    entity_label = "Article"
                    #return_fields = return_fields + ", b.journal \
                    # as journal_name, b.iso_sortpubdate AS publication_date "

                type_string = ":"+entity_label
                where_clause = self.get_where_clause_neighbors(entity_id)
            else:
                ## no type is given -> just filter for the id
                where_clause = self.get_where_clause_neighbors(entity_id)
        else:
            #return #jsonify(results = {'message': 'Error: id is missing'})
            return {'results':{'message': 'Error: id is missing'}}
        
        ## define and run the final query
        query_string = f'''
        MATCH (a)--(entity{type_string})
        {where_clause}
        RETURN {return_fields}
        '''
        
        ## create list from reponse, if the response exists
        response = self.query(query_string)
        response_list = [{'message':'no result found'}]
        if (response):
            if len(response) > 0:
                response_list = [dict(_) for _ in response]

        return response_list#jsonify(results = response_list)

    def redirect_relationships(self, from_keys: List[str], 
                               from_values: List[str], to_keys: List[str],
                               to_values: List[str]) -> str:
        ## check for inconsistency
        if (len(from_keys) != len(from_values) or \
                len(to_keys) != len(to_values)):
            self.logging.info("error: inconsistent key / values: from_keys="+from_keys \
                + " - from_values="+from_values+" - to_keys="+to_keys+" - "\
                "to_values="+to_values)
            return -1
        self.redirect_incoming_relationships(from_keys, from_values, to_keys, 
                                             to_values)
        self.redirect_outgoing_relationships(from_keys, from_values, to_keys, 
                                             to_values)
        return self.success_response + " - redirected incoming and outgoing "\
            "from_keys = " + str(from_keys) + " - from_values = " \
            + str(from_values) + " to to_keys = "+ str(to_keys) \
            + " - to_values = " + str(to_values)

    def redirect_incoming_relationships(self, from_keys: List[str], 
                                        from_values: List[str], 
                                        to_keys: List[str], 
                                        to_values: List[str]) -> str:
        ## check for inconsitency
        if (len(from_keys) != len(from_values) \
                or len(to_keys) != len(to_values)):
            self.logging.info("error: inconsistent key / values: from_keys=" \
                  + str(from_keys) +" - from_values="+str(from_values) \
                  + " - to_keys="+str(to_keys)+" - to_values="+str(to_values))
            return -1
        ## create the query strings
        string_from = ""
        for index, from_key in enumerate(from_keys):
            from_value = from_values[index]
            string_from = string_from + "n."+from_key+" = '"+from_value+"'"
            if index < len(from_keys)-1:
                string_from = string_from + " AND "
        string_to = ""
        for index, to_key in enumerate(to_keys):
            to_value = to_values[index]
            string_to = string_to + "m."+to_key+" = '"+to_value+"'"
            if index < len(to_keys)-1:
                string_to = string_to + " AND " 
                
        ## create and run the final query
        query_string = '''MATCH (n), (m)
        WHERE '''+ string_from + " AND " + string_to + \
        '''
        WITH n, m
        MATCH (n)<-[r]-()
        CALL apoc.refactor.to(r,m) YIELD output RETURN output;'''
        response = self.query(query_string)
        self.cleanup_duplicated_edges()
        return self.success_response + " - redirected incoming from_keys = " \
                + str(from_keys) + " - from_values = " + str(from_values) \
                + " to to_keys = "+ str(to_keys) + " - to_values = " \
                + str(to_values)

    def redirect_outgoing_relationships(self, from_keys: List[str], 
                                        from_values: List[str], 
                                        to_keys: List[str], 
                                        to_values: List[str]) -> str:
        ## check for inconsitency
        if (len(from_keys) != len(from_values) \
                or len(to_keys) != len(to_values)):
            self.logging.info("error: inconsistent key / values: from_keys=" \
                  + str(from_keys) + " - from_values=" + str(from_values) \
                  + " - to_keys="+str(to_keys)+" - to_values="+str(to_values))
            return -1
        ## create the query strings
        string_from = ""
        for index, from_key in enumerate(from_keys):
            from_value = from_values[index]
            string_from = string_from + "n."+from_key+" = '"+from_value+"'"
            if index < len(from_keys)-1:
                string_from = string_from + " AND "
        string_to = ""
        for index, to_key in enumerate(to_keys):
            to_value = to_values[index]
            string_to = string_to + "m."+to_key+" = '"+to_value+"'"
            if index < len(to_keys)-1:
                string_to = string_to + " AND " 
                
        ## create and run the final query
        query_string = '''MATCH (n), (m)
        WHERE '''+ string_from + " AND " + string_to + \
        '''
        WITH n, m
        MATCH (n)-[r]->()
        CALL apoc.refactor.from(r,m) YIELD output RETURN output;'''
        response = self.query(query_string)
        self.cleanup_duplicated_edges()
        return self.success_response + " - redirected outgoing from_keys = " \
               + str(from_keys) + " - from_values = " + str(from_values) \
               + " to to_keys = "+ str(to_keys) + " - to_values = " \
               + str(to_values)

    def merge_nodes(self, from_keys: List[str], 
                               from_values: List[str], to_keys: List[str],
                               to_values: List[str]) -> str:
        ## check for inconsitency
        if (len(from_keys) != len(from_values) or \
                len(to_keys) != len(to_values)):
            self.logging.info("error: inconsistent key / values: from_keys="+from_keys \
                + " - from_values="+from_values+" - to_keys="+to_keys+" - "\
                "to_values="+to_values)
            return -1
        ## create the query strings
        string_from = ""
        for index, from_key in enumerate(from_keys):
            from_value = from_values[index]
            string_from = string_from + "n."+from_key+" = '"+from_value+"'"
            if index < len(from_keys)-1:
                string_from = string_from + " AND "
        string_to = ""
        for index, to_key in enumerate(to_keys):
            to_value = to_values[index]
            string_to = string_to + "m."+to_key+" = '"+to_value+"'"
            if index < len(to_keys)-1:
                string_to = string_to + " AND " 
                
        ## create and run the final query
        query_string = '''MATCH (n), (m)
        WHERE '''+ string_from + " AND " + string_to + \
        '''
        WITH head(collect([n,m])) as nodes
        CALL apoc.refactor.mergeNodes(nodes,{properties:"overwrite", mergeRels:true})
        YIELD node
        RETURN count(*)
        '''
        response = self.query(query_string)
        #self.cleanup_duplicated_edges()
        return self.success_response + " response = " + str(response) + \
            "- merging "\
            "from_keys = " + str(from_keys) + " - from_values = " \
            + str(from_values) + " to to_keys = "+ str(to_keys) \
            + " - to_values = " + str(to_values)

    def rename_entity(self, from_keys: List[str], 
                               from_values: List[str], to_keys: List[str],
                               to_values: List[str]) -> str:
        ## check for inconsitency
        if (len(from_keys) != len(from_values) or \
                len(to_keys) != len(to_values)):
            self.logging.info("error: inconsistent key / values: from_keys="+from_keys \
                + " - from_values="+from_values+" - to_keys="+to_keys+" - "\
                "to_values="+to_values)
            return -1
        ## create the query strings
        string_from = ""
        for index, from_key in enumerate(from_keys):
            from_value = from_values[index]
            string_from = string_from + "n."+from_key+" = '"+from_value+"'"
            if index < len(from_keys)-1:
                string_from = string_from + " AND "
        string_to = ""
        for index, to_key in enumerate(to_keys):
            to_value = to_values[index]
            string_to = string_to + "n."+to_key+" = '"+to_value+"'"
            if index < len(to_keys)-1:
                string_to = string_to + ", " 
                
        ## create and run the final query
        query_string = f'''MATCH (n)
        WHERE {string_from} 
        SET {string_to}
        RETURN count(n)
        '''
        response = self.query(query_string)
        #self.cleanup_duplicated_edges()
        return self.success_response + " response = " + str(response) + \
            "- renaming "\
            "from_keys = " + str(from_keys) + " - from_values = " \
            + str(from_values) + " to to_keys = "+ str(to_keys) \
            + " - to_values = " + str(to_values)

    def delete_node(self, del_keys: List[str], del_values: List[str]) -> str:
        if (len(del_keys) != len(del_values)):
            self.logging.info("error: inconsistent key / values: del_keys=" + del_keys \
                  + " - del_values="+del_values)
            return -1
        ## create the query strings
        string_del = ""
        for index, del_key in enumerate(del_keys):
            del_value = del_values[index]
            string_del = string_del + "n." + del_key + " = '" + del_value+"'"
            if index < len(del_keys)-1:
                string_del = string_del + " AND "
        ## create and run the final query
        query_string = f'''
        MATCH (n)
        WHERE {string_del}
        DETACH DELETE n;
        '''
        ## run the query
        response = self.query(query_string)
        return self.success_response + " - deleted del_keys = " \
               + str(del_keys) + " - del_values = " + str(del_values)

    def delete_node_by_id(self, del_id: int) -> str:
        if (del_id == None):
            self.logging.info("error: del_id is None")
            return -1
        ## create and run the final query
        query_string = f'''
        MATCH (n)
        WHERE ID(n)={str(del_id)}
        DETACH DELETE n;
        '''
        ## run the query
        response = self.query(query_string)
        return self.success_response + " - deleted ID = " + str(del_id)

    def get_top_n_articles_for_label(self, 
                                     list_filter_entity_labels_1: List[str] = None, 
                                     list_filter_entity_attributes_1: List[str] = None, 
                                     list_filter_entity_operators_1: List[str] = None, 
                                     list_filter_entity_values_1: List[str] = None, 
                                     list_article_attributes: List[str] = None, 
                                     list_article_operators: List[str] = None, 
                                     list_article_values: List[str] = None,
                                     top_n: int = 10, 
                                     metric_norm: bool = True, 
                                     weight_mention: int = 100,
                                     format: str = "json",
                                     order_metric: str = None,
                                     options: str = None) -> any:
        if order_metric == None:
            order_metric = "count_metric_age_norm" if \
                            metric_norm == True else "count_metric"
        if options != None:
            pass
        return_fields = "ID(article), article{.*} "

        ## filter on specific type / class of entity 
        # (disease, article, gene, ...)
        subset_articles_query_1=""
        if list_filter_entity_labels_1 != None:
            if len(list_filter_entity_labels_1) > 0:
                for index, filter_entity_label in \
                        enumerate(list_filter_entity_labels_1):
                    filter_entity_match_clause = f"MATCH (s_1_{str(index)}:\
                        {filter_entity_label})<--\
                            (subset_articles_1:Article)"
                    filter_entity_where_clause = f"WHERE toLower(s_1_{str(index)}.\
                        {list_filter_entity_attributes_1[index]}) \
                        {list_filter_entity_operators_1[index]} \
                            '{list_filter_entity_values_1[index].lower()}'"
                    if list_article_attributes != None:
                        if len(list_article_attributes) > 0:
                            filter_entity_where_clause += " and " + self.get_article_where_clause( \
                                "subset_articles_1",
                                list_article_attributes, 
                                list_article_operators, 
                                list_article_values)
                    subset_articles_query_1 += (
                        filter_entity_match_clause \
                        + filter_entity_where_clause )
            else:
                subset_articles_query_1 = f"MATCH \
                    (subset_articles_1:Article)"
                if list_article_attributes != None:
                    if len(list_article_attributes) > 0:
                        subset_articles_query_1 += " WHERE "
                        subset_articles_query_1 += self.get_article_where_clause( \
                            "subset_articles_1",
                            list_article_attributes, 
                            list_article_operators, 
                            list_article_values)
        
        ## define and run the final query
        #query_string_1 = f'''
        #MATCH (subset_articles_1:Article)-->{optional_pathway_link}(g{class_string})
        #    {where_clause} '''
        query_string_1 = subset_articles_query_1
        query_string_2 = '''
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
        '''
        query_string_3 = '''
        WITH count_subset_articles_1, subset_list_1, \
             mentions_subset_1_target, count_all 
        CALL { 
            WITH count_subset_articles_1, subset_list_1, \
                mentions_subset_1_target, count_all
            MATCH (mentions_subset_1:Article)-->(mentions_subset_1_target)
            WHERE mentions_subset_1 IN subset_list_1
            WITH count(mentions_subset_1) AS count_target
            RETURN count_target
        }
        '''
        query_string_4 = f'''
        UNWIND [mentions_subset_1_target.age_in_months, 1] AS age_to_one 
        WITH mentions_subset_1_target as article, count_all, count_target, \
                max(age_to_one) AS age_norm,
            (count_all + {str(weight_mention)} * count_target) as count_metric,
            (toFloat(count_all + {str(weight_mention)} * count_target) / max(age_to_one)) \
                as count_metric_age_norm
        RETURN {return_fields}, \
               count_all as f_total_citations, count_target as \
               f_total_citations_from_target, count_metric as \
               f_unnormalized_metric, count_metric_age_norm as \
               f_normalized_metric, age_norm as f_age_norm \
        ORDER BY {order_metric} DESC LIMIT {str(top_n)}
        '''

        query_string = query_string_1 + query_string_2 + query_string_3 \
                       + query_string_4

        response = self.query(query_string)
        response_list = [{'message':'no result found'}]
        ## create list from reponse, if the response exists
        if (response):
            if len(response) > 0:
                self.logging.info("format = "+ format)
                csv_df = pd.DataFrame(columns=[
                    'score','pubmed_id', 'pmc_id', 'title', 'epubdate', 'journal', 
                    'total_citations', 'citations_from_target'
                    ])
                csv_df.index.name = "index"

                dict_all_results = [dict(_) for _ in response ]
                if format == "csv":
                    for i, dict_single in enumerate(dict_all_results):
                        dict_single['list_filter_entity_values_1'] = ",".join(list_filter_entity_values_1)
                        if list_article_values != None:
                            dict_single['list_article_values'] = ",".join(list_article_values)
                        pmc_id = "NA"
                        if "pmc_id" in dict_single["article"]:
                            pmc_id = dict_single["article"]["pmc_id"]
                    
                        csv_df.loc[i] = \
                            [ "{:.4f}".format(round(dict_single['f_normalized_metric'], 4)),
                              dict_single["article"]["name"].replace(";", ","), 
                              pmc_id,
                              dict_single["article"]["b_title"].replace(";", ","), 
                              dict_single["article"]["epubdate"].replace(";", ","),
                              dict_single["article"]["journal"].replace(";", ","), 
                              dict_single["f_total_citations"], 
                              dict_single["f_total_citations_from_target"],
                            ]
                    response_list = csv_df.to_csv(sep = ";", index=False)

                elif format == "json":
                    response_list = dict_all_results
                else:
                    response_list = "error: format not in [csv, json]"
        return response_list


    def get_top_entities(self, concept_label: str, top_n: int = 10) \
            -> List[dict]:
        return_fields = "ID(entity), entity{.*}, \
                         count(entity) as count_mentions "
        class_string = ""
        optional_pathway_link = ""
        ## filter on specific type / class of entity (disease, 
        # article, gene, ...)
        if concept_label:
            ## special format for the article type string
            if concept_label == "article" or concept_label == "Article":
                concept_label = "Article"
            if concept_label == "keyword":
                concept_label = "Keyword"
            if concept_label in ["GO_BP", "GO_CC", "GO_MF", "pathway_kegg", \
                                 "pathway_reactome", "pathway_wikipathways", \
                                 "pathway_biocarta", "pathway_netpath", \
                                 "pathway_pid", "drug"]:
                optional_pathway_link ="--(any_gene:gene)"

            class_string = ":"+concept_label
        else:
            return {'results':{'message': 'Error: concept_label = None'}}
            
        ## define and run the final query
        query_string = f'''
        MATCH (entity{class_string}){optional_pathway_link}--(a:Article) 
        RETURN {return_fields}
        ORDER BY count_mentions DESC LIMIT {str(top_n)}
        '''

        response = self.query(query_string)
        response_list = [{'message':'no result found'}]
        ## create list from reponse, if the response exists
        if (response):
            if len(response) > 0:
                dict_all_results = [dict(_) for _ in response ]
                response_list = dict_all_results

        return response_list

        
    def search_term_in_label(self, concept_label: str, concept_field: str, 
                             search_operator: str, term, return_field: str) \
                                 -> list:
        with self.driver.session() as session:
            result = session.read_transaction(
                        self._search_term_in_label, concept_label, 
                        concept_field, search_operator, term, 
                        return_field)
            return result
    
    def search_id_in_label(self, concept_label: str, concept_field: str, 
                           search_operator: str, term: str) -> list:
        with self.driver.session() as session:
            result = session.read_transaction(
                        self._search_id_in_label, concept_label, 
                        concept_field, search_operator, term)
            return result

    def get_all_nodes_for_label(self, concept_label: str, return_field: str):
        with self.driver.session() as session:
            result = session.read_transaction(self._get_all_nodes_for_label, concept_label, return_field)
            return result

    def create_pathway_for_gene(self, gene_name: str, pathway_name: str, 
                                pathway_label: str) -> list:
        with self.driver.session() as session:
            result = session.write_transaction(self._create_pathway_for_gene, gene_name, pathway_name, pathway_label)
            return result

    def create_object_for_entity(self, entity_label: str, entity_name: str, 
                                 object_label: str, object_name: str, 
                                 object_attributes: List[str], 
                                 object_values: List[str], 
                                 relationship_str: str, 
                                 entity_identifier: str = "p") -> list:
        with self.driver.session() as session:
            result = session.write_transaction(self._create_object_for_entity, entity_label, entity_name, object_label, object_name, object_attributes, object_values, relationship_str, entity_identifier)
            return result

    def has_gene_any_pathway(self, gene_name: str):
        with self.driver.session() as session:
            result = session.read_transaction(self._has_gene_any_pathway, 
                                              gene_name)
            return result
    
    def set_tag_node_attribute(self, node_id: int, attribute_name: str, 
                               attribute_value: str) -> list:
        with self.driver.session() as session:
            result = session.write_transaction(self._set_tag_node_attribute, 
                                               node_id, attribute_name, 
                                               attribute_value)
            return result

    def set_node_attribute(self, node_label: str, node_attribute: str,
                           node_value: str, attribute_name: str, 
                           attribute_value: str) -> list:
        with self.driver.session() as session:
            result = session.write_transaction(self._set_node_attribute, 
                        node_label, node_attribute,
                        node_value, attribute_name, 
                        attribute_value)
            return result

    ## outdated: we don't want to use iso_sortpubdate anymore, 
    # since it is already implemented by the epubdate attribute
    def add_iso_sortpubdate_for_all_articles(self):
        with self.driver.session() as session:
            result = session.write_transaction(
                        self._add_iso_sortpubdate_for_all_articles)
            return result

    def where_exists_field(self, concept_label: str, concept_field: str, 
                           return_field: str, negate = False) -> list:
        with self.driver.session() as session:
            result = session.read_transaction(self._where_exists_field, 
                                              concept_label, concept_field, 
                                              return_field, negate)
            return result
    
    def add_age_for_all_articles(self) -> list:
        with self.driver.session() as session:
            result = session.write_transaction(self._add_age_for_all_articles)
            return result

    def add_mygene_information(self):
        gene_list = self.where_exists_field("gene", "entrezgene", "name", 
                                            negate = True)
        self.logging.info("genes without entrezgene: " + str(len(gene_list)))
        sum_normalized = 0
        sum_malformated = 0
        correct_gene_names =[]
        for gene_name in gene_list:
            if gene_name.startswith("Gene:"):
                if gene_name.split("Gene:")[1].isnumeric():
                    sum_normalized += 1
                    correct_gene_names.append(gene_name)
                else:
                    #self.logging.info("The following gene is not normalized correctly: "\
                    # + gene_name)
                    sum_malformated += 1
            else: 
                #self.logging.info("The following gene is not normalized correctly: " \
                # + gene_name)
                sum_malformated += 1
        self.logging.info("There are "+str(sum_normalized)+" normalized genes and " \
              + str(sum_malformated)+" malformated gene names")

        ## transform gene-names to entrez ids
        entrez_gene_ids = [ gene_id.split(":")[1] for gene_id in \
                            correct_gene_names]
        ## start the query (batches of 1000 are processed)
        ginfo = self.mg.querymany(entrez_gene_ids, scopes='entrezgene', 
                                  fields="symbol,name,alias,entrezgene,"\
                                         "refseq.rna,ensembl.gene,taxid,"\
                                         "pathway.kegg,pathway.reactome,"\
                                         "pathway.biocarta,pathway.netpath,"\
                                         "pathway.wikipathways,pathway.pid,"\
                                         "go,type_of_gene,summary",
                                         returnall = True)

        ## get all information for one gene by using the mygene-package
        ## we are adding more entities: pathways, go-terms
        index_ginfo = 0
        for gene_query in ginfo['out']:
            if (index_ginfo %50 == 0):
                self.logging.info("index = "+str(index_ginfo))
            gene_id = self.search_id_in_label("gene", "name", "=", "Gene:" \
                                              + str(gene_query['query']))[0]
            
            ## if the gene cannot be found by mygene, don't search for it again
            if 'notfound' in gene_query:
                if gene_query['notfound'] == True:
                    gene_query['entrezgene'] = gene_query['query']

            if 'ensembl' in gene_query:
                query_key = gene_query['ensembl']
                ensembl_str = ", ".join(get_ensembl_genelist(query_key))
                self.set_tag_node_attribute(gene_id, "ensembl_ids", 
                                            add_quotes(ensembl_str))
            if 'alias' in gene_query:
                alias_value = "<empty>"
                if isinstance(gene_query['alias'], list):
                    alias_value = add_quotes(", ".join(gene_query['alias']))
                else:
                    alias_value = add_quotes(gene_query['alias'])
                    
                self.set_tag_node_attribute(gene_id, "alias", alias_value)
            if 'refseq' in gene_query:
                for refseq_attribute in gene_query['refseq']:
                    refseq_attribute_name = 'refseq_'+refseq_attribute
                    if isinstance(gene_query['refseq'][refseq_attribute], 
                                  list):
                        refseq_attribute_value = add_quotes(
                            ", ".join(gene_query['refseq'][refseq_attribute]))
                    else:
                        refseq_attribute_value = add_quotes(
                            gene_query['refseq'][refseq_attribute])
                    self.set_tag_node_attribute(
                        gene_id, refseq_attribute_name, refseq_attribute_value)
            
            if 'go' in gene_query:
                #self.logging.info(gene_query)
                for go_category in gene_query['go']:
                #if 'BP' in gene_query['go']:
                    go_category_list = gene_query['go'][go_category]
                    if (isinstance(go_category_list, dict)):
                        go_category_list = [go_category_list]
                    
                    for go_term in go_category_list:
                        #self.logging.info(go_term)
                        object_attributes = ['evidence', 'gocategory', 
                                             'qualifier', 'term']
                        
                        evidence_str = "empty_evidence"
                        qualifier_str = "empty_qualifier"
                        term_str = "empty_term"
                        if ('evidence' in go_term.keys()):
                            evidence_str = go_term['evidence']
                        if ('qualifier' in go_term.keys()):
                            qualifier_str = go_term['qualifier']
                        if ('term' in go_term.keys()):
                            term_str = go_term['term']

                        object_values = [replace_quotes(evidence_str),
                                         go_category,
                                         replace_quotes(qualifier_str),
                                         replace_quotes(term_str)]
                        if go_category == "BP":
                            object_label = "GO_BP"
                            go_rel = "-[:GO_BP_contains_gene]->"
                        elif go_category == "MF":
                            object_label = "GO_MF"
                            go_rel = "-[:GO_MF_contains_gene]->"
                        elif go_category == "CC":
                            object_label = "GO_CC"
                            go_rel = "-[:GO_CC_contains_gene]->"
                        else:
                            raise Exception("wrong go category "+go_category)
                        self.create_object_for_entity(
                            entity_label="gene", entity_name="Gene:" \
                            + str(gene_query['query']), 
                            object_label = object_label, 
                            object_name = go_term['id'], 
                            object_attributes = object_attributes, 
                            object_values = object_values, 
                            relationship_str = go_rel)
                        
            if 'pathway' in gene_query:
                #self.logging.info(gene_query)
                for pathway_category in gene_query['pathway']:
                #if 'BP' in gene_query['go']:
                    pathway_category_list = gene_query['pathway']\
                                            [pathway_category]
                    if (isinstance(pathway_category_list, dict)):
                        pathway_category_list = [pathway_category_list]
                    
                    for pathway_term in pathway_category_list:
                        #self.logging.info(go_term)
                        object_attributes = ['id','label']
                        object_values = [replace_quotes(pathway_term['id']),
                                         replace_quotes(pathway_term['name'])]
                        if pathway_category not in ["kegg", "reactome", 
                                                    "wikipathways", "netpath",
                                                    "pid", "biocarta"]:
                            raise Exception("wrong pathway category " \
                                            + pathway_category)
                        else:
                            object_label = "pathway_"+str(pathway_category)
                            pathway_rel = "-[:"+pathway_category \
                                + "_contains_gene]->"

                        self.create_object_for_entity(
                            entity_label="gene", entity_name="Gene:" \
                            + str(gene_query['query']), 
                            object_label = object_label, 
                            object_name = pathway_term['id'], 
                            object_attributes = object_attributes, 
                            object_values = object_values, 
                            relationship_str = pathway_rel)
            
            simple_fields = ["taxid", "symbol", "type_of_gene", "summary",
                             "entrezgene"]
            for simple_field in simple_fields:
                if simple_field in gene_query:
                    self.set_tag_node_attribute(
                        gene_id, simple_field, 
                        add_quotes(gene_query[simple_field]))
            #"query;_id;alias;_score;ensembl;entrezgene;name;refseq;symbol;
            # taxid;pathway;go;type_of_gene;summary"
            index_ginfo = index_ginfo + 1

    def add_species_information(self):
        species_list = self.where_exists_field("species", "current_name", "name", 
                                            negate = True)
        self.logging.info("species without current_name: " + str(len(species_list)))
        sum_normalized = 0
        sum_malformated = 0
        correct_species_names =[]
        for species_name in species_list:
            if species_name.startswith("Species:"):
                if species_name.split("Species:")[1].isnumeric():
                    sum_normalized += 1
                    correct_species_names.append(species_name)
                else:
                    #self.logging.info("The following gene is not normalized correctly: "\
                    # + gene_name)
                    sum_malformated += 1
            else: 
                #self.logging.info("The following gene is not normalized correctly: " \
                # + gene_name)
                sum_malformated += 1
        self.logging.info("There are "+str(sum_normalized)+" normalized species and " \
              + str(sum_malformated)+" malformated species names")

        ## transform species-names to ncbi ids
        ncbi_species_ids = [ species_id.split(":")[1] for species_id in \
                            correct_species_names]

        ## get all information for one gene by using the mygene-package
        ## we are adding more entities: pathways, go-terms
        index_sinfo = 0
        for ncbi_species_id in ncbi_species_ids:
            if (index_sinfo %20 == 0):
                self.logging.info("index = "+str(index_sinfo))
            species_id = self.search_id_in_label("species", "name", "=", "Species:" \
                                              + str(ncbi_species_id))[0]
            organism_id = str(ncbi_species_id)
            URL = "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=" + organism_id + "&lvl=0"
            #self.logging.info("URL = " + URL)
            fp = urllib.request.urlopen(URL)
            #self.logging.info("DONE getting html")
            mybytes = fp.read()

            html_string = mybytes.decode("utf8")
            fp.close()

            species_fields = {}
            current_name_index = html_string.find ( "<legend>current name</legend>" )
            current_remaining = html_string[current_name_index:]
            index_start = current_remaining.find("<strong>") + 8
            index_end = current_remaining.find("</strong>")
            species_fields["current_name"] = current_remaining[index_start:index_end].replace("<i>", "").replace("</i>", "")

            if len(species_fields["current_name"]) > 0:
                #print(species_fields["current_name"])
                common_name_index = html_string.find ( "Genbank common name:" )
                common_remaining = html_string[common_name_index:]
                index_start = common_remaining.find("<strong>") + 8
                index_end = common_remaining.find("</strong>")
                species_fields["common_name"] = common_remaining[index_start:index_end]
                #print(common_name)
                blast_name_index = html_string.find ( "NCBI BLAST name:" )
                blast_remaining = html_string[blast_name_index:]
                index_start = blast_remaining.find("<strong>") + 8
                index_end = blast_remaining.find("</strong>")
                species_fields["blast_name"] = blast_remaining[index_start:index_end]
                #print(blast_name)
                simple_fields = ["current_name", "common_name", "blast_name"]
                for simple_field in simple_fields:
                    self.set_tag_node_attribute(
                        species_id, simple_field, 
                        add_quotes(species_fields[simple_field]))
            else:
                print("no entry found")
                
            #"query;_id;alias;_score;ensembl;entrezgene;name;refseq;symbol;
            # taxid;pathway;go;type_of_gene;summary"
            index_sinfo = index_sinfo + 1

    def add_disease_information(self):
        disease_file = "/global/ctdbase_disease.csv"
        str_header = "DiseaseName,DiseaseID,AltDiseaseIDs,Definition,ParentIDs,TreeNumbers,ParentTreeNumbers,Synonyms,SlimMappings"
        header = str_header.split(",")
        df_diseases = pd.read_csv(disease_file, skiprows=29, names = header)
        diseases_list = self.where_exists_field("disease", "disease_name", "name", 
                                            negate = True)
        self.logging.info("disease without current_name: " + str(len(diseases_list)))
        sum_normalized = 0
        sum_malformated = 0
        correct_disease_names =[]
        for disease_name in diseases_list:
            if disease_name.startswith("Disease:"):
                correct_disease_names.append(disease_name)
                sum_normalized += 1   
            else:
                sum_malformated += 1
        self.logging.info("There are "+str(sum_normalized)+" normalized disease and " \
              + str(sum_malformated)+" malformated disease names")

        ## transform disease-names
        disease_ids = [ ":".join(dis_id.split(":")[1:]) for dis_id in \
                            correct_disease_names]

        ## get all information for one gene by using the mygene-package
        ## we are adding more entities: pathways, go-terms
        for index, disease_id in enumerate(disease_ids):
            if (index %100 == 0):
                self.logging.info("index = "+str(index))
            disease_db_id = str(self.search_id_in_label("disease", "name", "=", "Disease:" \
                                              + str(disease_id))[0])
            
            disease_split = disease_id.split(":")
            disease_fields = {}
            if len(disease_split) >= 2:
                disease = disease_id
            else:
                disease = "wrong format"

            data_found = False
            if (disease in list(df_diseases["DiseaseID"])):
                disease_fields['disease_id'] = df_diseases.loc[df_diseases["DiseaseID"] == disease, "DiseaseID"].values[0]
                disease_fields['disease_name']  = df_diseases.loc[df_diseases["DiseaseID"] == disease, "DiseaseName"].values[0]
                disease_fields['disease_definition']  = df_diseases.loc[df_diseases["DiseaseID"] == disease, "Definition"].values[0]
                disease_fields['disease_altids']  = df_diseases.loc[df_diseases["DiseaseID"] == disease, "AltDiseaseIDs"].values[0]
                disease_fields['disease_synonyms']  = df_diseases.loc[df_diseases["DiseaseID"] == disease, "Synonyms"].values[0]
                data_found = True
            elif (disease in str(df_diseases["AltDiseaseIDs"])):
                disease_fields['disease_id']  = df_diseases[df_diseases["AltDiseaseIDs"].fillna("").str.contains(disease)]["DiseaseID"].values[0]
                disease_fields['disease_name'] = df_diseases[df_diseases["AltDiseaseIDs"].fillna("").str.contains(disease)]["DiseaseName"].values[0]
                disease_fields['disease_definition'] = df_diseases[df_diseases["AltDiseaseIDs"].fillna("").str.contains(disease)]["Definition"].values[0]
                disease_fields['disease_altids'] = df_diseases[df_diseases["AltDiseaseIDs"].fillna("").str.contains(disease)]["AltDiseaseIDs"].values[0]
                disease_fields['disease_synonyms'] = df_diseases[df_diseases["AltDiseaseIDs"].fillna("").str.contains(disease)]["Synonyms"].values[0]
                data_found = True

            if data_found:
                simple_fields = ["disease_id", "disease_name", "disease_definition", "disease_altids", "disease_synonyms"]
                for simple_field in simple_fields:
                    self.set_tag_node_attribute(
                        disease_db_id, simple_field, 
                        add_quotes(disease_fields[simple_field]))


    def add_chemical_information(self):
        chemical_list = self.where_exists_field("chemical", "mesh_name", "name", 
                                            negate = True)
        self.logging.info("chemical without current_name: " + str(len(chemical_list)))
        sum_normalized = 0
        sum_malformated = 0
        correct_chemicals_names =[]
        for chemical_name in chemical_list:
            if chemical_name.startswith("Chemical:MESH:"):
                sum_normalized += 1
                correct_chemicals_names.append(chemical_name)
            else: 
                #self.logging.info("The following gene is not normalized correctly: " \
                # + gene_name)
                sum_malformated += 1
        self.logging.info("There are "+str(sum_normalized)+" normalized chemical and " \
                + str(sum_malformated)+" malformated chemical names")

        ## transform species-names to ncbi ids
        chemical_ids = [ species_id.split(":")[2] for species_id in \
                            correct_chemicals_names]

        ## get all information for one gene by using the mygene-package
        ## we are adding more entities: pathways, go-terms
        for index, chemical_id in enumerate(chemical_ids):
            if (index %20 == 0):
                self.logging.info("index = "+str(index))
            chemical_db_id = self.search_id_in_label("chemical", "name", "=", "Chemical:MESH:" \
                                                + str(chemical_id))[0]
            URL = "https://meshb.nlm.nih.gov/record/ui?ui=" + str(chemical_id)
            #self.logging.info("URL = " + URL)
            
            try: 
                fp = urllib.request.urlopen(URL)
            except urllib.error.HTTPError:
                self.logging.info("URL = " + URL + " is not accessible")
            else:
                mybytes = fp.read()
                html_string = mybytes.decode("utf8")
                fp.close()
                http_success = True

            if (http_success):
                chemical_attributes = {}

                mesh_index = html_string.find ( "<dt>MeSH Heading" )
                mesh_remaining = html_string[mesh_index:]
                index_start = mesh_remaining.find("<dd>") + 4
                index_end = mesh_remaining.find("</dd>")
                mesh_heading = mesh_remaining[index_start:index_end]
                chemical_attributes["mesh_name"] = mesh_heading

                # check if the MeSH Heading not exists
                if len(mesh_heading) == 0:
                    ## then search for MeSH Supplementary
                    mesh_index = html_string.find ( "<dt>MeSH Supplementary" )
                    mesh_remaining = html_string[mesh_index:]
                    index_start = mesh_remaining.find("<dd>") + 4
                    index_end = mesh_remaining.find("</dd>")
                    mesh_heading = mesh_remaining[index_start:index_end]
                    chemical_attributes["mesh_name"] = mesh_heading
                    note_index = html_string.find ( "<dt>Note" )
                    note_remaining = html_string[note_index:]
                    index_start = note_remaining.find("<dd>") + 4
                    index_end = note_remaining.find("</dd>")
                    note = note_remaining[index_start:index_end]
                    chemical_attributes["note"] = note
                    source_index = html_string.find ( "<dt>Source" )
                    source_remaining = html_string[source_index:]
                    index_start = source_remaining.find("<dd>") + 4
                    index_end = source_remaining.find("</dd>")
                    source = source_remaining[index_start:index_end]
                    chemical_attributes["source"] = source
                    

                if len(mesh_heading) > 0:
                    data_found = True
                    scope_note_index = html_string.find ( "<dt>Scope Note" )
                    scope_note_remaining = html_string[scope_note_index:]
                    index_start = scope_note_remaining.find("<dd>") + 4
                    index_end = scope_note_remaining.find("</dd>")
                    scope_note = scope_note_remaining[index_start:index_end]
                    chemical_attributes["scope_note"] = scope_note
                    
                    entry_terms_index = html_string.find ( "Entry Term(s)")
                    entry_terms_remaining = html_string[entry_terms_index:]
                    entry_terms = []
                    
                    more_entries = True
                    entries_more = entry_terms_remaining
                    while more_entries == True:
                        next_entry_index = entries_more.find("<dd>")
                        next_heading_index = entries_more.find("<dt>")
                        if next_entry_index >= 0:
                            if ( next_heading_index < next_entry_index) and (next_heading_index >= 0):
                                more_entries = False
                            else:
                                index_start = next_entry_index + 4
                                index_end = entries_more.find("</dd>")
                                entry_term = entries_more[index_start: index_end]
                                entry_terms.append(entry_term.strip())
                                entries_more = entries_more[index_end+5:]
                        else:
                            more_entries = False            
                    entry_terms_str = ", ".join(entry_terms)
                    chemical_attributes["entry_terms"] = entry_terms_str
                    
                    
                    pharm_actions_index = html_string.find ( "Pharm Action")
                    pharm_actions_remaining = html_string[pharm_actions_index:]
                    pharm_actions = []
                    
                    more_entries = True
                    entries_more = pharm_actions_remaining
                    while more_entries == True:
                        next_entry_index = entries_more.find("<a class=\"textLink_")
                        next_heading_index = entries_more.find("<dt>")
                        if next_entry_index >= 0:
                            if ( next_heading_index < next_entry_index) and (next_heading_index >= 0):
                                more_entries = False
                            else:
                                entries_more = entries_more[next_entry_index:]
                                entries_more = entries_more[entries_more.find(">")+1:]
                                index_start = 0
                                index_end = entries_more.find("</a>")
                                entry_term = entries_more[index_start: index_end]
                                pharm_actions.append(entry_term.strip())
                                entries_more = entries_more[index_end+5:]
                        else:
                            more_entries = False            
                    pharm_actions_str = ", ".join(pharm_actions)
                    chemical_attributes["pharmacological_actions"] = pharm_actions_str
                    
                    previous_index = html_string.find ( "Previous Indexing")
                    previous_remaining = html_string[previous_index:]
                    index_start = previous_remaining.find("<dd>") + 4
                    index_end = previous_remaining.find("</dd>")
                    previous = previous_remaining[index_start:index_end]
                    chemical_attributes["previous_indexing"] = previous
                    
                if data_found:
                    simple_fields = chemical_attributes.keys()
                    for simple_field in simple_fields:
                        self.set_tag_node_attribute(
                            chemical_db_id, simple_field, 
                            add_quotes(chemical_attributes[simple_field]))

    def run_node_embedding(self,
                           graph_creation: str = None,
                           embedding_attribute_128dim: str = "embedding",
                           embedding_attribute_2dim_prefix: str = "embedding_global",
                           ):
        ## check if the graph structure exists, then delete it
        check_query = '''
        CALL gds.graph.exists('knowledgeGraph')
        YIELD graphName, exists'''
        result = self.query(check_query)
        if result[0].data()['exists']:
            drop_query = "CALL gds.graph.drop('knowledgeGraph') YIELD graphName;"
            result = self.query(drop_query)
            print(result)

        result = self.query(graph_creation)

        ## run node2vec on neo4j
        graph_embedding = '''CALL gds.beta.node2vec.stream('knowledgeGraph', {concurrency: 4, iterations: 4, embeddingDimension: 128, walksPerNode: 50, walkLength: 80, returnFactor: 0.9, inOutFactor: 0.9})
        YIELD nodeId, embedding
        WITH nodeId, embedding
        MATCH (n)
        WHERE ID(n) = nodeId
        SET n.''' + f'''{embedding_attribute_128dim} = embedding
        RETURN count(nodeId)
        '''
        result = self.query(graph_embedding)

        ## get all nodes with their 128 dimensional embedding
        query = f'''Match (n) WHERE EXISTS(n.{embedding_attribute_128dim}) RETURN DISTINCT id(n), n.name, n.label, n.b_title, labels(n), n.{embedding_attribute_128dim}'''
        result = self.query(query)

        ## add embeddings to numpy array
        
        # Preallocate arrays
        A = None
        annotation = []
        title = []
        labels = []
        ids = []
        names = []
        for index, rec in enumerate(result):
            embedding = rec.data().get(f'''n.{embedding_attribute_128dim}''')
            if embedding is not None:
                embedding = np.array(embedding)  # Convert list to NumPy array
                if A is None:
                    A = np.empty((len(result), embedding.shape[0]))
                A[index] = embedding
            else:
                self.logging.info("embedding is none - did not find data in n." + embedding_attribute_128dim)
            annotation.append(rec.data().get('n.label'))
            title.append(rec.data().get('n.b_title'))
            ids.append(rec.data().get('id(n)'))
            names.append(rec.data().get('n.name'))
            labels.append(rec.data().get('labels(n)')[0] if rec.data().get('labels(n)') else None)
        
        # Trim the arrays if necessary
        if A is not None:
            A = A[:len(result)]

            self.logging.info("Start: TSNE embedding")
            ## run tsne dim reduction
            X_embedded = TSNE(n_components=2, learning_rate='auto',
                    init='random', perplexity=30, n_iter = 2000).fit_transform(A)
            X_embedded_annotation = pd.DataFrame(X_embedded, columns = ['x','y'])
            X_embedded_annotation['annotation'] = annotation
            X_embedded_annotation['labels'] = labels
            X_embedded_annotation['title'] = title
            X_embedded_annotation['id'] = ids
            X_embedded_annotation['name'] = names
            self.logging.info("DONE: TSNE embedding")

            self.logging.info("Start: writing embedding to neo4j")
            ## write it to neo4j
            for index, row in X_embedded_annotation.iterrows():
                if index % 5000 == 0:
                    self.logging.info("index = " + str(index))
                id = row['id']
                x = row['x']
                y = row['y']
                str_query = f'''
                MATCH (n)
                WHERE id(n) = {id}
                SET n.{embedding_attribute_2dim_prefix}_x = {x},
                n.{embedding_attribute_2dim_prefix}_y = {y}
                '''
                result = self.query(str_query,log_queries = False)
            self.logging.info("DONE: writing embedding to neo4j")
        else:
            self.logging.info("Embedding matrix A is None - cannot continue with embedding. Probably the neo4j graph embedding failed.")



    ## convert a neo4j query into a json graph dictionary
    ## assertion: query_string ends with RETURN {nodes:list_nodes, 
    # edges:list_relations}, see cytoscape example
    def neo4j_response_to_json(self, query_string: str,
            base_path = "/input", run_node_embedding: bool = True ) \
            -> List[dict]:
        json_path = os.path.join(base_path, "cytoscape_attributes.json")

        if not ('RETURN {nodes:list_nodes' \
                in query_string):
            raise ValueError("query_string does not contain the required "\
                             "'RETURN {nodes:list_nodes' - instead: "\
                             "query_string=", query_string)
        
        response = self.query(query_string)
        response_list = [{'message':'no result found'}]
        cyto_graph = None
        graph_data = []
        ## create list from reponse, if the response exists
        if (response):
            if len(response) > 0:
                response_list = [dict(_) for _ in response]
            if '{nodes:list_nodes, edges:list_relations}' in response_list[0]:
                cyto_graph =  response_list[0]['{nodes:list_nodes, '\
                                            'edges:list_relations}']

                node_factory = Node_Factory(json_path = json_path)
                if ( isinstance(cyto_graph, dict) ):
                    node_dict = {}
                    edge_dict = {}
                    if len(cyto_graph['nodes']) > 0:
                        for node in cyto_graph['nodes']:
                            node_dict[node.id] = node
                        for node in node_dict.values():
                            node_instance = node_factory.get_instance(
                                node_class = list(node.labels)[0], 
                                node_id = node.id, 
                                node_name = node._properties["name"], 
                                node_properties= node._properties)

                            data_dict = {}
                            data_dict['id'] = str(node_instance.id)
                            data_dict['node_class'] = node_instance.class_name

                            data_dict['color'] = node_instance.color
                            data_dict['label'] = node_instance.label
                            data_dict['tooltip'] = node_instance.tooltip
                            data_dict['opacity'] = node_instance.opacity
                            data_dict['size'] = node_instance.size
                            if "embedding_global_x" in node._properties:
                                data_dict_position = {'x': node._properties["embedding_global_x"], 
                                                     'y': node._properties["embedding_global_y"]}
                            else:
                                data_dict_position = {'x': 0, 
                                                     'y': 0}


                            graph_data.append({'data': data_dict, 'group':'nodes', 'position': data_dict_position})
                        
                    else:
                        self.logging.info("query returned 0 results -> skip json graph")
                        return graph_data

                    for edge in cyto_graph['edges']:
                        edge_dict[edge.id] = edge
                    for edge in edge_dict.values():
                        data_dict = {}
                        source_str = str(edge.start_node.id)
                        data_dict["source"] = source_str
                        target_str = str(edge.end_node.id)
                        data_dict["target"] = target_str
                        data_dict['id'] = "_".join([source_str, target_str])
                        data_dict['edge_class'] = edge.type
                        data_dict['label'] = edge.type
                        data_dict['tooltip'] = data_dict["id"]
                        graph_data.append({'data': data_dict, 'group':'edges'})

                    if (run_node_embedding):
                        node_list = [ node for node in graph_data if \
                            ( node['group'] == "nodes" ) ]
                        node_id_list = [ str(node['data']['id']) for node in node_list]

                        edge_list = [ edge for edge in graph_data if \
                            (edge['group'] == "edges" and edge['data']['source'] \
                            in node_id_list and edge['data']['target'] \
                            in node_id_list )]
                        for node in node_list:
                            node['data']['value'] = node['data']['id']
                            node['data']['name'] = node['data']['id']
                            node['data']['id'] = str(node['data']['id'])

                        cytoscape_graph = {
                            'data': [], 'directed': False,
                            'multigraph': False, 'elements': {'nodes': node_list,
                            'edges': edge_list}
                        }
                        G = nx.cytoscape_graph(cytoscape_graph)
                        #node2vec = Node2Vec(G, dimensions=64, walk_length=30, num_walks=200, workers=4)
                        node2vec = Node2Vec(G, dimensions=64, walk_length=30, num_walks=300, workers=4)
                        model = node2vec.fit(window=10, min_count=1, batch_words=4)
                        y = np.array([ model.wv.index_to_key[index] for index in range(len(model.wv)) ])
                        X = np.empty((0, 64))
                        for index in range(len(model.wv)):
                            X = np.vstack([X, model.wv[index]])
                        n_components = 2
                        tsne = TSNE(n_components)
                        tsne_result = tsne.fit_transform(X)
                        tsne_result_df = pd.DataFrame({'tsne_1': tsne_result[:,0], 'tsne_2': tsne_result[:,1], 'label': y})

                        #normalized_df=(tsne_result_df-tsne_result_df.min())/(tsne_result_df.max()-tsne_result_df.min())
                        x_norm = tsne_result_df['tsne_1']
                        x_norm = 2000 * len(x_norm) / 50 * (x_norm-x_norm.min())/(x_norm.max()-x_norm.min())
                        
                        y_norm = tsne_result_df['tsne_2']
                        y_norm = 2000 * len(y_norm) / 50 * (y_norm-y_norm.min())/(y_norm.max()-y_norm.min())

                        tsne_result_df['tsne_1'] = x_norm
                        tsne_result_df['tsne_2'] = y_norm

                        for node in graph_data:
                            if (node['group'] == 'nodes'):
                                node['position'] = {'x': float(tsne_result_df.loc[tsne_result_df['label'] == node['data']['id'] ,'tsne_1']),
                                                    'y': float(tsne_result_df.loc[tsne_result_df['label'] == node['data']['id'] ,'tsne_2'])}
            else:
                self.logging.info("query returned 0 results -> skip json graph")

        else:
            self.logging.info("query returned 0 results -> json graph")

        return graph_data


    def get_cytoscape_query(self, query_key: str, 
            base_input_path = "/input",
            base_output_path = "/output",
            run_node_embedding: bool = True
            ) -> None:
        response = None
        query_input_path =  os.path.join(base_input_path, "cytoscape_queries.json")
        query_output_path = os.path.join(base_output_path, "cytoscape_query_results.json")

        ## run the query
        self.logging.info("accessing cytoscape queries.json")
        with open(query_output_path) as result_dict_file:
            result_dict = json.load(result_dict_file)
            ## return cached result if exists
            if query_key in result_dict:
                response = result_dict[query_key]['result']
            ## else run query and save result in cache
            else:
                result_dict[query_key] = {}
                # open the global json-file and perform the curation
                with open(query_input_path) as json_file:
                    cytoscape_queries = json.load(json_file)
                    if query_key in cytoscape_queries:
                        query = cytoscape_queries[query_key]['query']
                        response = self.neo4j_response_to_json(query, base_path = base_input_path, \
                            run_node_embedding = run_node_embedding)
                                        # Directly from dictionary
                        result_dict[query_key]['result'] = response
                    else:
                        self.logging.info("Could not find query: entry=" \
                            + str(query_key) )
                        response = [{"message": "Could not find query: " \
                            + str(query_key)}]
                        
                with open(query_output_path, 'w') as result_dict_file:
                    json.dump(result_dict, result_dict_file)
        self.logging.info("DONE runnig the query")
        return response

    def cache_cytoscape_results(self, run_node_embedding: bool = True):
        self.logging.info("START caching cytoscape results")
        ## global curation file
        cytoscape_queries_json = "/input/cytoscape_queries.json"
         ## cached results
        cytoscape_results_json = "/output/cytoscape_query_results.json"
        create_cytoscape_results_json = Path(cytoscape_results_json)
        create_cytoscape_results_json.touch(exist_ok=True)

        result_dict = {}
        with open(cytoscape_queries_json) as queries_json_file:
            cytoscape_queries = json.load(queries_json_file)
            for query_key in cytoscape_queries:
                self.logging.info("START with query: " + query_key)
                result_dict[query_key] = {}
                query = cytoscape_queries[query_key]['query']
                response = self.neo4j_response_to_json(query, \
                    run_node_embedding=run_node_embedding)
                result_dict[query_key]['result'] = response
                self.logging.info("DONE with query: " + query_key)
        with open(cytoscape_results_json, 'w') as result_dict_file:
            json.dump(result_dict, result_dict_file)
        self.logging.info("DONE caching cytoscape results")
    
    @staticmethod
    def _set_tag_node_attribute(tx, node_id: int, attribute_name: str, 
                                attribute_value: str) -> list:
        query = (
            "MATCH (n)"
            "WHERE ID(n) = "+str(node_id)+" "
            "SET n."+str(attribute_name)+" = "+str(attribute_value) + " "
            "RETURN count(n) AS count_id_results;"
        )
        result = tx.run(query, node_id = node_id, 
                        attribute_name = attribute_name, 
                        attribute_value = attribute_value)
        return [record["count_id_results"] for record in result]

    @staticmethod
    def _set_node_attribute(tx, node_label: str, node_attribute: str,
                           node_value: str, attribute_name: str, 
                           attribute_value: str) -> list:
        query = (
            "MATCH (n:"+str(node_label)+") "
            "WHERE n."+str(node_attribute)+" = '"+str(node_value)+"' "
            "SET n."+str(attribute_name)+" = '"+str(attribute_value) + "' "
            "RETURN count(n) AS count_id_results;"
        )
        result = tx.run(query, node_label = node_label, 
                        node_attribute = node_attribute, 
                        node_value = node_value,
                        attribute_name = attribute_name, 
                        attribute_value = attribute_value)
        return [record["count_id_results"] for record in result]

    @staticmethod
    def _has_gene_any_pathway(tx, gene_name: str) -> list:
        query = (
            "MATCH (g:gene)--(p:pathway)"
            "WHERE g.name = '"+gene_name+"' "
            "RETURN p.name AS name;"
        )
        result = tx.run(query, gene_name=gene_name)
        return [record["name"] for record in result]

    @staticmethod
    def _create_pathway_for_gene(tx, gene_name: str, pathway_name: str,
                                 pathway_label: str) -> list:
        query = (
            "MATCH (g:gene)"
            "WHERE g.name = '"+gene_name+"' "
            "MERGE (p:pathway { name: '" + pathway_name +"' }) "
            "ON CREATE SET p.label = '"+ pathway_label +"' "
            "MERGE (p)-[:pathway_contains_gene]->(g)"
            "RETURN p.name AS name;"
        )
        result = tx.run(query, gene_name = gene_name, 
                        pathway_name = pathway_name, 
                        pathway_label = pathway_label)
        return [record["name"] for record in result]

    ## create an object (i.e. pathway) for an entity (i.e. gene)
    ## relationship_str = "-[:pathway_contains_gene]->"
    @staticmethod
    def _create_object_for_entity(tx, entity_label: str, entity_name: str, 
                                  object_label: str, object_name: str, 
                                  object_attributes: List[str], 
                                  object_values: List[str], 
                                  relationship_str: str, 
                                  entity_identifier: str) -> list:
        object_attribute_list = []
        if len(object_attributes) != len(object_values):
            raise Exception("Wrong length for attribute list and attribute "\
                            "values: len(object_attribute)=" \
                            + str(len(object_attributes)) \
                            + " vs len(object_values)=" \
                            + str(len(object_values)))
        else:
            for index, attribute in enumerate(object_attributes):
                object_attribute_list.append(
                    " " + entity_identifier + "." + attribute + "='" \
                    + object_values[index]+"' ") 
        
        object_attribute_str = ",".join(object_attribute_list)
        query = (
            "MATCH (g:"+entity_label+") "
            "WHERE g.name = '"+entity_name+"' "
            "MERGE (p:"+object_label+" { name: '" + object_name +"' }) "
            "ON CREATE SET "+object_attribute_str+" "
            "ON MATCH SET "+object_attribute_str+" "
            "MERGE (p)"+relationship_str+"(g)"
            "RETURN p.name AS name;"
        )
        result = tx.run(query, entity_label = entity_label, 
                        entity_name = entity_name, 
                        object_label = object_label,
                        object_name = object_name, 
                        object_attributes = object_attributes, 
                        object_values = object_values, 
                        relationship_str = relationship_str, 
                        entity_identifier = entity_identifier)
        return [record["name"] for record in result]


    @staticmethod
    def _search_term_in_label(tx, concept_label: str, concept_field: str, 
                              search_operator: str, term: str, 
                              return_field: str) -> list:
        query = (
            "MATCH (p:"+concept_label+") "
            "WHERE toLower(p." + concept_field+") " + search_operator \
                + " toLower('"+term +"') "
            "RETURN p."+return_field+" AS name"
        )
        result = tx.run(query, concept_label = concept_label, 
                        concept_field = concept_field, 
                        search_operator = search_operator, 
                        term = term, return_field = return_field)
        return [record["name"] for record in result]

    @staticmethod
    def _where_exists_field(tx, concept_label: str, concept_field: str, 
                            return_field: str, negate: bool = False) -> list:
        negate_str = ""
        if negate:
            negate_str = " NOT "

        query_string = '''
                MATCH (p:{}) 
                WHERE {} p.{} IS NOT NULL 
                RETURN p.{} AS name 
            '''.format(concept_label, negate_str, concept_field, return_field)
        query = (
            query_string
        )
        result = tx.run(query, concept_label = concept_label, negate = negate,
                        concept_field = concept_field, 
                        return_field = return_field)
        return [record["name"] for record in result]

    @staticmethod
    def _search_id_in_label(tx, concept_label: str, concept_field: str, 
                            search_operator: str, term: str) -> list:
        query = (
            "MATCH (p:"+concept_label+") "
            "WHERE toLower(p."+concept_field+") " + search_operator \
                + " toLower('" + term + "') "
            "RETURN ID(p) AS n_id"
        )
        result = tx.run(query, concept_label = concept_label, 
                        concept_field = concept_field, 
                        search_operator = search_operator, term=term)
        return [record["n_id"] for record in result]

    @staticmethod
    def _get_all_nodes_for_label(tx, concept_label: str, return_field: str) \
            -> list:
        query = (
            "MATCH (p:"+concept_label+") "
            "RETURN p."+return_field+" AS name"
        )
        result = tx.run(query, concept_label = concept_label, 
                        return_field = return_field)
        return [record["name"] for record in result]

    @staticmethod
    def _add_iso_sortpubdate_for_all_articles(tx):
        query = (
            "MATCH (n:Article) "
            "WHERE NOT EXISTS(n.iso_sortpubdate) "
            "SET n.iso_sortpubdate = replace(split\
                (n.sortpubdate,(' '))[0],'/','-') "
            "RETURN count(n) as count_n "
            )
        result = tx.run(query)
        return [record["count_n"] for record in result]
    
    @staticmethod
    def _add_age_for_all_articles(tx):
        query = (
            "MATCH (n:Article) " 
            "WHERE size(n.epubdate) = 10 AND size(n.date_integration) = 10 "
            "SET n.age_in_days = duration.inDays(date(n.epubdate), "\
                "date(n.date_integration)).days, n.age_in_months = "\
                "duration.inMonths(date(n.epubdate), "\
                "date(n.date_integration)).months "
            "RETURN count(n) as count_n"
            )
        result = tx.run(query)
        return [record["count_n"] for record in result]

    @staticmethod
    def _cleanup_duplicated_edges(tx):
        result = tx.run("match ()-[r]->() match (s)-[r]->(e) with "\
                        "s,e,type(r) as typ, tail(collect(r)) as coll "\
                        "foreach(x in coll | delete x);")


    @staticmethod
    def _cleanup_null_nodes(tx) -> None:
        result = tx.run("MATCH (n) WHERE n.name=\"Null\" DETACH DELETE n;")
        
    @staticmethod
    def _clear_graph(tx) -> None:
        result = tx.run("MATCH (n) DETACH DELETE n ")

    @staticmethod
    def _setup_index(tx) -> None:
        result = tx.run(
            "CREATE INDEX IF NOT EXISTS FOR (n:Article) ON (n.name);")
        result = tx.run(
            "CREATE INDEX IF NOT EXISTS FOR (n:Keyword) ON (n.name);")
        result = tx.run(
            "CREATE INDEX IF NOT EXISTS FOR (n:disease) ON (n.name);")
        result = tx.run(
            "CREATE INDEX IF NOT EXISTS FOR (n:gene) ON (n.name);")
        result = tx.run(
            "CREATE INDEX IF NOT EXISTS FOR (n:chemical) ON (n.name);")
        result = tx.run(
            "CREATE INDEX IF NOT EXISTS FOR (n:species) ON (n.name);")
        result = tx.run(
            "CREATE INDEX IF NOT EXISTS FOR (n:mutation) ON (n.name);")
        result = tx.run(
            "CREATE INDEX IF NOT EXISTS FOR (n:cellline) ON (n.name);")

    @staticmethod
    def _calculate_and_write_article_rank(tx) -> None:
        ## ensure that Articles as well as the relationship exists 
        ## before running the graph projection
        query = """
        OPTIONAL MATCH (a:Article)-[:citing]-(:Article)
        WITH count(a) as citationCount
        WHERE citationCount > 0
        CALL gds.graph.project(
            'articleGraph',
            'Article',
            'citing'
        ) YIELD graphName
        RETURN graphName
        """
        result = tx.run(query)
        # Only proceed with article rank if graph was created
        if result.peek() is not None:
            query = """
            CALL gds.articleRank.write('articleGraph', {
                writeProperty: 'article_rank'
            })
            YIELD nodePropertiesWritten
            RETURN nodePropertiesWritten
            """
            result = tx.run(query)
            
            query = """
            CALL gds.graph.drop('articleGraph')
            YIELD graphName
            RETURN graphName
            """
            result = tx.run(query)


    @staticmethod
    def _create_citation_graph(tx, bioconcepts: str) -> None:
        str_adding_annotations = neo4j_create_entities_command(bioconcepts)
        date_now = str(datetime.now().strftime('%Y-%m-%d'))
        query = ("LOAD CSV WITH HEADERS FROM 'file:///data/citations.csv' "\
                 "AS line FIELDTERMINATOR '|' "
                "MERGE (p1:Article { name: line.article }) "
                "ON CREATE SET p1.a_name = line.article, "\
                    "p1.label = line.article, "\
                    "p1.b_title = line.article_title, "\
                    "p1.pmc_id = line.article_pmc_id, "\
                    "p1.epubdate = line.article_epubdate, "\
                    "p1.authors = line.article_authors, "\
                    "p1.journal = line.article_journal, "\
                    "p1.z_abstract = line.article_abstract, "\
                    "p1.date_integration = '" + date_now + "' "
                "ON MATCH SET p1.a_name = line.article, "\
                    "p1.label = line.article, "\
                    "p1.b_title = line.article_title, "\
                    "p1.pmc_id = line.article_pmc_id, "\
                    "p1.epubdate = line.article_epubdate, "\
                    "p1.authors = line.article_authors, "\
                    "p1.journal = line.article_journal, "\
                    "p1.z_abstract = line.article_abstract, "\
                    "p1.date_integration = '" + date_now + "' "
                "MERGE (p2:Article { name: line.reference }) "
                "ON CREATE SET p2.a_name = line.reference, "\
                    "p2.label = line.reference, "\
                    "p2.b_title = line.reference_title, "\
                    "p2.pmc_id = line.reference_pmc_id, "\
                    "p2.epubdate = line.reference_epubdate, "\
                    "p2.authors = line.reference_authors, "\
                    "p2.journal = line.reference_journal, "\
                    "p2.z_abstract = line.reference_abstract, "\
                    "p2.date_integration = '" + date_now + "' "
                "ON MATCH SET p2.a_name = line.reference, "\
                    "p2.label = line.reference, "\
                    "p2.b_title = line.reference_title, "\
                    "p2.pmc_id = line.reference_pmc_id, "\
                    "p2.epubdate = line.reference_epubdate, "\
                    "p2.authors = line.reference_authors, "\
                    "p2.journal = line.reference_journal, "\
                    "p2.z_abstract = line.reference_abstract, "\
                    "p2.date_integration = '" + date_now + "' "
                "FOREACH (keyword1 in split(line.article_keywords, ',') | "\
                    "MERGE (k1:Keyword { name: keyword1 }) MERGE "\
                    "(p1)-[:contains]->(k1) ) " ""
                "FOREACH (keyword2 in split(line.reference_keywords, ',') | "\
                    "MERGE (k2:Keyword { name: keyword2 }) "\
                    "MERGE (p2)-[:contains]->(k2) ) " \
                    + str_adding_annotations \
                    + "MERGE (p1)-[:citing]->(p2);")
        result = tx.run(query)