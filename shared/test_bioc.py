
import pandas as pd
import os
#from bioc import biocxml
import bioc
import requests

def main():

    # Deserialize ``s`` to a BioC collection object.
    #collection = bioc.loads(s)

    bioconcepts_list = ['gene', 'disease', 'chemical', 'species', 'mutation', 'cellline']
    pmc_id = 'PMC5553912,PMC5036217'
    pmc_id = 'PMC5553912'
    url = 'https://www.ncbi.nlm.nih.gov/research/pubtator-api/publications/export/biocxml?pmcids='+str(pmc_id)
    response = requests.get(url)

    with open("temp/pubtator_response.xml", "w") as f:
        f.write(response.text)


    ## target format: Gene:2671;Augmenter of liver regeneration,Gene:2671;ALR,Gene:4780;NRF2,Gene:3170;FOXA2,Gene:3172;HNF4alpha,Gene:1958;EGR-1,Gene:3725;AP1,Gene:7023;AP4,Gene:11692;ALR|Disease:MESH:D005234;steatohepa

    ner_dict = {}
    # Deserialize ``fp`` to a BioC collection object.
    with open('temp/pubtator_response.xml', 'r') as fp:
        collection = bioc.load(fp)
        if len(collection.documents) > 0:
            for document in collection.documents:
                print(document.id)
                if len(document.passages) > 0:
                    for passage in document.passages:
                        if len(passage.annotations) > 0:
                            for annotation in passage.annotations:
                                print(annotation.text)
                                print("annotation: " + str(annotation.infons))
                                ner_type = "Null"
                                ner_identifier = "Null"
                                if 'type' in annotation.infons:
                                    ner_type = annotation.infons['type']
                                if 'identifier' in annotation.infons:
                                    ner_identifier = annotation.infons['identifier']
                                
                                ner_text = ner_type + ":" + ner_identifier + ";" + annotation.text
                                print(ner_text)
                                if ner_type.lower() in ner_dict:
                                    if (ner_identifier != 'Null') and not (ner_identifier in ner_dict[ner_type.lower()]):
                                        ner_dict[ner_type.lower()] +=  "," + ner_text
                                else:
                                    ner_dict[ner_type.lower()] = ner_text
                ner_string = ""
                for index, bioconcept in enumerate(bioconcepts_list):
                    if bioconcept in ner_dict:
                        ner_string += ner_dict[bioconcept]
                    else:
                        ner_string += "Null"
                    if index < len(bioconcepts_list)-1:
                        ner_string += "|"
                print(ner_string)

        print('OK')


if __name__ == '__main__':
    main()