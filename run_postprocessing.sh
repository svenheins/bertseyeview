#!/bin/bash

curl -X GET "http://localhost:5000/api/v1/merge_nodes?from_keys=name%2Clabel&from_values=Disease%3AMESH%3AD008113%2CALS&to_keys=name&to_values=Disease%3AMESH%3AD000690" -H  "accept: application/json"
#curl -X GET "http://localhost:5000/api/v1/delete_node?del_keys=name%2Clabel&del_values=Disease%3AMESH%3AD008113%2CALS" -H  "accept: application/json"

curl -X GET "http://localhost:5000/api/v1/merge_nodes?from_keys=name%2Clabel&from_values=Disease%3AMESH%3AC565957%2CALS&to_keys=name&to_values=Disease%3AMESH%3AD000690" -H  "accept: application/json"
#curl -X GET "http://localhost:5000/api/v1/delete_node?del_keys=name%2Clabel&del_values=Disease%3AMESH%3AC565957%2CALS" -H  "accept: application/json"

## for receiving the pathway and more meta data for each gene, we run the jupyter notebook 
## 01_get_gene_infos_mygene.ipynb

## for the pathway short_label
# from neo4j: "MATCH (n:pathway_kegg) SET n.short_label = split(n.label," - ")[0]"
