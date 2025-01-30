## neo4j-api.py ""
# flask API for the neo4j knowledge graph
import logging
import os 
import time
import configparser
import functools
from flask import Flask
from flask import jsonify
from flask import url_for
from flask import make_response
from flask_cors import CORS
from flask_restplus import Api, Resource
from flask_restplus import reqparse, inputs
from helper.neo4j_helper import Neo4j_Manager

## setup the logger to print to stdout and to the file
log_path = "/output"
log_file_name = "knowledge-graph-neo4j-helper.log"
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


flask_app = Flask(__name__)
CORS(flask_app)
## this solves the "No API definition provided." issue (no https supported)
check_use_https = os.getenv('USE_HTTPS', 'False').lower() \
                    in ('true', '1', 't')
if check_use_https:
    @property
    def specs_url(self):
        return url_for(self.endpoint('specs'), 
                       _external=True, 
                       _scheme='https')

    Api.specs_url = specs_url
## now construct the app
app = Api(app = flask_app, 
		  version = "1.0", 
		  title = "neo4j API", 
		  description = "interact with the neo4j knowledge graph")
name_space = app.namespace('api', description="Main APIs")

config_path = "/input/config.ini"
## general config
config = configparser.ConfigParser()
config.read(config_path)
project_name = config['GENERAL-settings']['project_name']
db_hostname_base = config['NEO4J-settings']['neo4j_hostname']
db_hostname = "-".join([db_hostname_base, project_name])
neo4j_bolt_base = config['NEO4J-settings']['neo4j_bolt']
neo4j_bolt_project = "-".join([neo4j_bolt_base, project_name])
noe4j_bolt_port = config['NEO4J-settings']['neo4j_bolt_port']
neo4j_bolt = ":".join([neo4j_bolt_project, noe4j_bolt_port])
neo4j_user = config['NEO4J-settings']['neo4j_user']
neo4j_password = config['NEO4J-settings']['neo4j_password']

# start
waittime = 0
logging.info("waiting "+ str(waittime)+" seconds before trying to connect to graph"\
      " on "+db_hostname)
time.sleep(waittime)
neo4j_manager = Neo4j_Manager(neo4j_bolt, neo4j_user, neo4j_password, logging = logging)

## define some argument parsers with argument definitions 
parser_normal_search = reqparse.RequestParser()
parser_normal_search.add_argument(
    'id', type=int, help="provide the ID as integer")
parser_normal_search.add_argument(
    'entity_label', type=str, default = "disease", help="entity label (article, disease, gene, species, "\
    "chemical, mutation, cellline)")
parser_normal_search.add_argument(
    'entity_fields', type=str, help="search fields separated by commas",
    default = "label", required=False)
parser_normal_search.add_argument(
    'search_operators', type=str, help="search_operators separated by commas",
    default = "CONTAINS", required=False)
parser_normal_search.add_argument('search_terms', default = "amyotrophic", type=str, help="search terms separated by commas")
parser_normal_search.add_argument('sort_by', type=str, help="sort by which attribute")
parser_normal_search.add_argument('sort_descending', type=inputs.boolean, default = True,  help="sort descending?")
parser_normal_search.add_argument('result_limit', type=int, help="result limit")
parser_normal_search.add_argument('format', type=str, default = "json", help="format in [json, csv]")

parser_neighbor_search = reqparse.RequestParser()
parser_neighbor_search.add_argument(
    'id', type=int, help="provide the ID as integer", required=True)
parser_neighbor_search.add_argument(
    'type', type=str, help="entity type (article, disease, gene, species, "\
    "chemical, mutation, cellline)")

parser_delete_node = reqparse.RequestParser()
parser_delete_node.add_argument(
    'del_keys', type=str, help="provide the selection keys separated "\
    "by commas")
parser_delete_node.add_argument(
    'del_values', type=str, help="provide the selection values separated by "\
    "commas")

parser_delete_node_by_id = reqparse.RequestParser()
parser_delete_node_by_id.add_argument(
    'del_id', type=int, help="enter the node id", required=True)

parser_redirect_relationships = reqparse.RequestParser()
parser_redirect_relationships.add_argument(
    'from_keys', type=str, help="provide the selection keys separated by "\
    "commas")
parser_redirect_relationships.add_argument(
    'from_values', type=str, help="provide the selection values separated "\
    "by commas")
parser_redirect_relationships.add_argument(
    'to_keys', type=str, help="provide the selection keys separated by "\
    "commas")
parser_redirect_relationships.add_argument(
    'to_values', type=str, help="provide the selection values separated by "\
    "commas")

parser_top_n_articles_for_label = reqparse.RequestParser()
parser_top_n_articles_for_label.add_argument(
    'count', type=int, help="provide count: how many articles should be "\
    "returned? (default = 10)", default = 10, required=False)
parser_top_n_articles_for_label.add_argument(
    'norm_by_age', type=inputs.boolean, help="should the metric be devided "\
    "by age? (default = True)", default="true", required=False)

## filter entities 1 (required)
parser_top_n_articles_for_label.add_argument(
    'filter_entity_labels_1', type=str, help="provide filter_entity_labels (disease, gene, chemical, "\
    "species, ...", default="disease", required=True)
parser_top_n_articles_for_label.add_argument(
    'filter_entity_attributes_1', type=str, help="provide filter_entity_attributes (name, label, ...)", default="name", required=True)
parser_top_n_articles_for_label.add_argument(
    'filter_entity_operators_1', type=str, help="provide filter_entity_operators, i.e. =", default ="=", required=True)
parser_top_n_articles_for_label.add_argument(
    'filter_entity_values_1', type=str, help="provide filter_entity_values", default = "Disease:MESH:D000690", required=True)
## article filter
parser_top_n_articles_for_label.add_argument(
    'article_attributes', type=str, help="provide article_attributes (epubdate, label, ...)", default= None, required=False)
parser_top_n_articles_for_label.add_argument(
    'article_operators', type=str, help="provide article_operators, i.e. =, contains, >=", default = None, required=False)
parser_top_n_articles_for_label.add_argument(
    'article_values', type=str, help="provide article_values", default = None, required=False)

parser_top_n_articles_for_label.add_argument(
    'format', type=str, help="format must be in [csv, json]", default="json", required=True)
parser_top_n_articles_for_label.add_argument(
    'order_metric', type=str, help="order metric", required=False)
parser_top_n_articles_for_label.add_argument(
    'options', type=str, help="additional options (html)", required=False)

parser_top_entities = reqparse.RequestParser()
parser_top_entities.add_argument(
    'count', type=int, help="provide count: how many articles should be "\
    "returned? (default = 10)", required=False)
parser_top_entities.add_argument(
    'label', type=str, help="provide concept_label (article, keyword, "\
    "disease, gene, chemical, species, ...", required=True)

parser_cytoscape_query = reqparse.RequestParser()
parser_cytoscape_query.add_argument(
    'query', type=str, help='insert query', required=True)

parser_label_abundance = reqparse.RequestParser()
## goal entity label (required)
parser_label_abundance.add_argument(
    'goal_entity_label', type=str, help="provide goal_entity_label (article, disease, gene, chemical, "\
    "species, ...", default="gene", required=True)
## goal entity filter criteria (adds where clause for goal entity label)    
parser_label_abundance.add_argument(
    'goal_entity_attribute', type=str, help="provide entity attribute (name, label, ...), i.e. taxid", required=False)
parser_label_abundance.add_argument(
    'goal_entity_operator', type=str, help="provide entity operator (=, contains, <, > ...)", required=False)
parser_label_abundance.add_argument(
    'goal_entity_value', type=str, help="provide entity value, i.e. 9606", required=False)
## filter entities 1 (required)
parser_label_abundance.add_argument(
    'filter_entity_labels_1', type=str, help="provide filter_entity_labels (disease, gene, chemical, "\
    "species, ...", default="disease", required=True)
parser_label_abundance.add_argument(
    'filter_entity_attributes_1', type=str, help="provide filter_entity_attributes (name, label, ...)", default="name", required=True)
parser_label_abundance.add_argument(
    'filter_entity_operators_1', type=str, help="provide filter_entity_operators, i.e. =", default ="=", required=True)
parser_label_abundance.add_argument(
    'filter_entity_values_1', type=str, help="provide filter_entity_values", default = "Disease:MESH:D000690", required=True)
## filter entities 2 (optional)
parser_label_abundance.add_argument(
    'filter_entity_labels_2', type=str, help="provide filter_entity_labels (disease, gene, chemical, "\
    "species, ...", default=None, required=False)
parser_label_abundance.add_argument(
    'filter_entity_attributes_2', type=str, help="provide filter_entity_attributes (name, label, ...)", default= None, required=False)
parser_label_abundance.add_argument(
    'filter_entity_operators_2', type=str, help="provide filter_entity_operators, i.e. =", default = None, required=False)
parser_label_abundance.add_argument(
    'filter_entity_values_2', type=str, help="provide filter_entity_values", default = None, required=False)
parser_label_abundance.add_argument(
    'article_attributes', type=str, help="provide article_attributes (epubdate, label, ...)", default= None, required=False)
parser_label_abundance.add_argument(
    'article_operators', type=str, help="provide article_operators, i.e. =, contains, >=", default = None, required=False)
parser_label_abundance.add_argument(
    'article_values', type=str, help="provide article_values", default = None, required=False)

parser_label_abundance.add_argument(
    'goal_entity_min_mentions', type=int, help="provide min mentions for goal entity", default=10, required=True)
parser_label_abundance.add_argument(
    'sort_string', type=str, help="sort by "\
    "(default = score)", default="score DESC", required=True)
parser_label_abundance.add_argument(
    'options', type=str, help="provide additional options (i.e. normalize_by_age for articles)", required=False)

parser_label_abundance_predefined = reqparse.RequestParser()
parser_label_abundance_predefined.add_argument(
    'query', type=str, help='insert query', required=True)

## page not found error
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404


## check status class
@name_space.route("/v1/status")
class Status(Resource):

    @app.doc(responses={ 200: "OK", 401: "AuthError - the neo4j instance "\
        "rejected your user credentials", 404: "Not found - the neo4j "\
        "instance is not available" },)
    def get(self):
        return neo4j_manager.get_status(neo4j_bolt, neo4j_user, 
                                        neo4j_password)


## check statistics class
@name_space.route("/v1/statistics")
class Statistics(Resource):

    @app.doc(responses={ 200: "OK", 401: "AuthError - the neo4j instance "\
        "rejected your user credentials", 404: "Not found - the neo4j "\
        "instance is not available" },)

    def get(self):
        return neo4j_manager.get_statistics()


## basic search class
@name_space.route("/v1/search")
class SearchClass(Resource):

    @app.doc(responses={ 200: "OK", 400: "Invalid arguments - need to pass "\
        "AT LEAST one argument" },)
    @name_space.expect(parser_normal_search)
    def get(self):
        ## get the arguments in the correct format
        args = parser_normal_search.parse_args()
        entity_id = str(args['id']) if args['id']!=None else args['id']
        entity_label = args['entity_label']
        entity_fields = args['entity_fields'].split(",")
        search_operators = args['search_operators'].split(",")
        search_terms = args['search_terms'].split(",")
        sort_by = args['sort_by']
        sort_descending = args['sort_descending']
        result_limit = args['result_limit']
        format = args['format']

        if not (entity_label or search_terms or entity_id):
            name_space.abort(400, "No argument was provided by the request",
                             status = "Could not retrieve result", 
                             statusCode = "400")

        request_result = neo4j_manager.search(
            entity_id = entity_id, entity_label = entity_label, 
            entity_fields = entity_fields, search_operators = search_operators,
            search_terms = search_terms, sort_by = sort_by, 
            sort_descending = sort_descending, result_limit = result_limit,
            format = format)

        if format == "csv":
            response = make_response(request_result, 200)
            response.mimetype = "text/plain"
            return response
        elif format == "json":
            return jsonify(results = request_result)
        else:
            return "error: format not in [csv, json]"

## search neighbors for a given id
@name_space.route("/v1/search_neighbor")
class SearchNeighborClass(Resource):

    @app.doc(
        responses={ 200: "OK", 400: "Invalid arguments - id is missing" })
    @app.expect(parser_neighbor_search)
    def get(self):
        args = parser_neighbor_search.parse_args()
        search_type = args['type']
        search_id = str(args['id']) if args['id']!=None else args['id']
        if not (search_id):
            name_space.abort(
                400, "No ID was provided by the request", 
                status = "Could not retrieve result", statusCode = "400")
        return neo4j_manager.get_neighbors(search_id, search_type)


## redirect relationships from one node to another
# @name_space.route("/v1/redirect_relationships")
class RedirectRelationshipsClass(Resource):

    @app.doc(responses={ 200: 'OK', 400: "Invalid arguments - need to pass "\
             "AT LEAST one argument" },)
    @name_space.expect(parser_redirect_relationships)
    def get(self):
        ## get the arguments in the correct format
        args = parser_redirect_relationships.parse_args()
        from_keys = args['from_keys']
        from_values = args['from_values']
        to_keys = args['to_keys']
        to_values = args['to_values']
        
        if not (from_keys and from_values and to_keys and to_values):
            name_space.abort(400, "Please provide all fields necessary", 
                             status = "Could not retrieve result", 
                             statusCode = "400")
        else: 
            from_keys = from_keys.split(",")
            from_values = from_values.split(",")
            to_keys = to_keys.split(",")
            to_values = to_values.split(",")
        return neo4j_manager.redirect_relationships(from_keys, from_values, 
                                                    to_keys, to_values)

## merge two nodes (first is merged into the second)
# @name_space.route("/v1/merge_nodes")
class MergeNodes(Resource):

    @app.doc(responses={ 200: 'OK', 400: "Invalid arguments - need to pass "\
             "AT LEAST one argument" },)
    @name_space.expect(parser_redirect_relationships)
    def get(self):
        ## get the arguments in the correct format
        args = parser_redirect_relationships.parse_args()
        from_keys = args['from_keys']
        from_values = args['from_values']
        to_keys = args['to_keys']
        to_values = args['to_values']
        
        if not (from_keys and from_values and to_keys and to_values):
            name_space.abort(400, "Please provide all fields necessary", 
                             status = "Could not retrieve result", 
                             statusCode = "400")
        else: 
            from_keys = from_keys.split(",")
            from_values = from_values.split(",")
            to_keys = to_keys.split(",")
            to_values = to_values.split(",")
        return neo4j_manager.merge_nodes(from_keys, from_values, 
                                                    to_keys, to_values)

## delete node by key-value pair
# @name_space.route("/v1/delete_node")
class DeleteNodeClass(Resource):

    @app.doc(responses={ 200: "OK", 400: "Invalid arguments - need to pass "\
             "AT LEAST one argument" },)
    @name_space.expect(parser_delete_node)
    def get(self):
        ## get the arguments in the correct format
        args = parser_delete_node.parse_args()
        del_keys = args['del_keys']
        del_values = args['del_values']
        
        if not (del_keys and del_values):
            name_space.abort(400, "Please provide all fields necessary", 
                             status = "Could not retrieve result", 
                             statusCode = "400")
        else:
            del_keys = del_keys.split(",")
            del_values = del_values.split(",")
        return neo4j_manager.delete_node(del_keys, del_values)


## delete node by id
# @name_space.route("/v1/delete_node_by_id")
class DeleteNodeByIDClass(Resource):

    @app.doc(responses={ 200: 'OK', 400: "Invalid arguments - need to pass "\
             "AT LEAST one argument" },)
    @name_space.expect(parser_delete_node_by_id)
    def get(self):
        ## get the arguments in the correct format
        args = parser_delete_node_by_id.parse_args()
        del_id = args['del_id']
        if not (del_id):
            name_space.abort(400, "Please provde the id for the node which "\
                             "you want to delete", 
                             status = "Could not retrieve result", 
                             statusCode = "400")
        return neo4j_manager.delete_node_by_id(del_id)


## get the top n articles for one label
@name_space.route("/v1/top_n_articles_for_label")
class TopNArticlesForLabelClass(Resource):

    @app.doc(responses={ 200: "OK", 400: "Invalid arguments - need to pass "\
             "all arguments" },)
    @name_space.expect(parser_top_n_articles_for_label)
    def get(self):
        ## get the arguments in the correct format
        args = parser_top_n_articles_for_label.parse_args()
        filter_entity_labels_1 = args['filter_entity_labels_1']
        filter_entity_attributes_1 = args['filter_entity_attributes_1']
        filter_entity_operators_1 = args['filter_entity_operators_1']
        filter_entity_values_1 = args['filter_entity_values_1']
        article_attributes = args['article_attributes']
        article_operators = args['article_operators']
        article_values = args['article_values']
        norm_by_age_str = args['norm_by_age']
        top_n = str(args['count']) if args['count']!=None else args['count']
        format = args['format']
        order_metric = args['order_metric']
        options = args['options']
        request_result = "no result"

        logging.info(f'''
        filter_entity_labels_1={filter_entity_labels_1}
        filter_entity_attributes_1={filter_entity_attributes_1}
        filter_entity_operators_1={filter_entity_operators_1}
        filter_entity_values_1={filter_entity_values_1}
        article_attributes={article_attributes}
        article_operators={article_operators}
        article_values={article_values}
        norm_by_age_str={norm_by_age_str}
        top_n={top_n}
        format={format}
        order_metric={order_metric}
        options={options}
         ''')
        
        list_filter_entity_labels_1 = filter_entity_labels_1.split(",")
        list_filter_entity_attributes_1 = filter_entity_attributes_1.split(",")
        list_filter_entity_operators_1 = filter_entity_operators_1.split(",")
        list_filter_entity_values_1 = filter_entity_values_1.split(",")

        if article_attributes:
            list_article_attributes = article_attributes.split(",")
            list_article_operators = article_operators.split(",")
            list_article_values = article_values.split(",")
        else:
            list_article_attributes = None
            list_article_operators = None
            list_article_values = None

        len_filter_entities_1 = len(list_filter_entity_labels_1)
        if not ( len_filter_entities_1 == len(list_filter_entity_attributes_1)
                 and len_filter_entities_1 == len(list_filter_entity_operators_1)
                 and len_filter_entities_1 == len(list_filter_entity_values_1)
                    ):
            name_space.abort(400, 
                "Filter criteria 1 differ: " \
                    "filter_entity_labels=" 
                    + str(len_filter_entities_1) + \
                    " filter_entity_attributes=" 
                    + str(len(filter_entity_attributes_1.split(","))) + \
                    " filter_entity_operators=" 
                    + str(len(filter_entity_operators_1.split(","))) + \
                    " filter_entity_values=" 
                    + str(len(filter_entity_values_1.split(","))),
                status = "Could not retrieve result", 
                statusCode = "400")
            
        #if not (concept_label and concept_field 
        #        and search_operator and terms):
        #    name_space.abort(400, 
        #                     "Not all arguments were provided by the request",
        #                     status = "Could not retrieve result", 
        #                     statusCode = "400")
        
        
        request_result = neo4j_manager.get_top_n_articles_for_label(
            list_filter_entity_labels_1 = list_filter_entity_labels_1,
            list_filter_entity_attributes_1 = list_filter_entity_attributes_1,
            list_filter_entity_operators_1 = list_filter_entity_operators_1,
            list_filter_entity_values_1 = list_filter_entity_values_1,
            list_article_attributes = list_article_attributes,
            list_article_operators = list_article_operators,
            list_article_values = list_article_values,
            top_n = top_n, 
            metric_norm = norm_by_age_str, format = format,
            order_metric = order_metric, options = options
            )
        
        if format == "csv":
            #logging.info(request_result)
            response = make_response(request_result, 200)
            response.mimetype = "text/plain"
            return response
        elif format == "json":
            return jsonify(results = request_result)
        else:
            return "error: format not in [csv, json]"


## get the top n articles for one label
@name_space.route("/v1/top_entities")
class TopN(Resource):
    @app.doc(responses={ 200: "OK", 400: "Invalid arguments - need to pass "\
             "all arguments" },)
    @name_space.expect(parser_top_entities)
    def get(self):
        ## get the arguments in the correct format
        args = parser_top_entities.parse_args()
        concept_label = args['label']
        top_n = str(args['count']) if args['count']!=None else args['count']
        request_result = "no result"

        if not (concept_label):
            name_space.abort(400, "Not all arguments were provided by the "\
                             "request", status = "Could not retrieve result", 
                             statusCode = "400")
        
        if not top_n:
            request_result = neo4j_manager.get_top_entities(
                concept_label=concept_label)
        else:
            request_result = neo4j_manager.get_top_entities(
                concept_label=concept_label, top_n = top_n)

        return jsonify(results = request_result)


## return cytoscape test object
# @name_space.route("/v1/cytoscape")
class CytoscapeEndpoint(Resource):

    @app.doc(responses={ 200: "OK", 404: "Not found - the neo4j instance is "\
             "not available" },)
    def get(self):
        return neo4j_manager.get_status(neo4j_bolt, neo4j_user, 
                                        neo4j_password)

## return cytoscape query (accepts any query...)
@name_space.route("/v1/cytoscape/predefined")
class CytoscapeQuery(Resource):

    @app.doc(responses={ 200: "OK", 404: "Not found - the neo4j instance is "\
             "not available" },)
    @name_space.expect(parser_cytoscape_query)
    def get(self):
        args = parser_cytoscape_query.parse_args()
        query = args['query']
        return neo4j_manager.get_cytoscape_query(query)


## get the label abundance for the graph
@name_space.route("/v1/label_abundance")
class LabelAbundanceClass(Resource):

    @app.doc(responses={ 200: "OK", 400: "Invalid arguments - need to pass "\
             "all arguments" },)
    @name_space.expect(parser_label_abundance)
    def get(self):
        ## get the arguments in the correct format
        args = parser_label_abundance.parse_args()

        goal_entity_label = args['goal_entity_label']
        goal_entity_attribute = args['goal_entity_attribute']
        goal_entity_operator = args['goal_entity_operator']
        goal_entity_value = args['goal_entity_value']
        filter_entity_labels_1 = args['filter_entity_labels_1']
        filter_entity_attributes_1 = args['filter_entity_attributes_1']
        filter_entity_operators_1 = args['filter_entity_operators_1']
        filter_entity_values_1 = args['filter_entity_values_1']
        filter_entity_labels_2 = args['filter_entity_labels_2']
        filter_entity_attributes_2 = args['filter_entity_attributes_2']
        filter_entity_operators_2 = args['filter_entity_operators_2']
        filter_entity_values_2 = args['filter_entity_values_2']
        article_attributes = args['article_attributes']
        article_operators = args['article_operators']
        article_values = args['article_values']
        goal_entity_min_mentions = args['goal_entity_min_mentions']
        sort_string = args['sort_string']
        options = args['options']
        logging.info(f'''
        goal_entity_label={goal_entity_label}
        goal_entity_attribute={goal_entity_attribute}
        goal_entity_operator={goal_entity_operator}
        goal_entity_value={goal_entity_value}
        filter_entity_labels_1={filter_entity_labels_1}
        filter_entity_attributes_1={filter_entity_attributes_1}
        filter_entity_operators_1={filter_entity_operators_1}
        filter_entity_values_1={filter_entity_values_1}
        filter_entity_labels_2={filter_entity_labels_2}
        filter_entity_attributes_2={filter_entity_attributes_2}
        filter_entity_operators_2={filter_entity_operators_2}
        filter_entity_values_2={filter_entity_values_2}
        article_attributes={article_attributes}
        article_operators={article_operators}
        article_values={article_values}
        sort_string={sort_string}
        options={options}
         ''')

        request_result = "no result"

        if not (goal_entity_label and filter_entity_labels_1 
                and filter_entity_attributes_1 and filter_entity_operators_1
                and filter_entity_values_1):
            name_space.abort(400, 
                             "Not all arguments were provided by the request",
                             status = "Could not retrieve result", 
                             statusCode = "400")

        list_filter_entity_labels_1 = filter_entity_labels_1.split(",")
        list_filter_entity_attributes_1 = filter_entity_attributes_1.split(",")
        list_filter_entity_operators_1 = filter_entity_operators_1.split(",")
        list_filter_entity_values_1 = filter_entity_values_1.split(",")
        if filter_entity_labels_2:
            list_filter_entity_labels_2 = filter_entity_labels_2.split(",")
            list_filter_entity_attributes_2 = filter_entity_attributes_2.split(",")
            list_filter_entity_operators_2 = filter_entity_operators_2.split(",")
            list_filter_entity_values_2 = filter_entity_values_2.split(",")
        else:
            list_filter_entity_labels_2 = None
            list_filter_entity_attributes_2 = None
            list_filter_entity_operators_2 = None
            list_filter_entity_values_2 = None

        if article_attributes:
            list_article_attributes = article_attributes.split(",")
            list_article_operators = article_operators.split(",")
            list_article_values = article_values.split(",")
        else:
            list_article_attributes = None
            list_article_operators = None
            list_article_values = None

        len_filter_entities_1 = len(list_filter_entity_labels_1)
        if not ( len_filter_entities_1 == len(list_filter_entity_attributes_1)
                 and len_filter_entities_1 == len(list_filter_entity_operators_1)
                 and len_filter_entities_1 == len(list_filter_entity_values_1)
                    ):
            name_space.abort(400, 
                "Filter criteria 1 differ: " \
                    "filter_entity_labels=" 
                    + str(len_filter_entities_1) + \
                    " filter_entity_attributes=" 
                    + str(len(filter_entity_attributes_1.split(","))) + \
                    " filter_entity_operators=" 
                    + str(len(filter_entity_operators_1.split(","))) + \
                    " filter_entity_values=" 
                    + str(len(filter_entity_values_1.split(","))),
                status = "Could not retrieve result", 
                statusCode = "400")
        
        if filter_entity_labels_2:
            len_filter_entities_2 = len(list_filter_entity_labels_2)
            if not ( len_filter_entities_2 == len(list_filter_entity_attributes_2)
                    and len_filter_entities_2 == len(list_filter_entity_operators_2)
                    and len_filter_entities_2 == len(list_filter_entity_values_2)
                        ):
                name_space.abort(400, 
                    "Filter criteria 2 differ: " \
                        "filter_entity_labels=" 
                        + str(len_filter_entities_2) + \
                        " filter_entity_attributes=" 
                        + str(len(filter_entity_attributes_2.split(","))) + \
                        " filter_entity_operators=" 
                        + str(len(filter_entity_operators_2.split(","))) + \
                        " filter_entity_values=" 
                        + str(len(filter_entity_values_2.split(","))),
                    status = "Could not retrieve result", 
                    statusCode = "400")
        
        if article_attributes:
            len_article_attributes = len(list_article_attributes)
            if not ( len_article_attributes == len(list_article_operators)
                    and len_article_attributes == len(list_article_values)
                        ):
                name_space.abort(400, 
                    "Filter criteria 2 differ: " \
                        "article_attributes=" 
                        + str(len_article_attributes) + \
                        " article_operators=" 
                        + str(len(article_operators.split(","))) + \
                        " article_values=" 
                        + str(len(article_values.split(","))),
                    status = "Could not retrieve result", 
                    statusCode = "400")

        request_result = neo4j_manager.get_label_abundance(
            goal_entity_label = goal_entity_label,
            goal_entity_attribute = goal_entity_attribute,
            goal_entity_operator = goal_entity_operator,
            goal_entity_value = goal_entity_value,
            list_filter_entity_labels_1 = list_filter_entity_labels_1,
            list_filter_entity_attributes_1 = list_filter_entity_attributes_1,
            list_filter_entity_operators_1 = list_filter_entity_operators_1,
            list_filter_entity_values_1 = list_filter_entity_values_1,
            list_filter_entity_labels_2 = list_filter_entity_labels_2,
            list_filter_entity_attributes_2 = list_filter_entity_attributes_2,
            list_filter_entity_operators_2 = list_filter_entity_operators_2,
            list_filter_entity_values_2 = list_filter_entity_values_2,
            list_article_attributes = list_article_attributes,
            list_article_operators = list_article_operators,
            list_article_values = list_article_values,
            goal_entity_min_mentions = goal_entity_min_mentions,
            sort_string = sort_string,
            options = options,
        )

        response = make_response(request_result, 200)
        response.mimetype = "text/plain"
        return response


## return cytoscape query (accepts any query...)
@name_space.route("/v1/label_abundance/predefined")
class LabelAbundancePredefined(Resource):

    @app.doc(responses={ 200: "OK", 404: "Not found - the neo4j instance is "\
             "not available" },)
    @name_space.expect(parser_label_abundance_predefined)
    def get(self):
        args = parser_label_abundance_predefined.parse_args()
        query = args['query']
        request_result = neo4j_manager.get_predefined_label_abundance(query)
        if request_result != None:
            response = make_response(request_result, 200)
            response.mimetype = "text/plain"
        else:
            response = [{"message: predefined query does not exist: "+ query}]
        return response