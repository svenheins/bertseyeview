import streamlit as st
import pandas as pd
import numpy as np
import configparser
import requests
import os
import sys
if sys.version_info[0] < 3: 
    from StringIO import StringIO
else:
    from io import StringIO
import requests
import src.helper as hlp

config_path = './config.ini'
config = configparser.ConfigParser()
config.read(config_path)
url_api = config['FRONTEND-settings']['url_api']
title = config['FRONTEND-settings']['title']
default_disease = config['FRONTEND-settings']['default_disease']
use_cert = config['FRONTEND-settings']['use_cert'].lower() == 'true'
project_name = config['FRONTEND-settings']['project_name']

session = requests.Session()
session.trust_env = False

hlp.config_streamlit(title=title)

st.markdown("<h1 style='text-align: center;'>Statistics: " + project_name +"</h1>", unsafe_allow_html=True)

            
@st.cache_data
def get_statistics(data_url, use_cert = False):
    if (use_cert):
        response = session.get(data_url, verify='./cert/cert.pem')
    else:
        response = session.get(data_url)
    df_response = response.json()[0]['labels']
    return df_response

stats_url = f"{url_api}statistics"
statistics = get_statistics(stats_url, use_cert=use_cert)
data_test = { 'class': statistics.keys() , 'count': statistics.values()}
df_test_all = pd.DataFrame.from_dict(data_test)
#df_test_all[project_name + " log10 transformed"] = np.log10(df_test_all['count'])
df_test_all[project_name] = (df_test_all['count'])
df_test_all = df_test_all.set_index("class")

st.bar_chart(df_test_all[[project_name]],height=600)
#st.markdown('''## Entity statistics (log10 transformed)
#And here are the log10 transformed counts
#''')
#st.bar_chart(df_test_all[[project_name+ " log10 transformed"]])