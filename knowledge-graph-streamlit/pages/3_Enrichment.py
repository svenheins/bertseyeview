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
hlp.initialize_requests()
hlp.initialize_neo4j()
if ("neo4j_manager" in st.session_state):
    neo4j_manager = st.session_state["neo4j_manager"]


## get selected_ids from search and analysis before
selection_enrichment_list = []
selection = None
if "selection_enrichment" in st.session_state:
    #selection = st.session_state["selection_enrichment"]
    selection = st.session_state["selection_enrichment"]

df_filtered = pd.DataFrame()
selection_enrichment_list, df_filtered = hlp.enrichment(url_api= url_api, 
                     selection = selection,              
                     )

hlp.compile_sidebar(selection_enrichment_list = selection_enrichment_list)

if (not df_filtered.empty):
    st.download_button(
        "Download as CSV",
        data=df_filtered.to_csv(),
        file_name="enrichment.csv",
        #mime="application/vnd.ms-excel",
)