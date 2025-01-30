# Biomedical Knowledge Graph

The biomedical knowledge graph is a network of biomedical entities, their semantic types, properties and relationships. First, a **citation graph** is build from relevant <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" >Pubmed</a> literature. Incoming and outgoing citations / references are also incorporated. Then six additional biomedical entity classes and a custom list of keywords are extracted from the text by using <a href="https://www.ncbi.nlm.nih.gov/research/pubtator/" target="_blank" >PubTator</a>, which leads to seven different entity classes: **articles, diseases, genes, chemicals, cellline, species, keywords**. 
By connecting the genes with associated pathway / ontology concepts (KEGG pathways, GO-terms, other pathways) the final graph consists of 16 different entities with 16 types of relationships. The resulting graph schema is depicted here:
::: align-center
![graphschema](https://files.ims.bio/knowledge-graph/images/graph_schema.png "Graph Schema"){{{width="800" height="auto"}}}
::: 
The statistics for the entire knowledge graph can be found <a href="<replace_base_api_url>/statistics" target="_blank" >here</a> and in order to send your own requests to the database, make use of the <a href="https://kg-<replace_project_name>-api.<replace_project_domain>" target="_blank" >API</a>.
<a href="https://neo4j.com" target="_blank" >Neo4J</a> is used as the database technology.