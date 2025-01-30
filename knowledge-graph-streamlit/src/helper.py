import streamlit as st
from streamlit.components.v1 import html
from streamlit_plotly_events import plotly_events
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import json
import requests
import os
import sys
import configparser
import math
import logging
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, DataReturnMode, JsCode


from helper.neo4j_helper import Neo4j_Manager

#import plotly.express as px
import networkx as nx
if sys.version_info[0] < 3: 
    from StringIO import StringIO
else:
    from io import StringIO

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
logging.info("streamlit: initialized the logger")

## global variables for streamlit
sample_size = 30#st.sidebar.number_input("rows", min_value=10, value=30)
grid_height = 400#st.sidebar.number_input("Grid height", min_value=200, max_value=800, value=400)
return_mode_value = "FILTERED"#DataReturnMode.__members__[return_mode]
update_mode_value = "GRID_CHANGED"#GridUpdateMode.__members__[update_mode]
enable_enterprise_modules = False#st.sidebar.checkbox("Enable Enterprise Modules")
fit_columns_on_grid_load = False #st.sidebar.checkbox("Fit Grid Columns on Load")
enable_selection= True # st.sidebar.checkbox("Enable row selection", value=True)
selection_mode = "multiple" #st.sidebar.radio("Selection Mode", ['single','multiple'], index=1)
use_checkbox = True #st.sidebar.checkbox("Use check box for selection", value=True)
groupSelectsChildren = True #st.sidebar.checkbox("Group checkbox select children", value=True)
groupSelectsFiltered = True #st.sidebar.checkbox("Group checkbox includes filtered", value=True)
enable_pagination = False # st.sidebar.checkbox("Enable pagination", value=False)


def config_streamlit(title: str = None):
    st.set_page_config(
    page_title=title,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': 'Created by Sven Heins, visit our institute https://www.ims.bio',
        }
    )   
    #html('''
    #    <script src='https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.0.2/tablesort.min.js'></script>
    #    <script>
    #        var table = window.parent.document.getElementById("myTable");
    #        console.log("ye")
    #        console.log(table.id);
    #    </script>
    #    <script>new Tablesort(window.parent.document.getElementById("myTable"));</script>
    #    ''')

def initialize_neo4j():
    config_path = './config.ini'
    config = configparser.ConfigParser()
    config.read(config_path)
    st.session_state["use_cert"] = config['FRONTEND-settings']['use_cert'].lower() == 'true'

    config_path = "/input/config.ini"
    ## general config
    #config = configparser.ConfigParser()
    #config.read(config_path)
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
    #logging.info("waiting "+ str(waittime)+" seconds before trying to connect to graph"\
    #    " on "+db_hostname)
    #time.sleep(waittime)
    st.session_state["neo4j_manager"] =  Neo4j_Manager(neo4j_bolt, neo4j_user, neo4j_password, logging = logging)

def initialize_requests():
    session = requests.Session()
    session.trust_env = False
    st.session_state["requests_session"] = session

## i.e. html_string = "https://google.com|google"
def make_clickable(html_string: str = ""):
    return_html_code = "wrong format: " + html_string
    if len(html_string.split("|")) == 2:
        html_link = html_string.split("|")[0]
        html_text = html_string.split("|")[1]
        return_html_code = f'<a target="_blank" href="{html_link}">{html_text}</a>'
    return return_html_code

## i.e. html_string = "https://google.com|google"
def get_entity_string(original_string: str = "", entity_type: str = "") -> str:
    return_string = "|"
    if entity_type == "disease":
        if len(original_string.split(":")) == 3:
            mesh_string = original_string.split(":")[1] + ":" + original_string.split(":")[2]
            return_string = "http://ctdbase.org/detail.go?type=disease&acc="+mesh_string+"|"+mesh_string
    elif entity_type == "gene":
        float_string = float(original_string)
        if not math.isnan(float_string):
            original_string = str(int(float_string))
            return_string = "https://www.ncbi.nlm.nih.gov/gene/"+original_string+"|"+original_string
    elif entity_type == "chemical":
        if len(original_string.split(":")) == 3:
            mesh_chemical = original_string.split(":")[2]
            return_string = "https://meshb.nlm.nih.gov/record/ui?ui="+mesh_chemical+"|"+mesh_chemical
    elif entity_type == "species":
        if len(original_string.split(":")) == 2:
            taxonomy_species = original_string.split(":")[1]
            return_string = "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=" + taxonomy_species + "&lvl=0"+"|"+taxonomy_species
    elif entity_type == "article":
        pubmed_id = original_string
        return_string = "https://pubmed.ncbi.nlm.nih.gov/" + pubmed_id +"|"+pubmed_id
    elif entity_type == "article_pmc":
        if original_string != "nan":
            pmc_id = original_string
            return_string = "https://www.ncbi.nlm.nih.gov/pmc/articles/" + pmc_id + "/"+"|"+pmc_id
        else:
            return_string = "https://www.ncbi.nlm.nih.gov/pmc|"
    elif entity_type == "article_pubtator":
        pubmed_id = original_string.replace("https://pubmed.ncbi.nlm.nih.gov/", "")
        return_string = "https://www.ncbi.nlm.nih.gov/research/pubtator/?view=publication&pmid=" + pubmed_id + "|"+pubmed_id
    return return_string


@st.cache_data
def get_neo4j_nodes_edges(count_literature = 10, selected_ids= []):
    if ("neo4j_manager" in st.session_state):
        neo4j_manager = st.session_state["neo4j_manager"]
    else:
        initialize_neo4j()
        neo4j_manager = st.session_state["neo4j_manager"]

    query = '''CALL {
    MATCH (e)--(subset_articles_1:Article)
    WHERE id(e) in ''' + str (selected_ids) + \
    '''
    RETURN count(subset_articles_1) AS count_subset_articles_1,
        collect(subset_articles_1) AS subset_list_1,
        COLLECT(e) AS entities
    }
    WITH entities, count_subset_articles_1, subset_list_1

    CALL {
        
    WITH count_subset_articles_1, subset_list_1, entities

    CALL {
    WITH count_subset_articles_1, subset_list_1, entities
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
    RETURN article ORDER BY count_metric_age_norm DESC LIMIT ''' + str(count_literature * len(selected_ids)) + \
    '''}   

    WITH entities, COLLECT(article) as literature
    CALL {
    WITH entities, literature
    MATCH (e1)--(a1:Article)
    WHERE e1 IN entities AND a1 in literature
    WITH DISTINCT e1, a1
    CALL apoc.create.vRelationship(a1,'LITERATURE_ENTITY', {from:a1.name, to:e1.name}, e1) YIELD rel as rel_lit_ent
    RETURN COLLECT(rel_lit_ent) as rels_lit_ent
    }

    WITH entities, literature, 
    rels_lit_ent
    CALL {
    WITH literature
    MATCH (l1:Article)-->(l2:Article)
    WHERE l1 IN literature and l2 IN literature
    WITH DISTINCT l1, l2
    CALL apoc.create.vRelationship(l1,'CITES', {from:l1.name, to:l2.name}, l2) YIELD rel as rel_lit
    RETURN COLLECT (rel_lit) as rels_lit
    }       

    WITH entities
    + literature
    AS list_nodes, 
    rels_lit_ent + rels_lit
    AS list_relations    
    RETURN {nodes:list_nodes, edges:list_relations}
    '''


    #query = "CALL {        MATCH (subset_articles_1:Article)-->(g:disease)        WHERE g.name = 'Disease:MESH:D015209'          WITH count(subset_articles_1) AS count_subset_articles_1,             collect(subset_articles_1) AS subset_list_1        CALL {            WITH count_subset_articles_1, subset_list_1            MATCH (mentions_all:Article)-->(mentions_subset_1_target:Article)            WHERE mentions_subset_1_target IN subset_list_1 WITH count_subset_articles_1, mentions_subset_1_target,                count(mentions_all) AS count_all            RETURN mentions_subset_1_target, count_all        }            WITH count_subset_articles_1, subset_list_1, mentions_subset_1_target, count_all         CALL {             WITH count_subset_articles_1, subset_list_1, mentions_subset_1_target, count_all            MATCH (mentions_subset_1:Article)-->(mentions_subset_1_target)            WHERE mentions_subset_1 IN subset_list_1             WITH count(mentions_subset_1) AS count_target            RETURN count_target        }        UNWIND [mentions_subset_1_target.age_in_months, 1] AS age_to_one         WITH mentions_subset_1_target as article, count_all, count_target, max(age_to_one) AS age_norm,            (count_all + 100 * count_target) as count_metric,            (toFloat(count_all + 100 * count_target) / max(age_to_one)) as count_metric_age_norm        RETURN article, count_metric_age_norm ORDER BY count_metric_age_norm DESC LIMIT 10    }    WITH COLLECT(article) as literature    CALL {        WITH literature        MATCH (a)--(g:gene)        WHERE a in literature        CALL apoc.create.vRelationship(a, 'HAS_GENE', {from:a.name, to:g.name}, g) YIELD rel AS rel1        WITH COLLECT (g) as genes, COLLECT(rel1) as rels1        CALL {            WITH genes            MATCH (g1)--(p:pathway_kegg)            WHERE g1 in genes            CALL apoc.create.vRelationship(p, 'KEGG_HAS_GENE', {from:p.name, to:g1.name}, g1) YIELD rel AS rel_p_g            RETURN COLLECT(p) as kegg_pathways, COLLECT(rel_p_g) as rels_p_g        }        RETURN genes, rels1, kegg_pathways, rels_p_g    }    CALL {        WITH literature        MATCH (b)--(d:disease)        WHERE b in literature        CALL apoc.create.vRelationship(b, 'HAS_DISEASE', {from:b.name, to:d.name}, d) YIELD rel AS rel2        RETURN COLLECT(d) as diseases, COLLECT(rel2) as rels2    }    CALL {        WITH literature        MATCH (b)--(c:chemical)        WHERE b in literature        CALL apoc.create.vRelationship(b, 'HAS_CHEMICAL', {from:b.name, to:c.name}, c) YIELD rel AS rel3        RETURN COLLECT(c) as chemicals, COLLECT(rel3) as rels3    }    CALL {        WITH literature        MATCH (b)--(s:species)        WHERE b in literature        CALL apoc.create.vRelationship(b, 'HAS_SPECIES', {from:b.name, to:s.name}, s) YIELD rel AS rel4        RETURN COLLECT(s) as species, COLLECT(rel4) as rels4    }    WITH diseases + genes + chemicals + species + literature + kegg_pathways AS list_nodes, rels1 + rels2 + rels3 + rels4 + rels_p_g as list_relations    RETURN {nodes:list_nodes, edges:list_relations}"
    result = neo4j_manager.neo4j_response_to_json(query_string = query, 
                                                    run_node_embedding=False)#, base_path = query_input_path)
    json_graph = result #json.loads(result)
    nodes = { item['data']['id']: item \
            for item in json_graph if item['group'] == "nodes"}
    edges = { item['data']['id']: item \
            for item in json_graph if item['group'] == "edges"}
    return nodes, edges
    


@st.cache_data
def run_query(data_url, json= False, use_cert = False):
    if "requests_session" in st.session_state:
        session = st.session_state["requests_session"]
    else:
        return None
    
    if "use_cert" in st.session_state:
        use_cert = st.session_state["use_cert"]
    
    if (use_cert):
        response = session.get(data_url, verify='./cert/cert.pem')
    else:
        response = session.get(data_url)
    if json == False: response = pd.read_csv(StringIO(response.text), sep=";")
    else: response = response.json()
    return response

@st.cache_data
def get_graph_data(data_url, use_cert = False):
    if "requests_session" in st.session_state:
        session = st.session_state["requests_session"]
    else:
        return None
    
    if "use_cert" in st.session_state:
        use_cert = st.session_state["use_cert"]

    if (use_cert):
        response = session.get(data_url, verify='./cert/cert.pem')
    else:
        response = session.get(data_url)
    json_response = response.text
    return json_response

def cellsytle_jscode(search_term):
    return JsCode("""
        function(params) {
            if (params.value != null) {
                if (params.value.toLowerCase().includes('"""
                    + search_term + """')) {
                    return {
                        'color': 'black',
                        'backgroundColor': '#8cdf8e'
                    }
                }
                else {
                    return {
                        'color': 'black',
                        'backgroundColor': 'white'
                    }
                }
            }
            else {
                return {
                    'color': 'black',
                    'backgroundColor': 'white'
                }
            }
        };
        """)

def configure_cellstyle(grid_builder, column_names, search_term):
    for column in column_names:
        grid_builder.configure_column(column, cellStyle=cellsytle_jscode(search_term))

@st.cache_data
def create_nodes_edges(graph_url):
    json_graph = json.loads(get_graph_data(graph_url))
    nodes = { item['data']['id']: item \
            for item in json_graph if item['group'] == "nodes"}
    edges = { item['data']['id']: item \
            for item in json_graph if item['group'] == "edges"}
    return nodes , edges

def compile_sidebar(selection_enrichment_list: list = []):
    selection = []
    if "selection_enrichment" in st.session_state:
        selection = st.session_state["selection_enrichment"]
    if len(selection) > 0:
        ## enrichement ids
        selection_ids = [id["ID(a)"] for category in selection.keys() for id in selection[category] ]

        selection_post = st.sidebar.multiselect(
                    "Select IDs for ENRICHMENT analysis", options=selection_ids, default=selection_ids
            )
        st.session_state["selection_ids_enrichment"] = selection_post
        selection_final = {}
        for entity_class in selection:
            selection_final[entity_class] = []
            for entry in selection[entity_class]:
                if entry["ID(a)"] in selection_post:
                    selection_final[entity_class].append(entry)
        st.session_state["selection_enrichment"] = selection_final
        
        ## visualization ids
        selection_pre = []
        if "selection_ids_visual" in st.session_state:
            selection_pre = st.session_state["selection_ids_visual"]
        selection_enrichment_ids = list(set([entry['db_id'] for entry in selection_enrichment_list] + selection_pre))
        selection_post = st.sidebar.multiselect(
                    "Select additional IDs for VISUALIZATION", options=selection_enrichment_ids, default=selection_enrichment_ids
            )
        st.session_state["selection_ids_visual"] = selection_post

## i.e.: url_api https://kg-als-api.int.ims.bio/api/v1/
def search_and_select(url_api: str = None,
                     title: str = "Knowledge graph",
                     ) \
        -> list:
    if (not url_api):
        return None
    
    ## global setup
    st.markdown("<h1 style='text-align: center;'>"+title+"</h1>", unsafe_allow_html=True)

    ## start the page
    temp_col1, inter_cols_pace, temp_col2 = st.columns((3, 6, 3))
    with inter_cols_pace.expander("Search", expanded = True):
        if not "search_term" in st.session_state:
            st.session_state["search_term"] = ""
        search_term = st.text_input(label = "Enter search term:", value = st.session_state["search_term"])
        st.session_state["search_term"] = search_term
        if len(search_term) > 0:
            if "submitted" not in st.session_state:
                st.session_state.submitted = True

    selection_response = {}
    if "submitted" in st.session_state and len(search_term) > 0:
        st.markdown("**Search results**")
        
        #col = [0,0,0]
        #col[0], col[1], col[2] = st.columns(3)
        #column_index = 0
        no_results = True

        search_url = f"{url_api}search?entity_label=disease&entity_fields=label%2Cname%2Cdisease_name%2Cdisease_synonyms%2Cdisease_id%2Cdisease_definition&search_operators=CONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS&search_terms={search_term}%2C{search_term}%2C{search_term}%2C{search_term}%2C{search_term}%2C{search_term}&sort_by=count_links&sort_descending=true&result_limit=1000&format=json"
        json_disease_search_result = run_query(search_url, json=True)

        
        if not ("message" in json_disease_search_result["results"][0]):
            df_disease_search_result = pd.DataFrame.from_dict(json_disease_search_result["results"])
            df_disease_search_result = pd.concat([df_disease_search_result.drop(['a'], axis = 1), df_disease_search_result['a'].apply(pd.Series)], axis = 1)
            cols_reordered_available = df_disease_search_result.columns.tolist()
            cols_reordered_selection = ["count_links", "disease_name", "label", "disease_id", "disease_definition", "disease_synonyms", "disease_altids", "name", "ID(a)"]
            cols_reordered = [col for col in cols_reordered_selection if col in cols_reordered_available]
            df_disease_search_result = df_disease_search_result[cols_reordered]
            df_disease_search_result = df_disease_search_result.rename(columns={"count_links": "mentions"})
            
            ## settings for the grid
            gb = GridOptionsBuilder.from_dataframe(df_disease_search_result)
            gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc='sum', editable=True)
            configure_cellstyle(grid_builder = gb, column_names=["label", "name", "disease_name", "disease_id", "disease_synonyms", "disease_definition"], search_term = search_term)#df_disease_search_result.columns)
            gb.configure_selection(selection_mode)
            gb.configure_selection(selection_mode, use_checkbox=True, groupSelectsChildren=groupSelectsChildren, groupSelectsFiltered=groupSelectsFiltered)
            gb.configure_grid_options(domLayout='normal')
            gb.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=10)
            gridOptions = gb.build()

            table_height = int(np.min([(df_disease_search_result.shape[0] + 2.5) * 28, grid_height])) + 100
            with st.expander("Diseases", expanded = True):
                ## print the grid and collect items
                selection_response["disease"] = AgGrid(
                    df_disease_search_result, 
                    gridOptions=gridOptions,
                    #height=table_height, 
                    width='100%',
                    data_return_mode=return_mode_value, 
                    update_mode=update_mode_value,
                    fit_columns_on_grid_load=fit_columns_on_grid_load,
                    allow_unsafe_jscode=True, #Set it to True to allow jsfunction to be injected
                    enable_enterprise_modules=enable_enterprise_modules
                    )['selected_rows']
                
                #column_index = (column_index + 1 ) % len(col)
                no_results = False
        else:
            pass
        
        ## chemicals
        search_url = f"{url_api}search?entity_label=chemical&entity_fields=label%2Cname%2Cmesh_name%2Centry_terms%2Cpharmacological_actions%2Cprevious_indexing%2Cscope_note&search_operators=CONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS&search_terms={search_term}%2C{search_term}%2C{search_term}%2C{search_term}%2C{search_term}%2C{search_term}%2C{search_term}&sort_by=count_links&sort_descending=true&result_limit=1000&format=json"
        json_chemical_search_result = run_query(search_url, json=True)
        #st.write(gene_search_result["results"])
        if not ("message" in json_chemical_search_result["results"][0]):
            df_chemical_search_result = pd.DataFrame.from_dict(json_chemical_search_result["results"])
            df_chemical_search_result = pd.concat([df_chemical_search_result.drop(['a'], axis = 1), df_chemical_search_result['a'].apply(pd.Series)], axis = 1)
            cols_reordered_available = df_chemical_search_result.columns.tolist()
            cols_reordered_selection = ["count_links", "mesh_name", "label", "name", "scope_note", "entry_terms", "pharmacological_actions", "previous_indexing", "note", "source", "ID(a)"]
            cols_reordered = [col for col in cols_reordered_selection if col in cols_reordered_available]
            df_chemical_search_result = df_chemical_search_result[cols_reordered]
            df_chemical_search_result = df_chemical_search_result.rename(columns={"count_links": "mentions"})

            ## settings for the grid
            gb = GridOptionsBuilder.from_dataframe(df_chemical_search_result)
            gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc='sum', editable=True)
            configure_cellstyle(grid_builder = gb, column_names=["label", "name", "mesh_name", "entry_terms", "pharmacological_actions", "previous_indexing", "scope_note"], search_term = search_term)
            gb.configure_selection(selection_mode)
            gb.configure_selection(selection_mode, use_checkbox=True, groupSelectsChildren=groupSelectsChildren, groupSelectsFiltered=groupSelectsFiltered)
            gb.configure_grid_options(domLayout='normal')
            gb.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=10)
            gridOptions = gb.build()

            table_height = int(np.min([(df_chemical_search_result.shape[0] + 2.5) * 28, grid_height]))
            with st.expander("Chemicals", expanded = True):
                ## print the grid and collect items
                selection_response["chemical"] = AgGrid(
                    df_chemical_search_result, 
                    gridOptions=gridOptions,
                    #height=table_height, 
                    width='100%',
                    data_return_mode=return_mode_value, 
                    update_mode=update_mode_value,
                    fit_columns_on_grid_load=fit_columns_on_grid_load,
                    allow_unsafe_jscode=True, #Set it to True to allow jsfunction to be injected
                    enable_enterprise_modules=enable_enterprise_modules
                    )['selected_rows']
                
                #column_index = (column_index + 1 ) % len(col)
                no_results = False
        else:
            pass
        
        ## species
        search_url = f"{url_api}search?entity_label=species&entity_fields=label%2Cname%2Ccurrent_name%2Ccommon_name%2Cblast_name&search_operators=CONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS&search_terms={search_term}%2C{search_term}%2C{search_term}%2C{search_term}%2C{search_term}&sort_by=count_links&sort_descending=true&result_limit=1000&format=json"
        json_species_search_result = run_query(search_url, json=True)

        if not ("message" in json_species_search_result["results"][0]):
            df_species_search_result = pd.DataFrame.from_dict(json_species_search_result["results"])
            df_species_search_result = pd.concat([df_species_search_result.drop(['a'], axis = 1), df_species_search_result['a'].apply(pd.Series)], axis = 1)
            cols_reordered_available = df_species_search_result.columns.tolist()
            cols_reordered_selection = ["count_links", "current_name", "label", "common_name", "blast_name", "name", "ID(a)"]
            cols_reordered = [col for col in cols_reordered_selection if col in cols_reordered_available]
            df_species_search_result = df_species_search_result[cols_reordered]
            df_species_search_result = df_species_search_result.rename(columns={"count_links": "mentions"})

            ## settings for the grid
            gb = GridOptionsBuilder.from_dataframe(df_species_search_result)
            gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc='sum', editable=True)
            configure_cellstyle(grid_builder = gb, column_names=["label", "name", "current_name", "common_name", "blast_name"], search_term = search_term)
            gb.configure_selection(selection_mode)
            gb.configure_selection(selection_mode, use_checkbox=True, groupSelectsChildren=groupSelectsChildren, groupSelectsFiltered=groupSelectsFiltered)
            gb.configure_grid_options(domLayout='normal')
            gb.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=10)
            gridOptions = gb.build()

            table_height = int(np.min([(df_species_search_result.shape[0] + 2.5) * 28, grid_height]))
            with st.expander("Species", expanded = True):
                ## print the grid and collect items
                selection_response["species"] = AgGrid(
                    df_species_search_result, 
                    gridOptions=gridOptions,
                    #height=table_height, 
                    width='100%',
                    data_return_mode=return_mode_value, 
                    update_mode=update_mode_value,
                    fit_columns_on_grid_load=fit_columns_on_grid_load,
                    allow_unsafe_jscode=True, #Set it to True to allow jsfunction to be injected
                    enable_enterprise_modules=enable_enterprise_modules
                    )['selected_rows']
                
                #column_index = (column_index + 1 ) % len(col)
                no_results = False
        else:
            pass

        ## genes
        search_url = f"{url_api}search?entity_label=gene&entity_fields=label%2Cname%2Calias%2Censembl_ids%2Centrrezgene%2Csymbol%2Crefseq_rna&search_operators=CONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS%2CCONTAINS&search_terms={search_term}%2C{search_term}%2C{search_term}%2C{search_term}%2C{search_term}%2C{search_term}%2C{search_term}&sort_by=count_links&sort_descending=true&result_limit=1000&format=json"
        json_gene_search_result = run_query(search_url, json=True)

        if not ("message" in json_gene_search_result["results"][0]):
            df_genes_search_result = pd.DataFrame.from_dict(json_gene_search_result["results"])
            df_genes_search_result = pd.concat([df_genes_search_result.drop(['a'], axis = 1), df_genes_search_result['a'].apply(pd.Series)], axis = 1)
            cols_reordered_available = df_genes_search_result.columns.tolist()
            cols_reordered_selection = ["count_links", "symbol", "entrezgene", "alias", "taxid", "label", "summary", "name", "ensembl_ids", "type_of_gene", "refseq_rna", "ID(a)"]
            cols_reordered = [col for col in cols_reordered_selection if col in cols_reordered_available]
            df_genes_search_result = df_genes_search_result[cols_reordered]
            df_genes_search_result = df_genes_search_result.rename(columns={"count_links": "mentions"})

            ## settings for the grid
            gb = GridOptionsBuilder.from_dataframe(df_genes_search_result)
            gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc='sum', editable=True)
            configure_cellstyle(grid_builder = gb, column_names=["alias", "ensembl_ids", "entrezgene", "label", "name", "refseq_rna", "summary", "symbol", "taxid", "type_of_gene"], search_term = search_term)
            gb.configure_selection(selection_mode)
            gb.configure_selection(selection_mode, use_checkbox=True, groupSelectsChildren=groupSelectsChildren, groupSelectsFiltered=groupSelectsFiltered)
            gb.configure_grid_options(domLayout='normal')
            gb.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=10)
            gridOptions = gb.build()

            table_height = int(np.min([(df_genes_search_result.shape[0] + 2.5) * 28, grid_height]))
            with st.expander("Genes", expanded = True):
                ## print the grid and collect items
                selection_response["gene"] = AgGrid(
                    df_genes_search_result, 
                    gridOptions=gridOptions,
                    #height=table_height, 
                    width='100%',
                    data_return_mode=return_mode_value, 
                    update_mode=update_mode_value,
                    fit_columns_on_grid_load=fit_columns_on_grid_load,
                    allow_unsafe_jscode=True, #Set it to True to allow jsfunction to be injected
                    enable_enterprise_modules=enable_enterprise_modules
                    )['selected_rows']
                
                #column_index = (column_index + 1 ) % len(col)
                no_results = False
        else:
            pass
        
        if no_results:
            st.markdown("**no results found**")
    return selection_response    


## render the enrichment table
def render_table(df_filtered, goal_entity_label ):
    column_select = "empty"
    additional_column = "empty"
    if (goal_entity_label == "disease"):
        column_select = "mesh_disease"
    elif (goal_entity_label == "gene"):
        column_select = "entrez_gene"
    elif (goal_entity_label == "chemical"):
        column_select = "mesh_chemical"
    elif (goal_entity_label == "species"):
        column_select = "name"
    elif (goal_entity_label == "article"):
        column_select = "pubmed_id"
        pubtator = "pubtator"
        additional_column = "pmc_id"

    
    if column_select in df_filtered.columns:    
        df_filtered[column_select] = df_filtered[column_select].astype(str)
        df_filtered[column_select] = df_filtered[column_select].apply(get_entity_string, args = [goal_entity_label])
        ## add the additional pmc_id link
        if (goal_entity_label == "article"):
            df_filtered[pubtator] = df_filtered[column_select].astype(str)
            df_filtered[pubtator] = df_filtered[column_select].apply(get_entity_string, args = [goal_entity_label+"_pubtator"])
            df_filtered[additional_column] = df_filtered[additional_column].astype(str)
            df_filtered[additional_column] = df_filtered[additional_column].apply(get_entity_string, args = [goal_entity_label+"_pmc"])
            df_filtered = df_filtered[["score", "pubmed_id", "pubtator", "pmc_id", "title", "epubdate", "journal", "total_citations", "citations_from_target"]]

    ## settings for the grid
    gb = GridOptionsBuilder.from_dataframe(df_filtered)
    gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc='sum', editable=True)
    #configure_cellstyle(grid_builder = gb, column_names=["label", "name"], search_term = search_term)#df_disease_search_result.columns)
    gb.configure_selection(selection_mode)
    gb.configure_selection(selection_mode, use_checkbox=True, groupSelectsChildren=groupSelectsChildren, groupSelectsFiltered=groupSelectsFiltered)
    gb.configure_grid_options(domLayout='normal')
    gb.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=10)

    gb.configure_column(
        column_select, column_select,
        cellRenderer=JsCode("""
            class UrlCellRenderer {
            init(params) {
                if (params.value != null) {
                    this.eGui = document.createElement('a');
                    this.eGui.innerText = params.value.split("|")[1];
                    this.eGui.setAttribute('href', params.value.split("|")[0]);
                    this.eGui.setAttribute('style', "text-decoration:none");
                    this.eGui.setAttribute('target', "_blank");
                }
            }
            getGui() {
                return this.eGui;
            }
            }
        """)
    )
    ## add the additional pmc_id link
    if (goal_entity_label == "article"):
        gb.configure_column(
            additional_column, additional_column,
            cellRenderer=JsCode("""
                class UrlCellRenderer {
                init(params) {
                    if (params.value != null) {
                        this.eGui = document.createElement('a');
                        this.eGui.innerText = params.value.split("|")[1];
                        this.eGui.setAttribute('href', params.value.split("|")[0]);
                        this.eGui.setAttribute('style', "text-decoration:none");
                        this.eGui.setAttribute('target', "_blank");
                    }
                }
                getGui() {
                    return this.eGui;
                }
                }
            """)
        )
        gb.configure_column(
            pubtator, pubtator,
            cellRenderer=JsCode("""
                class UrlCellRenderer {
                init(params) {
                    if (params.value != null) {
                        this.eGui = document.createElement('a');
                        this.eGui.innerText = params.value.split("|")[1];
                        this.eGui.setAttribute('href', params.value.split("|")[0]);
                        this.eGui.setAttribute('style', "text-decoration:none");
                        this.eGui.setAttribute('target', "_blank");
                    }
                }
                getGui() {
                    return this.eGui;
                }
                }
            """)
        )

    gridOptions = gb.build()
    response_data = AgGrid(
        df_filtered, 
        gridOptions=gridOptions,
        #height=table_height, 
        width='100%',
        data_return_mode=return_mode_value, 
        update_mode=update_mode_value,
        fit_columns_on_grid_load=fit_columns_on_grid_load,
        allow_unsafe_jscode=True, #Set it to True to allow jsfunction to be injected
        enable_enterprise_modules=enable_enterprise_modules
        )['selected_rows']
    return response_data


## run literature search
def literature(url_api: str = None,
               selection: list = None):
    st.markdown("### Literature ###")
    df_filtered = pd.DataFrame()

    filter_entity_labels_1 = filter_entity_attributes_1 = filter_entity_operators_1 = filter_entity_values_1 = ""
    with st.expander("API call settings"):
        st.markdown("**Target:**")
        col1, col2, col3, col4 = st.columns(4)
        goal_entity_label = col1.selectbox("Entity class", 
                                        [ "article"])
        goal_entity_attribute = col2.text_input(label = "Attribute", 
                                                value = "")
        goal_entity_operator = col3.selectbox("Operator", 
                                            ["=", "<", ">", "<=", ">=", "contains"])
        goal_entity_value = col4.text_input(label = "Value", 
                                            value = "")
        st.markdown("**Filter:**")
        col11, col21, col31, col41 = st.columns(4)
        if selection != None:
                if len(selection.keys()) > 0:
                    any_contains_entity = False
                    for entity_class in selection.keys():
                        if len(selection[entity_class]) > 0:
                            any_contains_entity = True
                    if any_contains_entity:
                        for entity_class in selection:
                            for entity in selection[entity_class]:
                                for attribute in ["name"]:#, "label"]:
                                    fel1 = col11.text_input("Entity class", 
                                                    value = entity_class, 
                                                    key = "label"  + entity_class + entity[attribute])
                                    filter_entity_labels_1 = ",".join([filter_entity_labels_1, fel1]) \
                                                            if len(filter_entity_labels_1) > 0 \
                                                            else fel1
                                    fea1 = col21.text_input("Attribute", 
                                                            value = attribute,
                                                            key = "attributes"  + entity_class + entity[attribute])
                                    filter_entity_attributes_1 = ",".join([filter_entity_attributes_1, fea1]) \
                                                                if len(filter_entity_attributes_1) > 0 \
                                                                else fea1
                                    feo1 = col31.text_input("Operator", 
                                                            value = "=",
                                                            key = "operators"  + entity_class + entity[attribute])
                                    filter_entity_operators_1 = ",".join([filter_entity_operators_1, feo1]) \
                                                                if len(filter_entity_operators_1) > 0 \
                                                                else feo1
                                    fev1 = col41.text_input(label = "Value", 
                                                            value = entity[attribute],
                                                            key = "values"  + entity_class + entity[attribute])
                                    filter_entity_values_1 = ",".join([filter_entity_values_1, fev1]) \
                                                            if len(filter_entity_values_1) > 0 \
                                                            else fev1

    #data_url = f"{url_api}label_abundance?goal_entity_label={goal_entity_label}&filter_entity_labels_1={filter_entity_labels_1}&filter_entity_attributes_1={filter_entity_attributes_1}&filter_entity_operators_1={filter_entity_operators_1}&filter_entity_values_1={filter_entity_values_1}{goal_entity_filter}&goal_entity_min_mentions=10&sort_string=score%20DESC"
    #data_url = f"{url_api}top_n_articles_for_label?count=1000&norm_by_age=true&label={filter_entity_labels_1}&field={filter_entity_attributes_1}&operator={filter_entity_operators_1}&terms={filter_entity_values_1}&format=csv"
    goal_entity_filter = ""
    if (len(goal_entity_attribute) > 0 \
        and len(goal_entity_operator) > 0 \
            and len(goal_entity_value) > 0):
        goal_entity_filter = f"&goal_entity_attribute={goal_entity_attribute}&goal_entity_operator={goal_entity_operator}&goal_entity_value={goal_entity_value}"
    
    literature_data = []
    if len(filter_entity_labels_1) > 0:
        data_url = f"{url_api}label_abundance?goal_entity_label={goal_entity_label}&filter_entity_labels_1={filter_entity_labels_1}&filter_entity_attributes_1={filter_entity_attributes_1}&filter_entity_operators_1={filter_entity_operators_1}&filter_entity_values_1={filter_entity_values_1}{goal_entity_filter}&goal_entity_min_mentions=10&sort_string=score%20DESC"

        ## filter
        df_complete = run_query(data_url)

        st.session_state.count_rows = len(df_filtered)

        if "max_rows_table" not in st.session_state:
            st.session_state.max_rows_table = "10"

        df_filtered = df_complete

        with st.expander("Table result", expanded= True):
            goal_entity_label = "article"
            literature_data = render_table(df_filtered, goal_entity_label)
    else:
        st.markdown(""" | :warning: **Please select at least one of the entities from the result tables** :warning: |
| --- | """)

    return literature_data, df_filtered


## run enrichment
def enrichment(url_api: str = None,
               selection: list = None,
               literature_only: bool = False):
    st.markdown("### Enrichment ###")
    df_filtered = pd.DataFrame()

    global_col1, global_col2, global_col3 = st.columns(3)
    filter_entity_labels_1 = filter_entity_attributes_1 = filter_entity_operators_1 = filter_entity_values_1 = ""
    ## API call
    with st.expander("API call settings"):
        st.markdown("**Target:**")
        col1, col2, col3, col4 = st.columns(4)
        if not literature_only:
            goal_entity_label = col1.selectbox("Entity class", 
                                        [ "gene", "disease", "chemical", "species", "cellline"])
        else:
            goal_entity_label = col1.selectbox("Entity class", 
                                        [ "article"])
        goal_entity_attribute = col2.text_input(label = "Attribute", 
                                                value = "")
        goal_entity_operator = col3.selectbox("Operator", 
                                            ["=", "<", ">", "<=", ">=", "contains"])
        goal_entity_value = col4.text_input(label = "Value", 
                                            value = "")
        st.markdown("**Filter:**")
        col11, col21, col31, col41 = st.columns(4)
        if selection != None:
            if len(selection.keys()) > 0:
                any_contains_entity = False
                for entity_class in selection.keys():
                    if len(selection[entity_class]) > 0:
                        any_contains_entity = True
                if any_contains_entity:
                    for entity_class in selection:
                        for entity in selection[entity_class]:
                            for attribute in ["name"]:#, "label"]:
                                fel1 = col11.text_input("Entity class", 
                                                value = entity_class, 
                                                key = "label"  + entity_class + entity[attribute])
                                filter_entity_labels_1 = ",".join([filter_entity_labels_1, fel1]) \
                                                        if len(filter_entity_labels_1) > 0 \
                                                        else fel1
                                fea1 = col21.text_input("Attribute", 
                                                        value = attribute,
                                                        key = "attributes"  + entity_class + entity[attribute])
                                filter_entity_attributes_1 = ",".join([filter_entity_attributes_1, fea1]) \
                                                            if len(filter_entity_attributes_1) > 0 \
                                                            else fea1
                                feo1 = col31.text_input("Operator", 
                                                        value = "=",
                                                        key = "operators"  + entity_class + entity[attribute])
                                filter_entity_operators_1 = ",".join([filter_entity_operators_1, feo1]) \
                                                            if len(filter_entity_operators_1) > 0 \
                                                            else feo1
                                fev1 = col41.text_input(label = "Value", 
                                                        value = entity[attribute],
                                                        key = "values"  + entity_class + entity[attribute])
                                filter_entity_values_1 = ",".join([filter_entity_values_1, fev1]) \
                                                        if len(filter_entity_values_1) > 0 \
                                                        else fev1

    goal_entity_filter = ""
    if (len(goal_entity_attribute) > 0 \
        and len(goal_entity_operator) > 0 \
            and len(goal_entity_value) > 0):
        goal_entity_filter = f"&goal_entity_attribute={goal_entity_attribute}&goal_entity_operator={goal_entity_operator}&goal_entity_value={goal_entity_value}"
    
    enrichment_data = []
    if len(filter_entity_labels_1) > 0:
        data_url = f"{url_api}label_abundance?goal_entity_label={goal_entity_label}&filter_entity_labels_1={filter_entity_labels_1}&filter_entity_attributes_1={filter_entity_attributes_1}&filter_entity_operators_1={filter_entity_operators_1}&filter_entity_values_1={filter_entity_values_1}{goal_entity_filter}&goal_entity_min_mentions=2&sort_string=score%20DESC"

        ## filter
        df_complete = run_query(data_url)

        df_filtered = df_complete
        st.session_state.count_rows = len(df_filtered)

        if "max_rows_table" not in st.session_state:
            st.session_state.max_rows_table = "10"
        with st.expander("Table result", expanded= True):
            enrichment_data = render_table(df_filtered, goal_entity_label)

    else:
        st.markdown(""" | :warning: **Please select at least one of the entities from the result tables** :warning: |
| --- | """)
    
    return enrichment_data, df_filtered

## run top literature
def top_literature(url_api: str = None,
               selection: list = None,
               top_n: int = 100,
               ):
    st.markdown("### Literature ###")
    df_filtered = pd.DataFrame()

    global_col1, global_col2, global_col3 = st.columns(3)
    filter_entity_labels_1 = filter_entity_attributes_1 = filter_entity_operators_1 = filter_entity_values_1 = ""
    ## API call
    with st.expander("API call settings"):
        st.markdown("**General:**")
        col10, col20, col30, col40 = st.columns(4)
        top_n = col10.text_input(label = "Max number of articles", 
                                                value = "100")
        st.markdown("**Article filter:**")
        col1, col2, col3, col4 = st.columns(4)

        article_attributes = col1.text_input(label = "Attribute", 
                                                value = "")
        article_operators = col2.selectbox("Operator", 
                                            ["=", "<", ">", "<=", ">=", "contains"])
        article_values = col3.text_input(label = "Value", 
                                            value = "")
        st.markdown("**Filter:**")
        col11, col21, col31, col41 = st.columns(4)
        if selection != None:
            if len(selection.keys()) > 0:
                any_contains_entity = False
                for entity_class in selection.keys():
                    if len(selection[entity_class]) > 0:
                        any_contains_entity = True
                if any_contains_entity:
                    for entity_class in selection:
                        for entity in selection[entity_class]:
                            for attribute in ["name"]:#, "label"]:
                                fel1 = col11.text_input("Entity class", 
                                                value = entity_class, 
                                                key = "label"  + entity_class + entity[attribute])
                                filter_entity_labels_1 = ",".join([filter_entity_labels_1, fel1]) \
                                                        if len(filter_entity_labels_1) > 0 \
                                                        else fel1
                                fea1 = col21.text_input("Attribute", 
                                                        value = attribute,
                                                        key = "attributes"  + entity_class + entity[attribute])
                                filter_entity_attributes_1 = ",".join([filter_entity_attributes_1, fea1]) \
                                                            if len(filter_entity_attributes_1) > 0 \
                                                            else fea1
                                feo1 = col31.text_input("Operator", 
                                                        value = "=",
                                                        key = "operators"  + entity_class + entity[attribute])
                                filter_entity_operators_1 = ",".join([filter_entity_operators_1, feo1]) \
                                                            if len(filter_entity_operators_1) > 0 \
                                                            else feo1
                                fev1 = col41.text_input(label = "Value", 
                                                        value = entity[attribute],
                                                        key = "values"  + entity_class + entity[attribute])
                                filter_entity_values_1 = ",".join([filter_entity_values_1, fev1]) \
                                                        if len(filter_entity_values_1) > 0 \
                                                        else fev1

    article_filter = ""
    if (len(article_attributes) > 0 \
        and len(article_operators) > 0 \
            and len(article_values) > 0):
        article_filter = f"&article_attributes={article_attributes}&article_operators={article_operators}&article_values={article_values}"
    
    enrichment_data = []
    if len(filter_entity_labels_1) > 0:
        
        #data_url = f"{url_api}label_abundance?goal_entity_label={goal_entity_label}&filter_entity_labels_1={filter_entity_labels_1}&filter_entity_attributes_1={filter_entity_attributes_1}&filter_entity_operators_1={filter_entity_operators_1}&filter_entity_values_1={filter_entity_values_1}{goal_entity_filter}&goal_entity_min_mentions=2&sort_string=score%20DESC"
        data_url = f"{url_api}top_n_articles_for_label?count={str(top_n)}&filter_entity_labels_1={filter_entity_labels_1}&filter_entity_attributes_1={filter_entity_attributes_1}&filter_entity_operators_1={filter_entity_operators_1}&filter_entity_values_1={filter_entity_values_1}{article_filter}&format=csv"

        ## filter
        df_complete = run_query(data_url)

        df_filtered = df_complete
        st.session_state.count_rows = len(df_filtered)

        if "max_rows_table" not in st.session_state:
            st.session_state.max_rows_table = "10"
        with st.expander("Table result", expanded= True):
            enrichment_data = render_table(df_filtered, "article")

    else:
        st.markdown(""" | :warning: **Please select at least one of the entities from the result tables** :warning: |
| --- | """)
    
    return enrichment_data, df_filtered

## graph analysis
def graph_analysis(
               selected_ids: list = None,
               title: str = ""):

        st.markdown("---")
        st.markdown("### Graph Analysis ###")

        with st.expander("Graph", expanded= True):
            #graph_query = "main-diseases"
            #graph_url = f"{url_api}cytoscape/predefined?query=" + graph_query
            #nodes, edges = create_nodes_edges(graph_url)        
            
            
            nodes, edges = get_neo4j_nodes_edges(count_literature=50, selected_ids=selected_ids)  

            #if 'nodes' not in st.session_state:
            node_x = []
            node_y = []
            node_color = []
            node_text = []
            for index, node_key in enumerate(nodes.keys()):
                x = nodes[node_key]['position']['x']
                y = nodes[node_key]['position']['y']
                color = nodes[node_key]['data']['color']
                node_x.append(x)
                node_y.append(y)
                node_color.append(color)
                hover_info = "<br>".join(["" + str(this_key) + ": " + \
                                        str(nodes[node_key]['data']['tooltip'][this_key]) \
                                            for this_key in (nodes[node_key]['data']['tooltip']).keys()])
                node_text.append(hover_info)
            node_trace = go.Scatter(
                x=node_x, y=node_y,
                mode='markers',
                hoverinfo='text',
                marker=dict(
                    #showscale=True,
                    # colorscale options
                    #'Greys' | 'YlGnBu' | 'Greens' | 'YlOrRd' | 'Bluered' | 'RdBu' |
                    #'Reds' | 'Blues' | 'Picnic' | 'Rainbow' | 'Portland' | 'Jet' |
                    #'Hot' | 'Blackbody' | 'Earth' | 'Electric' | 'Viridis' |
                    colorscale='YlGnBu',
                    reversescale=True,
                    color=node_color,
                    size=10,
                    opacity=0.6,
                    #colorbar=dict(
                    #    thickness=15,
                    #    title='Node Connections',
                    #    xanchor='left',
                    #    titleside='right'
                    #),
                    line_width=2))
                #st.session_state.nodes = node_trace
            node_trace.text = node_text

            edge_x = []
            edge_y = []
            #st.json(nodes)
            for edge_key in edges.keys():
                source_node_id = edges[edge_key]['data']['source']
                target_node_id = edges[edge_key]['data']['target']
                x0 = nodes[source_node_id]['position']['x']
                y0 = nodes[source_node_id]['position']['y']
                x1 = nodes[target_node_id]['position']['x']
                y1 = nodes[target_node_id]['position']['y']
                edge_x.append(x0)
                edge_x.append(x1)
                edge_x.append(None)
                edge_y.append(y0)
                edge_y.append(y1)
                edge_y.append(None)
                #x = nodes[node_key]['position']['x']
                #y = nodes[node_key]['position']['y']
                #color = nodes[node_key]['data']['color']
                #node_x.append(x)

            edge_trace = go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=0.5, color='#CCC'),
                hoverinfo='none',
                mode='lines')
            
            show_edges = st.checkbox("show edges", value=True)
            data_source = [node_trace]
            if show_edges:
                data_source = [edge_trace, node_trace ]
            fig = go.FigureWidget(data=data_source,#st.session_state.nodes],
                layout=go.Layout(
                    title=title,
                    titlefont_size=16,
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20,l=5,r=5,t=40),
                    annotations=[ dict(
                        text="t-SNE representation of a node2vec embedding for the graph",
                        showarrow=False,
                        xref="paper", yref="paper",
                        x=0.005, y=-0.002 ) ],
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                    )

            selected_points = plotly_events(fig, click_event=True, hover_event=False, select_event=True)
            
        ordered_list_markdown = "<ol>"
        with st.expander("Selection", expanded= True):
            if len(selected_points) > 0:

                for index, selection in enumerate(selected_points):
                    ordered_list_markdown += ("<li>")
                    #st.markdown("<li>", unsafe_allow_html = True)
                    ordered_list_markdown +=  (node_text[selection["pointIndex"]])
                    #st.markdown(node_text[selection["pointIndex"]], unsafe_allow_html = True)   
                    ordered_list_markdown += ("</li>")
                    #st.markdown("</li>", unsafe_allow_html = True)
                    
                #st.markdown("</ol>", unsafe_allow_html = True)
                ordered_list_markdown += ("</ol>")
                st.markdown(ordered_list_markdown, unsafe_allow_html = True)
            else:
                st.markdown("No node selected")
        


def clear_session_state():
    for key in st.session_state.keys():
        del st.session_state[key]


def validate_max_rows():
    st.session_state.max_rows_table = int(st.session_state.max_rows_table)