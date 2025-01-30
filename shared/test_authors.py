from datetime import datetime
import logging
import time
import pandas as pd

import requests



def batch(iterable: list, n: int = 1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]

def get_field_or_default_value(source_dict: dict, field: str, default):
    if field in source_dict:
        return source_dict[field]
    else:
        return default


## request something followed by a delay (pubmed allows 3 requests per second)
def request_with_delay(url: str, api_delay: float = 0.0, my_timeout: 
                       float = 20.0) -> requests.Response:
    try:
        response = requests.get(url, timeout=my_timeout)
    except (requests.exceptions.Timeout, 
            requests.exceptions.ConnectionError) as err:
        #raise Exception("Request takes too long")
        return None#'Server taking too long. Try again later'
    else:
        time.sleep(api_delay)
        return response    


## get meta data from a pubmed_id
## meta data = title, epubdate, abstract
def get_meta_data(pubmed_ids_all_batches: list, bioconcepts: str = "none", 
                  batch_size: int = 100) -> pd.DataFrame:
    title = []
    abstract = []
    annotations = []            
    sortpubdate = []
    epubdate = []
    authors =[]
    journal = []
    
    ## pubtator part: retrieve title, abstract and annotations
    pubtator_text = None
    pubtator_meta = {}
    bioconcepts_list = bioconcepts.split(",")

    ## define batches
    for pubmed_ids_batch in batch(range(0, len(pubmed_ids_all_batches)),
            batch_size):
        pubmed_ids = [str(pubmed_ids_all_batches[i]) 
                      for i in list(pubmed_ids_batch)]
        pubmed_ids_join = ",".join([str(pubmed_id_str) 
                                    for pubmed_id_str in pubmed_ids ])
        
        pubtator_url = "https://www.ncbi.nlm.nih.gov/research/pubtator-api/"\
            "publications/export/pubtator?pmids="+pubmed_ids_join+"&concepts"\
            "="+bioconcepts
        successful_request = False
        count_requests = 0
        while (successful_request != True):
            pubtator_response = request_with_delay(pubtator_url)
            count_requests += 1
            if count_requests > 1: 
                logging.info("count_requests = "+str(count_requests))
            if (pubtator_response != None):
                pubtator_text = pubtator_response.content.decode('utf-8')
                
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
                                    if (concept.lower() == bioconcept.lower()):
                                        normalized_annotation = text.split("\t")[5]
                                        concept_annotation = concept+":"\
                                                             +normalized_annotation+";"\
                                                             +annotation
                                        if (annotations_pubtator.endswith(concept_annotation)):
                                            continue
                                        else:
                                            if (concept_annotation+"," in annotations_pubtator):
                                                # skip if the annotation is 
                                                # already part of the annotation 
                                                # (we are only interested in unique annotations)
                                                continue
                                            else:
                                                annotations_pubtator = ",".join([annotations_pubtator,
                                                                                 concept_annotation])
                                    else:
                                        continue
                        ## if there is more than just "Null"
                        if len(annotations_pubtator) > 4:
                            annotations_pubtator = annotations_pubtator[5:]
                        annotations_all = "|".join([annotations_all, 
                                                    annotations_pubtator])
                    if len(annotations_all) > 0:    
                            annotations_all = annotations_all[1:]
                    entry_meta['annotations'] = annotations_all
                    pubtator_meta[pubmed_id_pubtator] = entry_meta
                successful_request = True            
            else:
                logging.info("Request failed: "+ pubtator_url)       
        
        ## eutils part: retrieve sortpubdate, epubdate, authors, journal
        meta_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"\
            "?db=pubmed&id="+pubmed_ids_join+"&retmode=json&tool=my_tool"\
            "&email=my_email@example.com"
        successful_request = False
        count_requests = 0
        while (successful_request != True):
            r_meta = request_with_delay(meta_url)
            count_requests += 1
            if count_requests > 1: 
                logging.info("count_requests = "+str(count_requests))
            if (r_meta != None):
                if 'result' in r_meta.json():
                    for pubmed_id in pubmed_ids:
                        if pubmed_id in r_meta.json()['result']:
                            if pubmed_id in pubtator_meta:
                                title.append(pubtator_meta[pubmed_id]['title'])
                                abstract.append(pubtator_meta[pubmed_id]['abstract'])
                                annotations.append(pubtator_meta[pubmed_id]['annotations'])
                            else:
                                title_from_eutil = get_field_or_default_value(
                                    r_meta.json()['result'][pubmed_id], 
                                    'title', default="NA")
                                title.append(title_from_eutil)
                                abstract.append("NA")
                                bioconcepts_list = bioconcepts.split(",")
                                annotations_all = ""
                                for bioconcept in bioconcepts_list:
                                    if len(annotations_all) > 0:
                                        annotations_all = "|".join([annotations_all, "Null"])
                                    else:
                                        annotations_all = "Null"
                                
                                annotations.append(annotations_all)

                            sortpubdate_raw = get_field_or_default_value(
                                r_meta.json()['result'][pubmed_id], 
                                'sortpubdate', default="NA")
                            ## transform to iso format
                            sortpubdate_processed = sortpubdate_raw.split(' ')[0].replace('/','-')
                            sortpubdate.append( sortpubdate_processed )
                            epubdate_raw = get_field_or_default_value(
                                r_meta.json()['result'][pubmed_id], 
                                'epubdate', default="NA")
                            ## epubdate and sortpubdate are well defined / 
                            # structured iso formats, but the pubdate is 
                            # quite arbitrary, this is why the pubdate_raw is 
                            # preprocessed and parsed quite attentive finally:
                            # if all fails, we fall back to the sortpubdate
                            if (epubdate_raw == "NA" or epubdate_raw == ""):
                                pubdate_raw = get_field_or_default_value(
                                    r_meta.json()['result'][pubmed_id], 
                                    'pubdate', default="NA")
                                pubdate_processed = preprocess_date(pubdate_raw)
                                try:
                                    pubdate = datetime.strptime(
                                        pubdate_processed, 
                                        '%Y %b %d').strftime('%Y-%m-%d')
                                except ValueError as e:
                                    logging.info(pubdate_raw)
                                    logging.info(pubdate_processed)
                                    logging.info(e)
                                    logging.info("take the sortpubdate_processed " \
                                        "version: "+sortpubdate_processed)
                                    epubdate_raw = datetime.strptime(
                                        sortpubdate_processed, 
                                        '%Y-%m-%d').strftime('%Y %b %d')
                                    logging.info("resulting epubdate_raw: "\
                                          +epubdate_raw)
                            epubdate_iso = pubdate if (epubdate_raw == "NA" 
                                                       or epubdate_raw == "") \
                                           else datetime.strptime(
                                               epubdate_raw, '%Y %b %d').strftime('%Y-%m-%d')
                            epubdate.append(epubdate_iso )
                            authors_list = (get_field_or_default_value(
                                r_meta.json()['result'][pubmed_id], 'authors', 
                                default="NA"))
                            
                            authors_string = "NA"
                            if authors_list != "NA":
                                authors_list_name = [ author["name"] for author in authors_list] 
                                authors_string = "; ".join(authors_list_name)
                                    
                            authors.append(authors_string)

                            journal.append(get_field_or_default_value(
                                r_meta.json()['result'][pubmed_id], 
                                'fulljournalname', default="NA"))
                successful_request = True            
            else:
                logging.info("Request failed: "+ meta_url)   

    df_content = {'title': title, 'abstract': abstract, 
                  'annotations': annotations, 'sortpubdate': sortpubdate, 
                  'epubdate': epubdate, 'authors': authors, 'journal':journal}

    return_df = pd.DataFrame(data=df_content, index=pubmed_ids_all_batches)
    return return_df


def main():
    pubmed_ids_all_batches = [ "35492906" ]
    bioconcepts = "disease"
    print(get_meta_data(pubmed_ids_all_batches, bioconcepts))



## __main__ function
if __name__ == '__main__':
    main()