import streamlit as st
import pandas as pd
import numpy as np
import src.helper as hlp
import configparser


config_path = './config.ini'
config = configparser.ConfigParser()
config.read(config_path)
url_api = config['FRONTEND-settings']['url_api']
title = config['FRONTEND-settings']['title']
default_disease = config['FRONTEND-settings']['default_disease']

hlp.config_streamlit(title=title)

if not "requests_session" in st.session_state:
    hlp.initialize_requests()

if (not "neo4j_manager" in st.session_state):
    hlp.initialize_neo4j()
    
selection_pre = []
selection_ids_pre = []
if "selection_enrichment" in st.session_state:
    selection_pre = st.session_state["selection_enrichment"]
    selection_ids_pre = [id["ID(a)"] for category in selection_pre.keys() for id in selection_pre[category] ]

selection_from_search = hlp.search_and_select(url_api= url_api, 
                     title = title)

selection_ids_enrichment = [id["ID(a)"] for category in selection_from_search.keys() for id in selection_from_search[category] ]
## combine id lists and dicts
selection_ids_enrichment = list(set(selection_ids_enrichment + selection_ids_pre))
if len(selection_pre) > 0:
    for entity_class in selection_from_search:
        if entity_class in selection_pre:
            for pre_val in selection_pre[entity_class]:
                found_entry = False
                for val in selection_from_search[entity_class]:
                    if val["ID(a)"] == pre_val["ID(a)"]:
                        found_entry = True
                        break
                ## pre_dict contains data that has not been selected -> append this to list
                if not found_entry:
                    selection_from_search[entity_class].append(pre_val)

st.session_state["selection_ids_enrichment"] = selection_ids_enrichment
st.session_state["selection_enrichment"] = selection_from_search

hlp.compile_sidebar()

