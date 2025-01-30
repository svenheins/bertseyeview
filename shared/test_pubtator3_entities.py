#!/usr/bin/env python3

import requests
import xml.etree.ElementTree as ET
import json
import logging
import time
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def request_with_delay(url: str, delay: float = 0.5) -> Optional[requests.Response]:
    """Make a request with delay to respect rate limits."""
    try:
        time.sleep(delay)
        response = requests.get(url)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        logging.error(f"Request failed: {str(e)}")
        return None

def analyze_xml_structure(xml_text: str) -> Dict:
    """Analyze the structure of XML response and return details about its components."""
    try:
        root = ET.fromstring(xml_text)
        structure = {
            "root_tag": root.tag,
            "root_attributes": dict(root.attrib),
            "children": []
        }
        
        def analyze_element(element, depth=0):
            """Recursively analyze XML element structure."""
            elem_info = {
                "tag": element.tag,
                "attributes": dict(element.attrib),
                "text": element.text.strip() if element.text and element.text.strip() else None,
                "depth": depth,
                "children": []
            }
            
            for child in element:
                elem_info["children"].append(analyze_element(child, depth + 1))
            
            return elem_info
        
        for child in root:
            structure["children"].append(analyze_element(child))
        
        return structure
    except ET.ParseError as e:
        logging.error(f"Failed to parse XML: {str(e)}")
        logging.error(f"Raw XML content: {xml_text[:500]}...")  # Show first 500 chars
        return {"error": str(e), "raw_content": xml_text[:500]}

def test_pubtator_response(pmid: str) -> None:
    """Test PubTator response for a specific PMID."""
    url = f"https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocxml?pmids={pmid}&full=true"
    
    logging.info(f"Testing PubTator response for PMID: {pmid}")
    logging.info(f"URL: {url}")
    
    response = request_with_delay(url)
    if response is None:
        return
    
    try:
        # Get raw response
        raw_content = response.content.decode('utf-8')
        logging.info("Raw response content (first 500 chars):")
        logging.info(raw_content[:500])
        
        # Analyze XML structure
        structure = analyze_xml_structure(raw_content)
        
        # Save results
        output_file = f"pubtator_analysis_{pmid}.json"
        with open(output_file, 'w') as f:
            json.dump(structure, f, indent=2)
        logging.info(f"Analysis saved to {output_file}")
        
        # Try to extract key elements
        try:
            root = ET.fromstring(raw_content)
            
            # Test different XPath queries
            xpath_tests = {
                "title": [
                    './/passage/text',
                    './/passage[.//infon[@key="type"]/text()="title"]//text',
                ],
                "abstract": [
                    './/passage[.//infon[@key="type"]/text()="abstract"]//text',
                    './/passage/text',
                ],
                "authors": [
                    './/infon[@key="authors"]',
                    './/passage//infon[@key="authors"]',
                ],
                "annotations": [
                    './/annotation',
                    './/document//annotation',
                ]
            }
            
            for element, queries in xpath_tests.items():
                logging.info(f"\nTesting XPath queries for {element}:")
                for query in queries:
                    results = root.findall(query)
                    logging.info(f"Query '{query}' found {len(results)} elements")
                    if results:
                        for i, result in enumerate(results[:3]):  # Show first 3 results
                            text = result.text if result.text else "None"
                            attrib = result.attrib if result.attrib else "None"
                            logging.info(f"Result {i}: Text={text[:100]}, Attributes={attrib}")
            
        except ET.ParseError as e:
            logging.error(f"Failed to parse XML for XPath testing: {str(e)}")
    
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")

def extract_entity_annotations(root: ET.Element) -> Dict[str, List[Dict]]:
    """Extract and analyze entity annotations from PubTator XML response."""
    # Map PubTator types to our internal types (case-sensitive)
    type_mapping = {
        'Gene': 'Gene',  # PubTator uses 'Gene'
        'Chemical': 'Chemical',
        'Disease': 'Disease',
        'Species': 'Species',
        'CellLine': 'Cell',  # PubTator uses 'Cell'
        'Variant': 'Mutation'  # PubTator uses 'Mutation'
    }
    
    # Create reverse mapping for lookup
    reverse_mapping = {v: k for k, v in type_mapping.items()}
    
    entities = {entity_type: [] for entity_type in type_mapping.keys()}
    
    try:
        # Find all annotation elements
        annotations = root.findall('.//annotation')
        
        for annotation in annotations:
            # Extract infon elements with their keys
            infons = {}
            for infon in annotation.findall('infon'):
                key = infon.attrib.get('key', '')
                infons[key] = infon.text
            
            # Get the text element
            text = annotation.find('text')
            text_content = text.text if text is not None else None
            
            # Get entity type from type infon
            pubtator_type = infons.get('type')
            
            # Map PubTator type to our internal type using reverse mapping
            entity_type = None
            if pubtator_type in reverse_mapping:
                entity_type = reverse_mapping[pubtator_type]
            
            if entity_type:
                # Only include entities with valid IDs (not "-" or None)
                entity_id = infons.get('identifier')
                if entity_id and entity_id != "-":
                    entity_info = {
                        'id': entity_id,
                        'text': text_content,
                        'type': pubtator_type,
                        'offset': annotation.find('location').attrib if annotation.find('location') is not None else None
                    }
                    entities[entity_type].append(entity_info)
                    
                    # Debug logging for gene entities
                    if entity_type == 'Gene':
                        logging.info(f"Found Gene entity: {json.dumps(entity_info, indent=2)}")
    
    except Exception as e:
        logging.error(f"Error extracting entity annotations: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
    
    return entities

def format_entities_for_neo4j(entities: Dict[str, List[Dict]], pmid: str) -> Dict[str, str]:
    """Format entities for Neo4j CSV import."""
    csv_entries = {}
    
    for entity_type, annotations in entities.items():
        if annotations:
            # Filter out entries without valid IDs or text
            valid_entries = [
                f"{ann['id']};{ann['text']}" 
                for ann in annotations 
                if ann['id'] and ann['id'] != "-" and ann['text']
            ]
            
            if valid_entries:
                # Remove duplicates while preserving order
                unique_entries = list(dict.fromkeys(valid_entries))
                
                # Format for article and other entities
                csv_entries[f"article_{entity_type.lower()}"] = ','.join(unique_entries)
                csv_entries[f"other_{entity_type.lower()}"] = 'Null'  # Set other entities to Null for now
    
    return csv_entries

def test_entity_annotations(pmid: str) -> None:
    """Test entity annotation extraction for a specific PMID."""
    url = f"https://www.ncbi.nlm.nih.gov/research/pubtator3-api/publications/export/biocxml?pmids={pmid}&full=true"
    
    logging.info(f"\nTesting entity annotations for PMID: {pmid}")
    response = request_with_delay(url)
    if response is None:
        return
    
    try:
        # Parse XML response
        root = ET.fromstring(response.content.decode('utf-8'))
        
        # Extract and analyze entity annotations
        entities = extract_entity_annotations(root)
        
        # Log entity statistics
        logging.info("\nEntity Statistics:")
        for entity_type, annotations in entities.items():
            logging.info(f"{entity_type}: {len(annotations)} annotations")
            
            # Show sample annotations
            if annotations:
                logging.info(f"\nSample {entity_type} annotations:")
                for ann in annotations[:3]:  # Show first 3 examples
                    logging.info(json.dumps(ann, indent=2))
        
        # Test Neo4j CSV formatting
        csv_entries = format_entities_for_neo4j(entities, pmid)
        logging.info("\nNeo4j CSV format:")
        for key, value in csv_entries.items():
            logging.info(f"{key}: {value}")
                    
    except ET.ParseError as e:
        logging.error(f"Failed to parse XML: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")

def main():
    # Test with PMIDs known to have entity annotations
    test_pmids = [
        "27940915",  # Known to have gene annotations (AQP4)
        "30356428",  # Known to have chemical annotations
        "34662340",  # Recent publication with mixed annotations
    ]
    
    for pmid in test_pmids:
        test_entity_annotations(pmid)
        logging.info("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()