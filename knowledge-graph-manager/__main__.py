## __main__.py: main script with main loop for the knowledge-graph manager

import pandas as pd
import os
import time
import functools
import configparser
import shutil
import filecmp
import requests
import re
import json
import logging
import xml.etree.ElementTree as ET

from typing import List, Set, Dict, Tuple
from neo4j import GraphDatabase
from datetime import datetime, timedelta

from helper.neo4j_helper import Neo4j_Manager

## setup the logger to print to stdout and to the file
log_path = "/output"
log_file_name = "knowledge-graph-neo4j-helper.log"
log_file_path = os.path.join(log_path, log_file_name)

log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] \
                                %(message)s"
)
logging.basicConfig(
    filename=log_file_path,
    filemode="a",
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(log_formatter)
logging.getLogger().addHandler(consoleHandler)
logging.info("initialized the logger")


def batch(iterable: list, n: int = 1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx : min(ndx + n, l)]


def get_field_or_default_value(source_dict: dict, field: str, default):
    if field in source_dict:
        return source_dict[field]
    else:
        return default


def contains_season(date_raw: str) -> bool:
    if (
        "fall" in date_raw.lower()
        or "spring" in date_raw.lower()
        or "winter" in date_raw.lower()
        or "summer" in date_raw.lower()
    ):
        return True
    else:
        return False


def contains_month(date_raw: str) -> bool:
    if (
        "jan" in date_raw.lower()
        or "feb" in date_raw.lower()
        or "mar" in date_raw.lower()
        or "apr" in date_raw.lower()
        or "mai" in date_raw.lower()
        or "jun" in date_raw.lower()
        or "jul" in date_raw.lower()
        or "aug" in date_raw.lower()
        or "sep" in date_raw.lower()
        or "oct" in date_raw.lower()
        or "nov" in date_raw.lower()
        or "dec" in date_raw.lower()
    ):
        return True
    else:
        return False


def season_to_month(season: str) -> str:
    if "spring" in season.lower():
        return "Mar"
    elif "summer" in season.lower():
        return "Jun"
    elif "fall" in season.lower():
        return "Sep"
    elif "winter" in season.lower():
        return "Dec"
    else:
        raise Exception("season is not a season: " + season)


def extract_month(date_raw: str) -> str:
    if "jan" in date_raw.lower():
        return "Jan"
    elif "feb" in date_raw.lower():
        return "Feb"
    elif "mar" in date_raw.lower():
        return "Mar"
    elif "apr" in date_raw.lower():
        return "Apr"
    elif "mai" in date_raw.lower():
        return "Mai"
    elif "jun" in date_raw.lower():
        return "Jun"
    elif "jul" in date_raw.lower():
        return "Jul"
    elif "aug" in date_raw.lower():
        return "Aug"
    elif "sep" in date_raw.lower():
        return "Sep"
    elif "oct" in date_raw.lower():
        return "Oct"
    elif "nov" in date_raw.lower():
        return "Nov"
    elif "dec" in date_raw.lower():
        return "Dec"
    else:
        raise Exception("date_raw is not a month: " + date_raw)


def preprocess_date(pubdate_raw: str) -> str:
    if pubdate_raw == "NA" or pubdate_raw == "":
        pubdate_raw = "1900 Jan 1"
    ## season string
    if contains_season(pubdate_raw):
        ## get year, season to month and day is always first of month
        year_raw = re.match(r".*([1-3][0-9]{3})", pubdate_raw).group(1)
        month_from_season = season_to_month(pubdate_raw)
        day_season = "1"
        pubdate_raw = " ".join([str(year_raw), month_from_season, day_season])
    if len(pubdate_raw.split(" ")) < 3:
        ## assumption: day is missing
        if len(pubdate_raw.split(" ")) == 2:
            year_raw = re.match(r".*([1-3][0-9]{3})", pubdate_raw).group(1)
            day_season = "1"
            month_from_raw = "Jan"
            if contains_season(pubdate_raw):
                month_from_raw = season_to_month(pubdate_raw)
            if contains_month(pubdate_raw):
                month_from_raw = extract_month(pubdate_raw)
            pubdate_raw = " ".join([str(year_raw), month_from_raw, day_season])
            ## if this test fails, the format is not year month
            try:
                test_date = datetime.strptime(pubdate_raw, "%Y %b %d")
            except ValueError as e:
                logging.info(pubdate_raw)
                logging.info(e)
        else:
            year_raw = re.match(r".*([1-3][0-9]{3})", pubdate_raw).group(1)
            if len(year_raw) == 4:
                pubdate_raw = pubdate_raw + " Jan 1"
            else:
                pubdate_raw = "1900 Jan 1"
    ## check for special chars (example: 2021 Jan/Mar 1;
    # 2021 Jan-Mar 1 is possible!)
    contains_no_special_chars = len(re.split("-|/", pubdate_raw)) == 1
    pubdate_raw = (
        pubdate_raw
        if contains_no_special_chars
        else re.split("-|/", pubdate_raw)[0] + re.split("-|/", pubdate_raw)[1][3:]
    )
    return pubdate_raw


## simple helper function to remove quotation from comma-separated values
def get_list_from_csv_string(
    quoted_strings: str, quotation_character: str = "'", split_string: str = ","
) -> list:
    test_split = quoted_strings.split(split_string)
    new_split = test_split
    for index, term in enumerate(test_split):
        if term.startswith(quotation_character) and term.endswith(quotation_character):
            new_split[index] = term[1:-1]
    return new_split


## request something followed by a delay (pubmed allows 3 requests per second)
def request_with_delay(
    url: str, api_delay: float = 0.0, my_timeout: float = 20.0
) -> requests.Response:
    try:
        response = requests.get(url, timeout=my_timeout)
    except (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
    ) as err:
        # raise Exception("Request takes too long")
        return None  #'Server taking too long. Try again later'
    else:
        time.sleep(api_delay)
        return response


def halve_time_interval(start_date_str, end_date_str):
    # Parse the input date strings into datetime objects
    start_date = datetime.strptime(start_date_str, "%Y/%m/%d")
    end_date = datetime.strptime(end_date_str, "%Y/%m/%d")

    # Calculate the time interval in days
    time_interval = (end_date - start_date).days

    # Calculate the midpoint by adding half of the time interval to the start date
    midpoint = start_date + timedelta(days=time_interval // 2)

    # Format the midpoint and return it along with the start date
    midpoint_str = midpoint.strftime("%Y/%m/%d")

    return midpoint_str


def update_doi_csv_by_query(search_query: str, path_doi_list: str) -> None:
    if len(search_query) > 0:
        logging.info("running query = " + search_query)

        csv_out = "DOI"
        min_date = "1900/01/01"
        max_date_final = max_date = "2025/12/31"

        ## if retmax <= 9999, one query is enough to get all the data
        retmax_prepare = search_query.split("retmax=")
        if len(retmax_prepare) > 0:
            retmax = int(retmax_prepare[1].split("&")[0])
        if retmax <= 9999:
            if len(search_query) > 0:
                # logging.info("running query = " + search_query)
                csv_out = "DOI"
                result = request_with_delay(search_query)
                if result != None:
                    if result.json() != None:
                        if "esearchresult" in result.json():
                            if "idlist" in result.json()["esearchresult"]:
                                for doi in result.json()["esearchresult"]["idlist"]:
                                    csv_out = "\n".join([csv_out, str(doi)])
                        f = open(path_doi_list, "w")
                        f.write(csv_out)
                        f.close()
        ## if retmax > 9999: get all entries by defining smaller bins (time intervals)
        else:
            # search_query = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax=10000&term=kidney+immune&sort=relevance"
            total_results_query = (
                search_query + f"""&mindate={min_date}&maxdate={max_date_final}"""
            )
            result = request_with_delay(total_results_query)
            total_results = 0
            if result != None:
                if result.json() != None:
                    if "esearchresult" in result.json():
                        if "idlist" in result.json()["esearchresult"]:
                            total_results = int(result.json()["esearchresult"]["count"])
                            logging.info("Total results = " + str(total_results))

            if total_results > 0:
                current_results = 0
                while current_results < total_results:
                    search_query_interval = (
                        search_query + f"""&mindate={min_date}&maxdate={max_date}"""
                    )
                    result = request_with_delay(search_query_interval)
                    if "esearchresult" in result.json():
                        count_results = int(result.json()["esearchresult"]["count"])

                        if count_results < 9999:
                            if "idlist" in result.json()["esearchresult"]:
                                for doi in result.json()["esearchresult"]["idlist"]:
                                    csv_out = "\n".join([csv_out, str(doi)])
                            current_results = len(csv_out.split("\n")) - 1
                            logging.info(
                                "found interval: "
                                + min_date
                                + " - "
                                + max_date
                                + " | count_results = "
                                + str(count_results)
                                + ", total_results = "
                                + str(current_results)
                            )
                            min_date = max_date
                            max_date = max_date_final
                        else:
                            ## halve the time interval
                            max_date = halve_time_interval(min_date, max_date)
                    else:
                        break
                        ## just leave the result as is

                list_DOIs = ["DOI"]
                ## remove duplicates
                list_DOIs.extend(list(set(csv_out.split("\n")[1:])))
                logging.info("removing duplicates and writing to csv-file")
                final_output_str = "\n".join(list_DOIs)
                f = open(path_doi_list, "w")
                f.write(final_output_str)
                f.close()


## get meta data from a pubmed_id
## meta data = title, epubdate, abstract
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

        if run_pubtator == True:
            pubtator_url = (
                "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/"
                "publications/export/pubtator?pmids=" + pubmed_ids_join + "&concepts"
                "=" + bioconcepts
            )
            successful_request = False
            count_requests = 0
            while successful_request != True:
                pubtator_response = request_with_delay(pubtator_url)
                count_requests += 1
                if count_requests > 1:
                    logging.info("count_requests = " + str(count_requests))
                if pubtator_response != None:
                    pubtator_text = pubtator_response.content.decode("utf-8")
                    try:
                        root = ET.fromstring(pubtator_text)
                        for document in root.findall('.//document'):
                            pubmed_id_pubtator = document.get('id', '')
                            
                            # Initialize PubTator variables
                            title_pubtator = ""
                            abstract_pubtator = ""
                            authors_pubtator = ""
                            annotations_pubtator = {
                                'disease': 'Null',
                                'gene': 'Null',
                                'chemical': 'Null',
                                'species': 'Null',
                                'mutation': 'Null'
                            }
                            
                            # Get metadata from PubTator
                            if run_pubtator and pubmed_id_pubtator:  # Check for valid PMID
                                try:
                                    pubtator_url = (
                                        "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/"
                                        "publications/export/biocxml?pmids="
                                        + str(pubmed_id_pubtator)
                                        + "&full=true"
                                    )
                                    pubtator_response = request_with_delay(pubtator_url)
                                    if pubtator_response is not None and pubtator_response.content:
                                        pubtator_text = pubtator_response.content.decode("utf-8")
                                        if not pubtator_text.strip():
                                            logging.warning(f"Empty PubTator response for PMID {pubmed_id_pubtator}")
                                            continue
                                            
                                        root = ET.fromstring(pubtator_text)
                                        
                                        # Find the document element
                                        document = root.find('.//document')
                                        if document is None:
                                            logging.warning(f"No document element found for PMID {pubmed_id_pubtator}")
                                            continue
                                        
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
                                                # Get abstract
                                                elif type_elem.text == "abstract":
                                                    text_elem = passage.find('.//text')
                                                    if text_elem is not None and text_elem.text:
                                                        abstract_pubtator = text_elem.text
                                            
                                            # Get authors
                                            authors_elem = passage.find('.//infon[@key="authors"]')
                                            if authors_elem is not None and authors_elem.text:
                                                authors_pubtator = authors_elem.text
                                        
                                        # Process annotations
                                        entity_annotations = {
                                            'Disease': [], 'Gene': [], 'Chemical': [], 
                                            'Species': [], 'Mutation': []
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
                                                    
                                                    if entity_type in entity_annotations:
                                                        annotation_str = f"{entity_id};{entity_text}"
                                                        entity_annotations[entity_type].append(annotation_str)
                                            except Exception as e:
                                                logging.error(f"Error processing annotation: {str(e)}")
                                                continue
                                        
                                        # Convert annotations to final format
                                        for entity_type, annotations in entity_annotations.items():
                                            entity_type_lower = entity_type.lower()
                                            if annotations:
                                                annotations_pubtator[entity_type_lower] = ','.join(annotations)
                                            else:
                                                annotations_pubtator[entity_type_lower] = 'Null'
                                                
                                except ET.ParseError as e:
                                    logging.error(f"XML Parse error for PMID {pubmed_id_pubtator}: {str(e)}")
                                    if pubtator_response is not None:
                                        logging.error(f"Raw content: {pubtator_response.content[:500]}")
                                except Exception as e:
                                    logging.error(f"Unexpected error processing PMID {pubmed_id_pubtator}: {str(e)}")
                            
                            entry_meta = {
                                "title": title_pubtator,
                                "abstract": abstract_pubtator,
                                "annotations": annotations_pubtator,
                                "authors": authors_pubtator
                            }
                            pubtator_meta[pubmed_id_pubtator] = entry_meta
                            
                    except ET.ParseError as e:
                        logging.error(f"Failed to parse XML: {str(e)}")
                        continue
                    successful_request = True
                else:
                    logging.info("Request failed: " + pubtator_url)

        ## meta part: retrieve epubdate, authors and journal
        meta_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            "?db=pubmed&id=" + pubmed_ids_join + "&retmode=json&tool=my_tool"
            "&email=my_email@example.com"
        )

        successful_request = False
        count_requests = 0
        while successful_request != True:
            r_meta = request_with_delay(meta_url)
            count_requests += 1
            if count_requests > 1:
                logging.info("count_requests = " + str(count_requests))
            if r_meta != None:
                if "result" in r_meta.json():
                    for pubmed_id in pubmed_ids:
                        if pubmed_id in r_meta.json()["result"]:
                            if pubmed_id in pubtator_meta:
                                title_list.append(pubtator_meta[pubmed_id]["title"])
                                abstract_list.append(
                                    pubtator_meta[pubmed_id]["abstract"]
                                )
                                annotations_list.append(
                                    pubtator_meta[pubmed_id]["annotations"]
                                )
                                # sortpubdate.append(pubtator_meta[pubmed_id]['sortpubdate'])
                                # epubdate.append(pubtator_meta[pubmed_id]['epubdate'])
                                # authors.append(pubtator_meta[pubmed_id]['authors'])
                                # journal.append(pubtator_meta[pubmed_id]['journal'])
                                # pmc_id.append(pubtator_meta[pubmed_id]['pmc_id'])
                            else:
                                title_from_eutil = get_field_or_default_value(
                                    r_meta.json()["result"][pubmed_id],
                                    "title",
                                    default="NA",
                                )
                                title_list.append(title_from_eutil)
                                abstract_list.append("NA")
                                bioconcepts_list = bioconcepts.split(",")
                                annotations_all = ""
                                for bioconcept in bioconcepts_list:
                                    if len(annotations_all) > 0:
                                        annotations_all = "|".join(
                                            [annotations_all, "Null"]
                                        )
                                    else:
                                        annotations_all = "Null"

                                annotations_list.append(annotations_all)

                            sortpubdate_raw = get_field_or_default_value(
                                r_meta.json()["result"][pubmed_id],
                                "sortpubdate",
                                default="NA",
                            )
                            ## transform to iso format
                            sortpubdate_processed = sortpubdate_raw.split(" ")[
                                0
                            ].replace("/", "-")
                            sortpubdate_list.append(sortpubdate_processed)
                            epubdate_raw = get_field_or_default_value(
                                r_meta.json()["result"][pubmed_id],
                                "epubdate",
                                default="NA",
                            )
                            ## epubdate and sortpubdate are well defined /
                            # structured iso formats, but the pubdate is
                            # quite arbitrary, this is why the pubdate_raw is
                            # preprocessed and parsed quite attentive finally:
                            # if all fails, we fall back to the sortpubdate
                            if epubdate_raw == "NA" or epubdate_raw == "":
                                pubdate_raw = get_field_or_default_value(
                                    r_meta.json()["result"][pubmed_id],
                                    "pubdate",
                                    default="NA",
                                )
                                pubdate_processed = preprocess_date(pubdate_raw)
                                try:
                                    pubdate = datetime.strptime(
                                        pubdate_processed, "%Y %b %d"
                                    ).strftime("%Y-%m-%d")
                                except ValueError as e:
                                    logging.info(pubdate_raw)
                                    logging.info(pubdate_processed)
                                    logging.info(e)
                                    logging.info(
                                        "take the sortpubdate_processed "
                                        "version: " + sortpubdate_processed
                                    )
                                    epubdate_raw = datetime.strptime(
                                        sortpubdate_processed, "%Y-%m-%d"
                                    ).strftime("%Y %b %d")
                                    logging.info(
                                        "resulting epubdate_raw: " + epubdate_raw
                                    )
                            epubdate_iso = (
                                pubdate
                                if (epubdate_raw == "NA" or epubdate_raw == "")
                                else datetime.strptime(
                                    epubdate_raw, "%Y %b %d"
                                ).strftime("%Y-%m-%d")
                            )
                            epubdate_list.append(epubdate_iso)
                            authors = get_field_or_default_value(
                                r_meta.json()["result"][pubmed_id],
                                "authors",
                                default="NA",
                            )
                            authors_list.append(authors)

                            journal_list.append(
                                get_field_or_default_value(
                                    r_meta.json()["result"][pubmed_id],
                                    "fulljournalname",
                                    default="NA",
                                )
                            )
                            pmc_id = "NA"
                            if "articleids" in r_meta.json()["result"][pubmed_id]:
                                for article_id in r_meta.json()["result"][pubmed_id][
                                    "articleids"
                                ]:
                                    if article_id["idtype"] == "pmc":
                                        pmc_id = article_id["value"]

                                        if run_pubtator == True:
                                            pubtator_url_pmc = (
                                                "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocxml?pmids="
                                                + str(pubmed_id) + "&full=true"
                                            )
                                            successful_request = False
                                            count_requests = 0
                                            while successful_request != True:
                                                pubtator_response = request_with_delay(
                                                    pubtator_url_pmc
                                                )
                                                count_requests += 1
                                                if count_requests > 1:
                                                    logging.info(
                                                        "count_requests = "
                                                        + str(count_requests)
                                                    )
                                                if pubtator_response != None:
                                                    successful_request = True
                                                    ## write biocxml to temp file
                                                    with open(
                                                        "/output/pubtator_response.xml",
                                                        "w",
                                                    ) as f:
                                                        f.write(pubtator_response.text)
                                                    ner_dict = {}
                                                    ## load biocxml file and put to collection
                                                    with open(
                                                        "/output/pubtator_response.xml",
                                                        "r",
                                                    ) as fp:
                                                        collection = None
                                                        try:
                                                            collection = bioc.load(fp)
                                                        except:
                                                            logging.info(
                                                                f"Error: collection for {pmc_id}: pubtator_url = {pubtator_url_pmc}"
                                                            )
                                                        if collection != None:
                                                            # logging.info(f"Success: collection for {pmc_id}: pubtator_url = {pubtator_url_pmc}")
                                                            if (
                                                                len(
                                                                    collection.documents
                                                                )
                                                                > 0
                                                            ):
                                                                for (
                                                                    document
                                                                ) in (
                                                                    collection.documents
                                                                ):
                                                                    ## document.id is the pmc id
                                                                    if (
                                                                        len(
                                                                            document.passages
                                                                        )
                                                                        > 0
                                                                    ):
                                                                        for (
                                                                            passage
                                                                        ) in (
                                                                            document.passages
                                                                        ):
                                                                            if (
                                                                                len(
                                                                                    passage.annotations
                                                                                )
                                                                                > 0
                                                                            ):
                                                                                ## loop through all annotation
                                                                                for annotation in (
                                                                                    passage.annotations
                                                                                ):
                                                                                    ner_type = "Null"
                                                                                    ner_identifier = "Null"
                                                                                    if (
                                                                                        "type"
                                                                                        in annotation.infons
                                                                                    ):
                                                                                        ner_type = annotation.infons[
                                                                                            "type"
                                                                                        ]
                                                                                    if (
                                                                                        "identifier"
                                                                                        in annotation.infons
                                                                                    ):
                                                                                        ner_identifier = annotation.infons[
                                                                                            "identifier"
                                                                                        ]
                                                                                    ## ner-text for each entity
                                                                                    try:
                                                                                        ner_text = (
                                                                                            str(ner_type)
                                                                                            + ":"
                                                                                            + str(ner_identifier)
                                                                                            + ";"
                                                                                            + str(annotation.text)
                                                                                        )
                                                                                    except:
                                                                                        logging.info("error with ner_text")
                                                                                        
                                                                                    if (
                                                                                        ner_type.lower()
                                                                                        in ner_dict
                                                                                    ):
                                                                                        if ner_identifier:
                                                                                            if (
                                                                                                ner_identifier
                                                                                                != "Null"
                                                                                            ) and not (
                                                                                                ner_identifier
                                                                                                in ner_dict[
                                                                                                    ner_type.lower()
                                                                                                ]
                                                                                            ):
                                                                                                ner_dict[
                                                                                                    ner_type.lower()
                                                                                                ] += (
                                                                                                    ","
                                                                                                    + ner_text
                                                                                                )
                                                                                    else:
                                                                                        ner_dict[
                                                                                            ner_type.lower()
                                                                                        ] = ner_text
                                                                    ner_string = ""
                                                                    ## for each concept, build the respective entity string
                                                                    for (
                                                                        index,
                                                                        bioconcept,
                                                                    ) in enumerate(
                                                                        bioconcepts_list
                                                                    ):
                                                                        if (
                                                                            bioconcept
                                                                            in ner_dict
                                                                        ):
                                                                            ner_string += ner_dict[
                                                                                bioconcept
                                                                            ]
                                                                        else:
                                                                            ner_string += (
                                                                                "Null"
                                                                            )
                                                                        ## add separator between entity types (and not at the end)
                                                                        if (
                                                                            index
                                                                            < len(
                                                                                bioconcepts_list
                                                                            )
                                                                            - 1
                                                                        ):
                                                                            ner_string += (
                                                                                "|"
                                                                            )
                                                    ## replace the original pubtator annotation if there is a pmc annotation
                                                    if len(ner_dict) > 0:
                                                        annotations_list = (
                                                            annotations_list[:-1]
                                                        )
                                                        annotations_list.append(
                                                            ner_string
                                                        )

                            pmc_id_list.append(pmc_id)
                successful_request = True
            else:
                logging.info("Request failed: " + meta_url)

    df_content = {
        "title": title_list,
        "abstract": abstract_list,
        "annotations": annotations_list,
        "sortpubdate": sortpubdate_list,
        "epubdate": epubdate_list,
        "authors": authors_list,
        "journal": journal_list
    }

    if len(df_content["title"]) == len(pubmed_ids_all_batches):
        return_df = pd.DataFrame(data=df_content, index=pubmed_ids_all_batches)
    else:
        return_df = pd.DataFrame()
        logging.info(
            "Error: index has not the same size as the metadata-dataframe -> skipping the following batch"
            + str(pubmed_ids_all_batches)
        )
    return return_df


def is_relevant(str_candidate: str, search_terms: List[str]) -> bool:
    relevant = False
    if len(search_terms) > 0:
        for term in search_terms:
            if str(term).lower() in str(str_candidate).lower():
                relevant = True
                break
    else:
        ## if there is no filter, always return True for relevant
        relevant = True
    return relevant


def get_relevant_keywords(str_candidate: str, search_terms: List[str]) -> List[str]:
    relevant = ["Null"]
    if len(search_terms) > 0:
        for term in search_terms:
            if str(term).lower() in str(str_candidate).lower():
                ## add to the beginning of the list
                relevant.insert(0, term)
        ## if there are more than one items, remove the last (Null-item)
        if len(relevant) > 1:
            relevant = relevant[:-1]
    return relevant


## this function takes in the json_response, and the csv_content and updates
# the csv_content based on the json_response and article_data, that needs to
# be provided
def update_csv_content_by_json_response(
    json_response: requests.Response,
    csv_content: str,
    csv_header_column_count: int,
    reference_id: int,
    test_mode: bool,
    is_article_first: bool,
    filter_terms: List[str],
    additional_keywords: List[str],
    bioconcepts: str,
    article_id: str,
    article_title: str,
    article_pmc_id: str,
    article_epubdate: str,
    article_authors: str,
    article_journal: str,
    article_abstract: str,
    article_keywords: List[str],
    article_annotations: pd.DataFrame,
    run_pubtator=True,
) -> Tuple[str, int]:
    """Update CSV content with new citations."""
    if json_response is None:
        return csv_content, reference_id

    try:
        meta_json = json_response.json()
        
        # Check if response has expected structure
        if not isinstance(meta_json, dict):
            logging.error("Invalid JSON response format")
            return csv_content, reference_id
            
        # Check if response has linksets
        if "linksets" not in meta_json or not meta_json["linksets"]:
            logging.warning("No linksets found in response")
            return csv_content, reference_id
            
        # Check if linksets has linksetdbs
        linkset = meta_json["linksets"][0]
        if "linksetdbs" not in linkset or not linkset["linksetdbs"]:
            logging.warning("No linksetdbs found in linkset")
            return csv_content, reference_id
            
        # Get the links
        links = linkset["linksetdbs"][0].get("links", [])
        if not links:
            logging.warning("No links found in linksetdb")
            return csv_content, reference_id
            
        # Process links
        max_index = min(len(links), 3) if test_mode else len(links)
        other_article_list = links[:max_index]

        # Get PubTator metadata for all articles in this batch
        other_meta_df = get_meta_data(
            other_article_list,
            bioconcepts=bioconcepts,
            run_pubtator=run_pubtator
        )
        
        if other_meta_df.empty:
            logging.warning("No metadata found for articles")
            return csv_content, reference_id

        # Process each reference
        for other_article in other_article_list:
            try:
                other_meta = other_meta_df.loc[other_article]
                if not isinstance(other_meta, pd.Series):
                    logging.warning(f"Invalid metadata format for article {other_article}")
                    continue
                
                # Get metadata with proper escaping
                other_title = str(other_meta.get("title", "")).replace("|", ";")
                other_epubdate = str(other_meta.get("epubdate", "")).replace("|", ";")
                other_abstract = str(other_meta.get("abstract", "")).replace("|", ";")
                other_authors = str(other_meta.get("authors", "")).replace("|", ";")
                other_journal = str(other_meta.get("journal", "")).replace("|", ";")
                
                # Skip if no title or abstract
                if not other_title or not other_abstract:
                    logging.warning(f"Missing title or abstract for article {other_article}")
                    continue
                
                # Check if article matches filter terms
                candidate = " ".join([other_title, other_abstract])
                if not is_relevant(candidate, filter_terms):
                    logging.debug(f"Article {other_article} did not match filter terms")
                    continue
                    
                # Get keywords
                other_keywords = get_relevant_keywords(candidate, additional_keywords)
                
                # Get annotations (default to empty dict if not found)
                other_annotations = {}
                if isinstance(other_meta.get("annotations"), dict):
                    other_annotations = other_meta["annotations"]
                
                # Create CSV line
                csv_candidate = ""
                
                if is_article_first:
                    # Article metadata
                    csv_candidate = (
                        f"{reference_id}|{article_id}|{article_title}|{article_epubdate}|"
                        f"{article_authors}|{article_journal}|{article_abstract}|"
                        f"{','.join(article_keywords) if article_keywords else ''}"
                    )
                    
                    # Article entity annotations
                    for entity_type in ['disease', 'gene', 'chemical', 'species', 'mutation']:
                        csv_candidate += f"|{article_annotations.get(entity_type, 'Null')}"
                    
                    # Referenced article metadata
                    csv_candidate += (
                        f"|{reference_id}|{other_article}|{other_title}|{other_epubdate}|"
                        f"{other_authors}|{other_journal}|{other_abstract}|"
                        f"{','.join(other_keywords) if other_keywords else ''}"
                    )
                    
                    # Referenced article entity annotations
                    for entity_type in ['disease', 'gene', 'chemical', 'species', 'mutation']:
                        csv_candidate += f"|{other_annotations.get(entity_type, 'Null')}"
                    
                    # Add GO and pathway annotations
                    csv_candidate += "|Null|Null|Null|Null|Null|Null"
                else:
                    # Referenced article metadata
                    csv_candidate = (
                        f"{reference_id}|{other_article}|{other_title}|{other_epubdate}|"
                        f"{other_authors}|{other_journal}|{other_abstract}|"
                        f"{','.join(other_keywords) if other_keywords else ''}"
                    )
                    
                    # Referenced article entity annotations
                    for entity_type in ['disease', 'gene', 'chemical', 'species', 'mutation']:
                        csv_candidate += f"|{other_annotations.get(entity_type, 'Null')}"
                    
                    # Article metadata
                    csv_candidate += (
                        f"|{reference_id}|{article_id}|{article_title}|{article_epubdate}|"
                        f"{article_authors}|{article_journal}|{article_abstract}|"
                        f"{','.join(article_keywords) if article_keywords else ''}"
                    )
                    
                    # Article entity annotations
                    for entity_type in ['disease', 'gene', 'chemical', 'species', 'mutation']:
                        csv_candidate += f"|{article_annotations.get(entity_type, 'Null')}"
                    
                    # Add GO and pathway annotations
                    csv_candidate += "|Null|Null|Null|Null|Null|Null"
                
                csv_candidate += "\n"
                
                # Verify column count
                column_count = len(csv_candidate.strip().split("|"))
                if column_count != csv_header_column_count:
                    raise Exception(
                        f"Error: csv row has wrong number of columns: {column_count} "
                        f"expected: {csv_header_column_count}\n{csv_candidate}"
                    )
                
                csv_content += csv_candidate
                reference_id += 1

            except Exception as e:
                logging.error(f"Error processing article {other_article}: {str(e)}")
                continue

    except Exception as e:
        logging.error(f"Error processing JSON response: {str(e)}")
        raise e

    return csv_content, reference_id


def get_author_string(author_list: List[str]) -> str:
    if not author_list:
        return "'NA'"
    
    if isinstance(author_list, str):
        # If it's already a string, just clean and return it
        return "'" + author_list.replace("'", "\\'") + "'"
    
    author_list_temp = []
    if isinstance(author_list, list):
        for author in author_list:
            if isinstance(author, dict):
                author_name = author.get("name", "NA")
            else:
                author_name = str(author)
            author_list_temp.append(author_name)
        authors = "'" + ";".join(author_list_temp).replace("'", "\\'") + "'"
    else:
        authors = "'NA'"
    return authors


## create the citation csv (incoming and outgoing citations for all DOIs in the doi_list)
# and return the int value of the next article id (reference_id)
def create_citation_csv(
    doi: str,
    article_meta: pd.DataFrame,
    reference_id_start: int,
    filter_terms: List[str],
    additional_keywords: List[str],
    test_mode: bool,
    bioconcepts: str,
    run_pubtator: bool = True,
) -> int:
    reference_id = reference_id_start
    csv_content = ""
    csv_header = ("reference_id|article_id|article_title|article_epubdate|"
                 "article_authors|article_journal|article_abstract|article_keywords|"
                 "article_disease|article_gene|article_chemical|article_species|article_mutation|"
                 "other_reference_id|other_article_id|other_title|other_epubdate|"
                 "other_authors|other_journal|other_abstract|other_keywords|"
                 "other_disease|other_gene|other_chemical|other_species|other_mutation|"
                 "article_GO_BP|article_GO_CC|article_GO_MF|article_pathway_kegg|"
                 "article_pathway_reactome|article_pathway_wikipathways")
    csv_header_column_count = len(csv_header.split("|"))
    csv_content = csv_header + "\n"
    ## first article
    article_id = article_meta.index[0]
    article_title = article_meta.loc[article_id, "title"].replace("|", ";")
    article_epubdate = article_meta.loc[article_id, "epubdate"].replace("|", ";")
    article_authors = article_meta.loc[article_id, "authors"].replace("|", ";")
    article_journal = article_meta.loc[article_id, "journal"].replace("|", ";")
    article_abstract = article_meta.loc[article_id, "abstract"].replace("|", ";")
    article_annotations = article_meta.loc[article_id, "annotations"]

    ## only add lines, if at least the DOI is relevant with respect to
    # the search-terms
    article_search_for_terms = " ".join([article_title, article_abstract])
    if is_relevant(article_search_for_terms, filter_terms):
        article_keywords = get_relevant_keywords(
            article_search_for_terms, additional_keywords
        )
        csv_content_old = csv_content

        # citations (article is cited by the list of publications)
        citing_articles_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
            "elink.fcgi?dbfrom=pubmed&linkname=pubmed_pubmed_citedin&id="
            + article_id
            + "&tool=my_tool&email=my_email@example.com&retmode=json"
        )
        json_response_citing = request_with_delay(citing_articles_url)
        is_article_first = False
        csv_content, reference_id = update_csv_content_by_json_response(
            json_response_citing,
            csv_content,
            csv_header_column_count,
            reference_id,
            test_mode,
            is_article_first,
            filter_terms,
            additional_keywords,
            bioconcepts,
            article_id,
            article_title,
            "",
            article_epubdate,
            article_authors,
            article_journal,
            article_abstract,
            article_keywords,
            article_annotations,
            run_pubtator,
        )

        # references (article cites the list of references)
        references_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
            "elink.fcgi?dbfrom=pubmed&linkname=pubmed_pubmed_refs&id="
            + article_id
            + "&tool=my_tool&email=my_email@example.com&"
            "retmode=json"
        )
        json_response_references = request_with_delay(references_url)
        is_article_first = True
        csv_content, reference_id = update_csv_content_by_json_response(
            json_response_references,
            csv_content,
            csv_header_column_count,
            reference_id,
            test_mode,
            is_article_first,
            filter_terms,
            additional_keywords,
            bioconcepts,
            article_id,
            article_title,
            "",
            article_epubdate,
            article_authors,
            article_journal,
            article_abstract,
            article_keywords,
            article_annotations,
            run_pubtator,
        )

        if csv_content_old == csv_content:
            ## no changes: at least add the article itself
            other_article = (
                other_title
            ) = other_epubdate = other_abstract = other_annotations = "Null"
            other_keywords = ""
            csv_candidate = (
                "|".join(
                    [
                        str(reference_id),
                        article_id,
                        article_title,
                        article_epubdate,
                        article_authors,
                        article_journal,
                        article_abstract,
                        ",".join(article_keywords),
                        article_annotations,
                        str(other_article),
                        other_title,
                        other_epubdate,
                        other_abstract,
                        ",".join(other_keywords),
                        other_annotations,
                        "Null",
                        "Null",
                        "Null",
                        "Null",
                        "Null",
                        "Null",
                    ]
                )
                + "\n"
            )
            csv_content += csv_candidate
            reference_id += 1

    csv_text = csv_content
    csv_text = csv_text.replace('"', "")

    ## write to file, that can be accessed from neo4j (neo4j is
    # mapped to the neo4j container /var/lib/...)
    f = open("/neo4j/citations.csv", "w")
    f.write(csv_text)
    f.close()

    return reference_id


def run_global_curation(neo4j_manager: Neo4j_Manager) -> None:
    ## run the curation
    logging.info("run global curations")
    ## global curation file
    currate_annoations_json = "/global/curate_annotations.json"
    # open the global json-file and perform the curation
    with open(currate_annoations_json) as json_file:
        curate_data = json.load(json_file)
        for dict_curate_entry in curate_data:
            ## validate structure
            ## merge, rename entities
            if set(
                [
                    "name",
                    "description",
                    "from_keys",
                    "to_keys",
                    "from_values",
                    "to_values",
                    "method",
                ]
            ) == set(curate_data[dict_curate_entry].keys()):
                from_keys = curate_data[dict_curate_entry]["from_keys"]
                from_values = curate_data[dict_curate_entry]["from_values"]
                to_keys = curate_data[dict_curate_entry]["to_keys"]
                to_values = curate_data[dict_curate_entry]["to_values"]
                method = curate_data[dict_curate_entry]["method"]
                ## execute the curation
                if method == "merge":
                    response = neo4j_manager.merge_nodes(
                        from_keys, from_values, to_keys, to_values
                    )
                elif method == "rename":
                    response = neo4j_manager.rename_entity(
                        from_keys, from_values, to_keys, to_values
                    )
                else:
                    logging.info("curation method not known: " + method)
                logging.info(response)

            ## neo4j queries
            if set(["name", "description", "query"]) == set(
                curate_data[dict_curate_entry].keys()
            ):
                neo4j_query = curate_data[dict_curate_entry]["query"]
                neo4j_manager.query(neo4j_query)
    logging.info("DONE running the curations")


def get_global_graph_query() -> str:
    ## create the graph structure that is relevant for the embedding
    return """CALL gds.graph.project('knowledgeGraph', 
    ['Article', 'gene', 'disease', 'chemical', 'cellline', 
    'mutation', 'species', 'pathway_kegg', 
    'pathway_reactome', 'pathway_wikipathways',
    'GO_BP', 'GO_CC', 'GO_MF'], 
    {has_named_entity: {orientation: 'UNDIRECTED'}, 
    citing: {orientation: 'UNDIRECTED'}, 
    kegg_contains_gene: {orientation: 'UNDIRECTED'}, 
    wikipathways_contains_gene: {orientation: 'UNDIRECTED'}, 
    GO_MF_contains_gene: {orientation: 'UNDIRECTED'},
    GO_BP_contains_gene: {orientation: 'UNDIRECTED'},
    GO_CC_contains_gene: {orientation: 'UNDIRECTED'},
    reactome_contains_gene: {orientation: 'UNDIRECTED'}});"""


def get_graph_query(str_entity_1: str = "gene", str_entity_2: str = None) -> str:
    ## create the graph structure that is relevant for the embedding
    ret_value = ""
    if str_entity_2:
        ret_value = (
            f"""CALL gds.graph.project('knowledgeGraph', 
                ['Article', '{str_entity_1}', '{str_entity_2}'], """
                    + """{has_named_entity: {orientation: 'UNDIRECTED'}, 
                citing: {orientation: 'UNDIRECTED'}
                });"""
            )
    else:
        ret_value = (
            f"""CALL gds.graph.project('knowledgeGraph', 
                ['Article', '{str_entity_1}'], """
                    + """{has_named_entity: {orientation: 'UNDIRECTED'}, 
                citing: {orientation: 'UNDIRECTED'}
                });"""
            )

    return ret_value


def get_global_graph_query() -> str:
    ## create the graph structure that is relevant for the embedding
    return """CALL gds.graph.project('knowledgeGraph', 
    ['Article', 'gene', 'disease', 'chemical', 'cellline', 
    'mutation', 'species', 'pathway_kegg', 
    'pathway_reactome', 'pathway_wikipathways',
    'GO_BP', 'GO_CC', 'GO_MF'], 
    {has_named_entity: {orientation: 'UNDIRECTED'}, 
    citing: {orientation: 'UNDIRECTED'}, 
    kegg_contains_gene: {orientation: 'UNDIRECTED'}, 
    wikipathways_contains_gene: {orientation: 'UNDIRECTED'}, 
    GO_MF_contains_gene: {orientation: 'UNDIRECTED'},
    GO_BP_contains_gene: {orientation: 'UNDIRECTED'},
    GO_CC_contains_gene: {orientation: 'UNDIRECTED'},
    reactome_contains_gene: {orientation: 'UNDIRECTED'}});"""


def run_main_loop(
    config_path: str,
    waittime: int = 0,
) -> None:
    ## general config
    config = configparser.ConfigParser()
    config.read(config_path)
    delete_neo4j = config["NEO4J-settings"]["delete_neo4j"].lower() == "true"

    project_name = config["GENERAL-settings"]["project_name"]
    db_hostname_base = config["NEO4J-settings"]["neo4j_hostname"]
    db_hostname = "-".join([db_hostname_base, project_name])
    neo4j_bolt_base = config["NEO4J-settings"]["neo4j_bolt"]
    neo4j_bolt_project = "-".join([neo4j_bolt_base, project_name])
    noe4j_bolt_port = config["NEO4J-settings"]["neo4j_bolt_port"]
    neo4j_bolt = ":".join([neo4j_bolt_project, noe4j_bolt_port])
    neo4j_user = config["NEO4J-settings"]["neo4j_user"]
    neo4j_password = config["NEO4J-settings"]["neo4j_password"]

    filter_terms_raw = config["FILTER-criteria"]["filter_terms"]
    filter_terms = filter_terms_raw.split(",")
    additional_keywords_raw = config["FILTER-criteria"]["additional_keywords"]
    additional_keywords = get_list_from_csv_string(additional_keywords_raw)

    bioconcepts = config["FILTER-criteria"]["bioconcepts"]
    max_integration_age_articles = int(
        config["RUN-settings"]["max_integration_age_articles"]
    )
    max_count_integration_batch = int(
        config["RUN-settings"]["max_count_integration_batch"]
    )
    refresh_old_articles = (
        config["RUN-settings"]["refresh_old_articles"].lower() == "true"
    )
    test_mode = config["RUN-settings"]["test_mode"].lower() == "true"
    run_node_embedding = config["RUN-settings"]["run_node_embedding"].lower() == "true"
    run_pubtator = config["RUN-settings"]["run_pubtator"].lower() == "true"

    all_doi_list = "/input/DOI-list-all.csv"
    path_doi_list = "/input/DOI-list.csv"
    old_doi_list = "/input/DOI-list-old.csv"

    logging.info("--- Settings for NEO4J ---")
    for key in config["NEO4J-settings"]:
        logging.info(key + ": " + config["NEO4J-settings"][key])

    # start
    logging.info(
        "waiting " + str(waittime) + " seconds before trying to connect to "
        "graph on " + db_hostname
    )
    time.sleep(waittime)
    neo4j_manager = Neo4j_Manager(
        neo4j_bolt, neo4j_user, neo4j_password, logging=logging
    )
    if delete_neo4j:
        logging.info("--- clearing NEO4J ---")
        neo4j_manager.clear_graph()
        with open(all_doi_list, "w") as f:
            f.write("DOI,integration_date\n")
        with open(path_doi_list, "w") as f:
            f.write("DOI,integration_date\n")
        with open(old_doi_list, "w") as f:
            f.write("DOI,integration_date\n")

    ## setup the index for the most important entities and properties
    logging.info(
        "Creating index for the most important entities and their "
        "name properties (if they don't exist yet)"
    )
    neo4j_manager.setup_index()
    logging.info("Creating index - DONE")
    
    ## calculate and write the article rank for all articles
    logging.info(
        "Calculate and write the ARTICLE RANK for all articles"
    )
    neo4j_manager.calculate_and_write_article_rank()
    logging.info("calculating ARTICLE RANK - DONE")


    ## refresh old articles based on their age in seconds
    if refresh_old_articles:
        ## delete articles with an old integration_date
        doi_all_df = pd.read_csv(all_doi_list)
        integration_date_list = list(doi_all_df["integration_date"])
        delete_date_list = []
        now = datetime.now()
        for index, date_time in enumerate(integration_date_list):
            date_object = datetime.strptime(date_time, "%Y-%m-%d|%H:%M:%S")
            duration = (now - date_object).total_seconds()
            if duration > max_integration_age_articles:
                delete_date_list.append(index)
            if len(delete_date_list) >= max_count_integration_batch:
                break

        drop_old_rows = doi_all_df.index[delete_date_list]
        doi_all_df.drop(drop_old_rows, inplace=True)
        doi_all_df.to_csv(all_doi_list, index=False)

    ## create the csv file, which is later imported into neo4j
    logging.info("creating the csv")
    reference_id = 0
    doi_df = pd.read_csv(path_doi_list)

    ## get the new (non duplicated) articles
    article_list_complete_pre = list(doi_df["DOI"])
    article_list_complete = []
    for article_ids_pre_int in article_list_complete_pre:
        article_ids_pre_str = str(article_ids_pre_int)
        skip_doi = False
        ## unique ids sorted properly
        if article_ids_pre_str not in article_list_complete:
            with open(all_doi_list, "r") as read_obj:
                # Read all lines in the file one by one
                for line in read_obj:
                    # For each line, check if line contains the string
                    if article_ids_pre_str in line:
                        skip_doi = True
        else:
            skip_doi = True
        if not skip_doi:
            article_list_complete.append(article_ids_pre_str)
    count_DOIs = len(article_list_complete)
    logging.info(
        "SKIPPED duplicated articles: "
        + str(len(article_list_complete_pre) - len(article_list_complete))
    )

    ## run article integration in batches of 100
    for article_list_batch in batch(range(0, len(article_list_complete)), 100):
        # logging.info([article_list[i] for i in list(x)] )
        first_index = list(article_list_batch)[0]
        logging.info("Starting batch with index = " + str(first_index))
        article_ids = [str(article_list_complete[i]) for i in list(article_list_batch)]
        article_meta = get_meta_data(
            article_ids, bioconcepts=bioconcepts, run_pubtator=run_pubtator
        )

        if len(article_ids) > 0 and not article_meta.empty:
            for index, doi in enumerate(article_ids):
                article_id = str(doi)

                logging.info(
                    "current article: "
                    + str(article_id)
                    + ": index/last_index = "
                    + str(index + first_index)
                    + "/"
                    + str(count_DOIs - 1)
                )
                reference_id_after = create_citation_csv(
                    str(doi),
                    article_meta,
                    reference_id,
                    filter_terms,
                    additional_keywords,
                    test_mode,
                    bioconcepts,
                    run_pubtator=run_pubtator,
                )
                reference_id = reference_id_after

                ## connect to neo4j and create the citation graph from the csv
                neo4j_manager.create_citation_graph(bioconcepts)

                logging.info("DONE integrating article " + article_id)

                neo4j_manager.set_node_attribute(
                    node_label="Article",
                    node_attribute="name",
                    node_value=article_id,
                    attribute_name="query",
                    attribute_value="main",
                )

                now = datetime.now()
                integration_date_time = now.strftime("%Y-%m-%d|%H:%M:%S")
                with open(all_doi_list, "a") as f:
                    f.write(article_id + "," + str(integration_date_time) + "\n")
    logging.info("clean up all null nodes")
    neo4j_manager.cleanup_null_nodes()
    logging.info("add age for all articles")
    neo4j_manager.add_age_for_all_articles()
    ## calculate and write the article rank for all articles
    logging.info(
        "calculate and write the ARTICLE RANK for all articles"
    )
    neo4j_manager.calculate_and_write_article_rank()
    logging.info("calculating ARTICLE RANK - DONE")

    logging.info("add chemical information (attributes) for all chemicals")
    neo4j_manager.add_chemical_information()
    logging.info("add disease information (attributes) for all diseases")
    neo4j_manager.add_disease_information()
    logging.info("add species information (attributes) for all species")
    neo4j_manager.add_species_information()
    logging.info("add mygene information (attributes, pathways, ...) for all genes")
    neo4j_manager.add_mygene_information()
    logging.info("run global curation of annotated entities")
    run_global_curation(neo4j_manager=neo4j_manager)

    ## check if new embedding is necessary (based on max_integration_age_articles)
    run_embedding_now = False
    stats_query = """
    MATCH (s:Stats)
    WHERE s.name = 'global_stats'
    RETURN s.last_embedding
    """
    result = neo4j_manager.query(stats_query, log_queries=True)
    # if stats does exist, else
    if len(result) > 0:
        ## take diff timestamps
        start_embedding = result[0].data()["s.last_embedding"]
        stats_update_query = """WITH apoc.date.currentTimestamp() as ts RETURN ts """
        result = neo4j_manager.query(stats_update_query)
        end_embedding = result[0].data()["ts"]
        total_time_passed_embedding = (end_embedding - start_embedding) / 1000
        if total_time_passed_embedding > max_integration_age_articles:
            logging.info(
                "run global embedding after "
                + str(total_time_passed_embedding)
                + " seconds waiting time"
            )
            run_embedding_now = True
        else:
            logging.info(
                "wait for more time to pass for next embedding: time passed so far:  "
                + str(total_time_passed_embedding)
                + " seconds."
            )
    else:
        logging.info("run global embedding for the first time")
        run_embedding_now = True

    ## run embedding if enough time has passed or the embedding was never conducted
    if run_node_embedding and run_embedding_now:
        logging.info("embed disease entities with Articles")
        graph_query_dis = get_graph_query(
            str_entity_1="disease", str_entity_2=None
        )
        neo4j_manager.run_node_embedding(
            graph_query_dis,
            embedding_attribute_128dim="embedding_dis",
            embedding_attribute_2dim_prefix="embedding_2dim_dis",
        )
        logging.info("embed gene entities with Articles")
        graph_query_gen = get_graph_query(
            str_entity_1="gene", str_entity_2=None
        )
        neo4j_manager.run_node_embedding(
            graph_query_gen,
            embedding_attribute_128dim="embedding_gen",
            embedding_attribute_2dim_prefix="embedding_2dim_gen",
        )
        logging.info("embed chemical entities with Articles")
        graph_query_che = get_graph_query(
            str_entity_1="chemical", str_entity_2=None
        )
        neo4j_manager.run_node_embedding(
            graph_query_che,
            embedding_attribute_128dim="embedding_che",
            embedding_attribute_2dim_prefix="embedding_2dim_che",
        )
        logging.info("embed species entities with Articles")
        graph_query_spe = get_graph_query(
            str_entity_1="species", str_entity_2=None
        )
        neo4j_manager.run_node_embedding(
            graph_query_spe,
            embedding_attribute_128dim="embedding_spe",
            embedding_attribute_2dim_prefix="embedding_2dim_spe",
        )
        
        logging.info("ALL: embed all entities together")
        global_graph_query = get_global_graph_query()
        neo4j_manager.run_node_embedding(
            global_graph_query,
            embedding_attribute_128dim="embedding",
            embedding_attribute_2dim_prefix="embedding_global",
        )
        logging.info("embed disease and gene entities with Articles")
        graph_query_dis_gen = get_graph_query(
            str_entity_1="disease", str_entity_2="gene"
        )
        neo4j_manager.run_node_embedding(
            graph_query_dis_gen,
            embedding_attribute_128dim="embedding_dis_gen",
            embedding_attribute_2dim_prefix="embedding_2dim_dis_gen",
        )
        logging.info("embed disease and chemical entities with Articles")
        graph_query_dis_che = get_graph_query(
            str_entity_1="disease", str_entity_2="chemical"
        )
        neo4j_manager.run_node_embedding(
            graph_query_dis_che,
            embedding_attribute_128dim="embedding_dis_che",
            embedding_attribute_2dim_prefix="embedding_2dim_dis_che",
        )
        logging.info("embed disease and species entities with Articles")
        graph_query_dis_spe = get_graph_query(
            str_entity_1="disease", str_entity_2="species"
        )
        neo4j_manager.run_node_embedding(
            graph_query_dis_spe,
            embedding_attribute_128dim="embedding_dis_spe",
            embedding_attribute_2dim_prefix="embedding_2dim_dis_spe",
        )
        logging.info("embed gene and chemical entities with Articles")
        graph_query_gen_che = get_graph_query(
            str_entity_1="gene", str_entity_2="chemical"
        )
        neo4j_manager.run_node_embedding(
            graph_query_gen_che,
            embedding_attribute_128dim="embedding_gen_che",
            embedding_attribute_2dim_prefix="embedding_2dim_gen_che",
        )
        stats_query = """
        MERGE (s:Stats {name: 'global_stats'})
        SET s.name = 'global_stats', s.last_embedding = apoc.date.currentTimestamp()
        RETURN s
        """
        result = neo4j_manager.query(stats_query, log_queries=False)

    # logging.info("cache cytoscape results")
    # neo4j_manager.cache_cytoscape_results(run_node_embedding = run_node_embedding)

    logging.info("DONE with all articles")
    # close neo4j after integrating all csvs
    neo4j_manager.close()


def main() -> None:
    ## start __main__.py
    # Make sure stdout is flushed after each print
    doi_list_path = "/input/DOI-list.csv"
    old_doi_list_path = "/input/DOI-list-old.csv"
    config_path = "/input/config.ini"
    # compare_to_doi_list = "/input/DOI-list-"
    # shutil.copy(doi_list,current_doi_list)

    big_loop_wait_time = 2
    wait_counter_new_integration = 0
    logging.info("########## starting knowledge-graph manager ##########")
    ## wait for neo4j to start
    logging.info("wait for neo4j to start")
    time.sleep(30)
    logging.info(
        "check if the DOI-list has changed (every "
        + str(big_loop_wait_time)
        + " seconds)"
    )
    while True:
        ## first run the query, if it exists
        config = configparser.ConfigParser()
        config.read(config_path)
        search_query = config["FILTER-criteria"]["search_query"]
        delete_neo4j = config["NEO4J-settings"]["delete_neo4j"].lower() == "true"
        max_seconds_check_old_integration = int(
            config["RUN-settings"]["max_seconds_check_old_integration"]
        )
        update_doi_csv_by_query(search_query, doi_list_path)

        # logging.info("check if the DOI-list has changed")
        if os.path.isfile(old_doi_list_path):
            if (
                ((filecmp.cmp(old_doi_list_path, doi_list_path)) == True)
                & (wait_counter_new_integration < max_seconds_check_old_integration)
                & (delete_neo4j == False)
            ):
                # no change -> do nothing
                wait_counter_new_integration += big_loop_wait_time
                big_loop_wait_time += 2
                big_loop_wait_time = min([60, big_loop_wait_time])
                logging.info("waiting for " + str(big_loop_wait_time) + " seconds")
            else:
                ## changes have been made to "DOI-list.csv"
                # -> start creating the csv and import it to graph
                run_main_loop(config_path=config_path, waittime=0)
                shutil.copy(doi_list_path, old_doi_list_path)
                big_loop_wait_time = 2
                wait_counter_new_integration = 0
        else:
            logging.info("old_doi_list is missing")
            ## this means, it is the first run
            # -> start creating the csv and graph
            run_main_loop(config_path=config_path, waittime=10)
            shutil.copy(doi_list_path, old_doi_list_path)
            big_loop_wait_time = 2
        # logging.info("checking again in {waittime} seconds"\
        #   .format(waittime=big_loop_wait_time))
        time.sleep(big_loop_wait_time)


## __main__ function
if __name__ == "__main__":
    main()
