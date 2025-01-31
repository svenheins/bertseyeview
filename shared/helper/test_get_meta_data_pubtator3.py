#!/usr/bin/env python3

import logging
import sys
import os
import pandas as pd
from typing import List

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_pubtator.log')
    ]
)

def batch(iterable: list, n: int = 1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx : min(ndx + n, l)]

## get meta data from a pubmed_id
## meta data = title, epubdate, abstract
def get_meta_data(
    pubmed_ids_all_batches: list,
    bioconcepts: str = "none",
    batch_size: int = 100,
    run_pubtator: bool = True,
) -> pd.DataFrame:
    title_list = []
    abstract_list = []
    annotations_list = []
    sortpubdate_list = []
    epubdate_list = []
    authors_list = []
    journal_list = []
    pmc_id_list = []

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

                    pubtator_text_split = pubtator_text.split("\n\n")[:-1]
                    for entry in pubtator_text_split:
                        concept_annotation = ""
                        annotations_all = ""
                        entry_meta = {}
                        for index, text in enumerate(entry.split("\n")):
                            if index > 1:
                                break
                            else:
                                if index == 0:
                                    if len(text.split("|")) == 3:
                                        pubmed_id_pubtator = text.split("|")[0]
                                        title_pubtator = text.split("|")[2]
                                    else:
                                        logging.info("error: not the pubtator format")
                                        logging.info(text)
                                else:
                                    if len(text.split("|")) == 3:
                                        abstract_pubtator = text.split("|")[2]
                                    else:
                                        logging.info("error: not the pubtator format")
                                        logging.info(text)
                        entry_meta["title"] = title_pubtator
                        entry_meta["abstract"] = abstract_pubtator

                        for bioconcept in bioconcepts_list:
                            annotations_pubtator = "Null"
                            for index, text in enumerate(entry.split("\n")):
                                if index <= 1:
                                    ## title and abstract -> skip
                                    pass

                                else:
                                    if len(text.split("\t")) > 3:
                                        annotation = text.split("\t")[3]
                                        concept = text.split("\t")[4]
                                        ## only treat the current bioconcept
                                        # (we need to process the concepts in
                                        # correct order)
                                        if concept.lower() == bioconcept.lower():
                                            normalized_annotation = text.split("\t")[5]
                                            concept_annotation = (
                                                concept
                                                + ":"
                                                + normalized_annotation
                                                + ";"
                                                + annotation
                                            )
                                            if annotations_pubtator.endswith(
                                                concept_annotation
                                            ):
                                                continue
                                            else:
                                                if (
                                                    concept_annotation + ","
                                                    in annotations_pubtator
                                                ):
                                                    # skip if the annotation is
                                                    # already part of the annotation
                                                    # (we are only interested in unique annotations)
                                                    continue
                                                else:
                                                    annotations_pubtator = ",".join(
                                                        [
                                                            annotations_pubtator,
                                                            concept_annotation,
                                                        ]
                                                    )
                                        else:
                                            continue
                            ## if there is more than just "Null"
                            if len(annotations_pubtator) > 4:
                                annotations_pubtator = annotations_pubtator[5:]
                            annotations_all = "|".join(
                                [annotations_all, annotations_pubtator]
                            )
                        if len(annotations_all) > 0:
                            annotations_all = annotations_all[1:]
                        entry_meta["annotations"] = annotations_all
                        pubtator_meta[pubmed_id_pubtator] = entry_meta
                    successful_request = True
                else:
                    logging.info("Request failed: " + pubtator_url)

        ## eutils part: retrieve sortpubdate, epubdate, authors, journal
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
                                                                                    ner_text = (
                                                                                        ner_type
                                                                                        + ":"
                                                                                        + ner_identifier
                                                                                        + ";"
                                                                                        + annotation.text
                                                                                    )
                                                                                    if (
                                                                                        ner_type.lower()
                                                                                        in ner_dict
                                                                                    ):
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
        "journal": journal_list,
        "pmc_id": pmc_id_list,
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




def test_get_meta_data():
    # Test PMIDs
    test_pmids = [
        "36116464",
        "28980624",
        "28700839"
    ]
    
    logging.info("Starting metadata retrieval test with PMIDs: %s", test_pmids)
    
    try:
        # Call get_meta_data with debug settings
        result_df = get_meta_data(
            pubmed_ids_all_batches=batch(test_pmids, 1),
            bioconcepts="gene,disease,chemical,species,mutation,cellline",
            batch_size=1,  # Process one at a time for easier debugging
            run_pubtator=True
        )
        
        # Print detailed results for each PMID
        for pmid in test_pmids:
            logging.info("\n" + "="*80)
            logging.info(f"Results for PMID {pmid}:")
            if pmid in result_df.index:
                row = result_df.loc[pmid]
                logging.info(f"Title: {row['title']}")
                logging.info(f"Abstract: {row['abstract'][:200]}...")  # Show first 200 chars
                logging.info(f"Publication Date: {row['sortpubdate']}")
                logging.info(f"Authors: {row['authors']}")
                logging.info(f"Journal: {row['journal']}")
                logging.info("\nAnnotations:")
                annotations = row['annotations'].split('|')
                for i, concept in enumerate(['Gene', 'Disease', 'Chemical', 'Species', 'Mutation', 'CellLine']):
                    if i < len(annotations):
                        logging.info(f"{concept}: {annotations[i]}")
            else:
                logging.warning(f"No data found for PMID {pmid}")
            logging.info("="*80 + "\n")
        
        # Save results to CSV for further analysis
        result_df.to_csv('pubtator_test_results.csv')
        logging.info("Results saved to pubtator_test_results.csv")
        
    except Exception as e:
        logging.error("Error occurred during testing: %s", str(e), exc_info=True)

if __name__ == "__main__":
    test_get_meta_data()