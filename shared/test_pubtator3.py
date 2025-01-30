
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

def main():
    # Test with a few PMIDs
    test_pmids = [
        "25644544",  # Example PMID
        "30356428",  # Another example
        "34662340",  # Recent publication
    ]
    
    for pmid in test_pmids:
        test_pubtator_response(pmid)
        logging.info("\n" + "="*80 + "\n")  # Separator between tests

if __name__ == "__main__":
    main()