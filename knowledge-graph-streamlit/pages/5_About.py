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
url_api_external = config['FRONTEND-settings']['url_api_external']
title = config['FRONTEND-settings']['title']
default_disease = config['FRONTEND-settings']['default_disease']
use_cert = config['FRONTEND-settings']['use_cert'].lower() == 'true'
project_name = config['FRONTEND-settings']['project_name']

session = requests.Session()
session.trust_env = False

hlp.config_streamlit(title=title)

st.markdown("<h1 style='text-align: center;'>Biomedical Knowledge Graph</h1>", unsafe_allow_html=True)

st.markdown(f'''
The biomedical knowledge graph is a network of biomedical entities, their semantic types, properties and relationships. First, a **citation graph** is build from relevant <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" >Pubmed</a> literature. Incoming and outgoing citations / references are also incorporated. Then six additional biomedical entity classes and a custom list of keywords are extracted from the text by using <a href="https://www.ncbi.nlm.nih.gov/research/pubtator/" target="_blank" >PubTator</a>, which leads to seven different entity classes: **articles, diseases, genes, chemicals, cellline, species, keywords**. 
By connecting the genes with associated pathway / ontology concepts (KEGG pathways, GO-terms, other pathways) the final graph consists of 16 different entities with 16 types of relationships. The resulting graph schema is depicted here:
''', unsafe_allow_html=True)
col1, col2, col3 = st.columns((2,6,2))
with col1:
    st.write(' ')
with col2:
    st.image("media/images/graph_schema.png")
with col3:
    st.write(' ')
st.markdown(f'''
The statistics for the entire knowledge graph can be found <a href="{url_api_external}statistics" target="_blank" >here</a> and in order to send your own requests to the database, make use of the <a href="{url_api_external[:-8]}" target="_blank" >API</a>.
<a href="https://neo4j.com" target="_blank" >Neo4J</a> is used as the database technology.
''', unsafe_allow_html=True) 
            
#st.markdown('''## Entity statistics (log10 transformed)
#And here are the log10 transformed counts
#''')
#st.bar_chart(df_test_all[[project_name+ " log10 transformed"]])

st.markdown('''
## Formulas
The tables use different scores in order to rank articles or entities. Here are the mathematical formulas for the scores:
#### Literature
For each article, which is cited at least once, the score is defined by:
''')
st.latex(r'''
\begin{equation*}
\begin{split}
&score_i = \frac{c_{i,all} + w \times c_{i,sub}} {age_i} \\
&\text{where }  \\
&i\textrm{: article ID} \\
&c_{i,all}\textrm{: all incoming citations for article }i \\
&c_{i,sub}\textrm{: subgraph citations - all incoming citations from the disease subgraph (citations, that are also mentioning the disease itself) for article }i \\
&w\textrm{: weight for subgraph citations; default: } w = 100 \\
&age_i\textrm{: age in month of article }i \\
\end{split}
\end{equation*}
''')
         
st.markdown('''
#### Latest Literature
By using the sort option (click on the column name) you can also sort by age. 
Be aware that by default we only consider the top 100 entries. 
In order to get all literature (with at least one citation), you may want to increase the limit parameter 
(expand the parameters in the upper area of the results page).

#### Genes / Chemicals / Diseases
The score of each entity is calculated by taking the following formula:
''')
st.latex(r'''
            \begin{equation*}
            \begin{split}
            &score_i = \frac{r_{sub}}{r_{all}} \\
            &\text{where }  \\
            &i\textrm{: entity ID}\\
            &r_{sub}\textrm{: entity frequency in the disease subgraph} \\
            &r_{all}\textrm{: entity frequency in the whole graph}") \\
            \end{split}
            \end{equation*}
        ''')
st.markdown("The score of each entity is calculated by taking the following formula: ")
                


## graph explanation
st.markdown('''
#### Graphs
The graphs display some central subgraphs that shed light on the main literature, recent literature trends and the most abundant entities.

- **Main Literature**: Top 10 articles with associated biomedical entities and KEGG pathways.

- **Latest Literature**: Top 10 articles within the last 100 days with associated biomedical entities and KEGG pathways.

- **Main Entities**: For the top 5 diseases the main literature is considered. Based on these articles we are linking the top associated biomedical entities with the co-occurring diseases.
''')

