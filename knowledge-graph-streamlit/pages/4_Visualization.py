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

selection_ids_enrichment = []
if "selection_ids_enrichment" in st.session_state:
    selection_ids_enrichment = st.session_state["selection_ids_enrichment"] 
selection_ids_visual = []
if "selection_ids_visual" in st.session_state:
    selection_ids_visual = st.session_state["selection_ids_visual"] 


hlp.graph_analysis(
               selected_ids = selection_ids_enrichment + selection_ids_visual,
               title = title)

hlp.compile_sidebar()