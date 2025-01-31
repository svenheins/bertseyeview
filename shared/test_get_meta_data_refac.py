#!/usr/bin/env python3

import logging
import sys
import os
import time
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from typing import List
import json

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def batch(iterable: list, n: int = 1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx : min(ndx + n, l)]

def request_with_delay(url: str, api_delay: float = 0.0, my_timeout: float = 20.0):
    try:
        response = requests.get(url, timeout=my_timeout)
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.exceptions.RequestException as err:
        logging.error(f"Request failed: {str(err)}")
        return None
    else:
        time.sleep(api_delay)
        return response

def get_meta_data(
    pubmed_ids_all_batches: list,
    bioconcepts: str = "none",
    batch_size: int = 100,
    run_pubtator=True,
) -> pd.DataFrame:
    title_list = []
    abstract_list = []
    annotations_list = []
    sortpubdate_list = []
    epubdate_list = []
    authors_list = []
    journal_list = []

    ## pubtator part: retrieve title, abstract and annotations
    pubtator_text = None
    pubtator_meta = {}
    bioconcepts_list = bioconcepts.split(",")

    ## define batches
    for pubmed_ids_batch in batch(range(0, len(pubmed_ids_all_batches)), batch_size):
        pubmed_ids = [str(pubmed_ids_all_batches[i]) for i in list(pubmed_ids_batch)]
        pubmed_ids_join = ",".join([str(pubmed_id_str) for pubmed_id_str in pubmed_ids])
        
        logging.info(f"Processing batch of PMIDs: {pubmed_ids}")

        if run_pubtator:
            pubtator_url = (
                "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/"
                "publications/export/biocxml?pmids=" + pubmed_ids_join + "&full=true"
            )
            successful_request = False
            count_requests = 0
            while successful_request != True and count_requests < 3:  # Limit retries
                pubtator_response = request_with_delay(pubtator_url)
                count_requests += 1
                if count_requests > 1:
                    logging.info("count_requests = " + str(count_requests))
                if pubtator_response != None:
                    pubtator_text = pubtator_response.content.decode("utf-8")
                    try:
                        logging.debug(f"Received PubTator response: {pubtator_text[:500]}...")
                        root = ET.fromstring(pubtator_text)
                        
                        for document in root.findall('.//document'):
                            # Get PubMed ID from passage infon
                            pubmed_id_pubtator = None
                            pmc_id_pubtator = None
                            for id in document.findall('.//id'):
                                pubmed_id_pubtator = id.text
                            for passage in document.findall('.//passage'):
                                for infon in passage.findall('.//infon'):
                                    if infon.get('key') == 'article-id_pmid':
                                        pubmed_id_pubtator = infon.text
                                        break
                                    if infon.get('key') == 'article-id_pmc':
                                        pmc_id_pubtator = infon.text
                                        break
                                if pubmed_id_pubtator:
                                    break
                            
                            if not pubmed_id_pubtator:
                                logging.warning("Could not find PMID in PubTator response")
                                continue
                                
                            logging.info(f"Processing PMID from PubTator: {pubmed_id_pubtator}")
                            
                            # Initialize PubTator variables
                            title_pubtator = ""
                            abstract_pubtator = ""
                            authors_pubtator = ""
                            annotations_pubtator = {
                                'disease': 'Null',
                                'gene': 'Null',
                                'chemical': 'Null',
                                'species': 'Null',
                                'mutation': 'Null',
                                'cellline': 'Null'
                            }
                            
                            # Process passages
                            for passage in document.findall('.//passage'):
                                # Get type
                                type_elem = passage.find('.//infon[@key="type"]')
                                if type_elem is not None:
                                    # Get title
                                    if type_elem.text == "title":
                                        text_elem = passage.find('.//text')
                                        if text_elem is not None and text_elem.text:
                                            title_pubtator = text_elem.text
                                            logging.debug(f"Found title: {title_pubtator}")
                                    # Get abstract
                                    elif type_elem.text == "abstract":
                                        text_elem = passage.find('.//text')
                                        if text_elem is not None and text_elem.text:
                                            abstract_pubtator = text_elem.text
                                            logging.debug(f"Found abstract: {abstract_pubtator[:100]}...")
                                
                                # Get authors
                                authors_elem = passage.find('.//infon[@key="authors"]')
                                if authors_elem is not None and authors_elem.text:
                                    authors_pubtator = authors_elem.text
                                    logging.debug(f"Found authors: {authors_pubtator}")
                            
                            # Process annotations
                            entity_annotations = {
                                'Disease': [], 'Gene': [], 'Chemical': [], 
                                'Species': [], 'Mutation': [], 'CellLine': []
                            }
                            
                            for annotation in document.findall('.//annotation'):
                                try:
                                    type_elem = annotation.find('.//infon[@key="type"]')
                                    id_elem = annotation.find('.//infon[@key="identifier"]')
                                    text_elem = annotation.find('.//text')
                                    
                                    if all([type_elem is not None, id_elem is not None, text_elem is not None]):
                                        entity_type = type_elem.text
                                        entity_id = id_elem.text
                                        entity_text = text_elem.text
                                        
                                        logging.debug(f"Found annotation - Type: {entity_type}, ID: {entity_id}, Text: {entity_text}")
                                        
                                        # Skip invalid IDs
                                        if entity_id == "-" or not entity_id:
                                            logging.warning(f"Skipping invalid entity ID for {entity_type}: {entity_text}")
                                            continue
                                            
                                        if entity_type in entity_annotations:
                                            annotation_str = f"{entity_type}:{entity_id};{entity_text}"
                                            entity_annotations[entity_type].append(annotation_str)
                                            logging.debug(f"Added {entity_type} annotation: {annotation_str}")
                                except Exception as e:
                                    logging.error(f"Error processing annotation: {str(e)}")
                                    continue
                            
                            # Convert annotations to final format
                            for entity_type, annotations in entity_annotations.items():
                                entity_type_lower = entity_type.lower()
                                if annotations:
                                    annotations_pubtator[entity_type_lower] = ','.join(annotations)
                                    logging.debug(f"Final {entity_type} annotations: {annotations_pubtator[entity_type_lower]}")
                                else:
                                    annotations_pubtator[entity_type_lower] = 'Null'
                                    logging.debug(f"No {entity_type} annotations found")
                            
                            pubtator_meta[pubmed_id_pubtator] = {
                                "title": title_pubtator,
                                "abstract": abstract_pubtator,
                                "annotations": annotations_pubtator,
                                "authors": authors_pubtator
                            }
                            logging.info(f"Successfully processed PubTator data for PMID {pubmed_id_pubtator}")
                        
                        successful_request = True
                    except ET.ParseError as e:
                        logging.error(f"XML parsing error: {str(e)}")
                        if count_requests >= 3:
                            logging.error("Maximum retry attempts reached for PubTator request")
                            successful_request = True  # Exit the retry loop
                    except Exception as e:
                        logging.error(f"Error processing PubTator response: {str(e)}")
                        if count_requests >= 3:
                            logging.error("Maximum retry attempts reached for PubTator request")
                            successful_request = True  # Exit the retry loop
                else:
                    logging.error("Failed to get response from PubTator")
                    if count_requests >= 3:
                        logging.error("Maximum retry attempts reached for PubTator request")
                        successful_request = True  # Exit the retry loop
                
                time.sleep(1)  # Add delay between retries
        ## meta part: retrieve epubdate, authors and journal
        meta_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            f"?db=pubmed&id={pubmed_ids_join}&retmode=json"
        )
        
        retry_count = 0
        max_retries = 3
        while retry_count < max_retries:
            meta_response = request_with_delay(meta_url, api_delay=0.5)  # Add delay between E-utils requests
            if meta_response is not None:
                try:
                    meta_json = meta_response.json()
                    logging.debug(f"E-utils response: {json.dumps(meta_json, indent=2)[:500]}...")
                    
                    for pubmed_id in pubmed_ids:
                        pubmed_id = str(pubmed_id)
                        logging.info(f"Processing metadata for PMID {pubmed_id}")
                        
                        if pubmed_id in pubtator_meta:
                            logging.debug(f"Found PubTator data for PMID {pubmed_id}")
                            title_list.append(pubtator_meta[pubmed_id]["title"])
                            abstract_list.append(pubtator_meta[pubmed_id]["abstract"])
                            annotations_list.append(pubtator_meta[pubmed_id]["annotations"])
                            authors_list.append(pubtator_meta[pubmed_id]["authors"])
                        else:
                            logging.warning(f"No PubTator data found for PMID {pubmed_id}")
                            title_list.append("")
                            abstract_list.append("")
                            annotations_list.append({
                                'disease': 'Null',
                                'gene': 'Null',
                                'chemical': 'Null',
                                'species': 'Null',
                                'mutation': 'Null',
                                'cellline': 'Null'
                            })
                            authors_list.append("")

                        if pubmed_id in meta_json.get("result", {}):
                            meta_result = meta_json["result"][pubmed_id]
                            sortpubdate_list.append(meta_result.get("sortpubdate", ""))
                            epubdate_list.append(meta_result.get("epubdate", ""))
                            journal_list.append(meta_result.get("fulljournalname", ""))
                            logging.debug(f"Added metadata for PMID {pubmed_id}")
                        else:
                            logging.warning(f"No E-utils metadata found for PMID {pubmed_id}")
                            sortpubdate_list.append("")
                            epubdate_list.append("")
                            journal_list.append("")
                except Exception as e:
                    logging.error(f"Error processing E-utils response: {str(e)}")
                    retry_count += 1
                else:
                    break
            else:
                logging.error("Failed to get response from E-utils")
                retry_count += 1

    # Create DataFrame
    df = pd.DataFrame({
        "pubmed_id": pubmed_ids_all_batches,
        "title": title_list,
        "abstract": abstract_list,
        "sortpubdate": sortpubdate_list,
        "epubdate": epubdate_list,
        "authors": authors_list,
        "journal": journal_list,
        "annotations": annotations_list
    })

    logging.info(f"Final DataFrame shape: {df.shape}")
    logging.debug(f"DataFrame head:\n{df.head()}")

    # Print results for each PMID
    for _, row in df.iterrows():
        logging.info("\n" + "=" * 80)
        logging.info(f"Results for PMID {row['pubmed_id']}:")
        logging.info(f"Title: {row['title']}")
        logging.info(f"Authors: {row['authors']}")
        logging.info(f"Journal: {row['journal']}")
        logging.info("\nAnnotations:")
        for entity_type, annotations in row['annotations'].items():
            logging.info(f"{entity_type}: {annotations}")
        logging.info("=" * 80 + "\n")

    return df

def main():
    # Test PMIDs known to have good entity annotations
    test_pmids = [
        "36116464",  # Paper with gene annotations
        "28980624",  # Another paper with known annotations
        "28700839"   # Another test case
    ]
    
    try:
        # Call get_meta_data with debug settings
        logging.info("Starting metadata retrieval for PMIDs: %s", test_pmids)
        
        result_df = get_meta_data(
            pubmed_ids_all_batches=test_pmids,
            bioconcepts="Gene,Disease,Chemical,Species,Mutation,CellLine",
            batch_size=1,  # Process one at a time for easier debugging
            run_pubtator=True
        )
        
    except Exception as e:
        logging.error("Error occurred: %s", str(e), exc_info=True)

if __name__ == "__main__":
    main()
