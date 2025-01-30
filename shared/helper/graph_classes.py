import json

class Node:    
    color = "#CCCCCC"
    size = "100%"
    opacity ="1.0"
    label = "label"
    
    def __init__(self, node_class: str, node_id: int, node_name: str, \
                  node_properties: dict) -> None:
            self.class_name = node_class
            self.id = node_id
            self.name = node_name
            self.label = node_name
            if "label" in node_properties:
                self.label = node_properties['label']
            self.properties = node_properties
    
    @property
    def tooltip(self):
        dict_tooltip = {}
        for property in self.properties:
            dict_tooltip[property] = self.properties[property]
        return dict_tooltip

    
class Node_Factory:
    def __init__(self, json_path):
        self.json_path = json_path

    def get_instance(self, node_class: str, node_id: int, node_name: str, \
                  node_properties: dict) -> any:
        
        is_welldefined_class = False
        ## read attribues for the cytoscape graph
        cytoscape_attributes_filename = self.json_path
        with open(cytoscape_attributes_filename) as cytoscape_attributes_file:
            cytoscape_attributes = json.load(cytoscape_attributes_file)
            if node_class in cytoscape_attributes:
                color = cytoscape_attributes[node_class]['color']
                size = cytoscape_attributes[node_class]['size']
                opacity = cytoscape_attributes[node_class]['opacity']
                is_welldefined_class = True

        node = None
        if node_class == "Article":
            node = Article(node_class = node_class, node_id = node_id, node_name= node_name, \
                           node_properties = node_properties)
        elif node_class == "drug":
            node = Drug(node_class = node_class, node_id = node_id, node_name= node_name, \
                           node_properties = node_properties)
        elif node_class == "gene":
            node = Gene(node_class = node_class, node_id = node_id, node_name= node_name, \
                           node_properties = node_properties)
        elif node_class == "chemical":
            node = Chemical(node_class = node_class, node_id = node_id, node_name= node_name, \
                           node_properties = node_properties)     
        elif node_class == "disease":
            node = Disease(node_class = node_class, node_id = node_id, node_name= node_name, \
                           node_properties = node_properties)
        elif node_class == "species":
            node = Species(node_class = node_class, node_id = node_id, node_name= node_name, \
                           node_properties = node_properties)
        elif node_class == "pathway_kegg":
            node = KEGG_Pathway(node_class = node_class, node_id = node_id, node_name= node_name, \
                           node_properties = node_properties)
        elif ( node_class == "GO_MF" or node_class == "GO_CC" or node_class == "GO_BP" ):
            node = GO_Term(node_class = node_class, node_id = node_id, node_name= node_name, \
                           node_properties = node_properties)                        
        else:
            node = Node(node_class = node_class, node_id = node_id, node_name= node_name, \
                           node_properties = node_properties)
        
        if is_welldefined_class:
            node.color = color
            node.size = size
            node.opacity = opacity
            
        return node

class Article(Node):
    def __init__(self, node_class: str, node_id: int, node_name: str, \
                  node_properties: dict) -> None:
        super().__init__(node_class = node_class, node_id = node_id, \
                  node_properties = node_properties, node_name= node_name)

    @property
    def tooltip(self):
        dict_tooltip = {}
        
        if "name" in self.properties:
            pubmed_id = self.properties["name"]
            dict_tooltip["Name"] = pubmed_id
            dict_tooltip["Pubmed"] = f'''<a href="https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/" target="_blank" rel="noopener noreferrer">{pubmed_id}</a>'''
            dict_tooltip["Pubtator"] = f'''<a href="https://www.ncbi.nlm.nih.gov/research/pubtator/?view=docsum&query={pubmed_id}" target="_blank" rel="noopener noreferrer">{pubmed_id}</a>'''
        if "b_title" in self.properties:
            dict_tooltip["Title"] = self.properties["b_title"]
        
        if "epubdate" in self.properties:
            dict_tooltip["Publication date"] = self.properties["epubdate"]
        if "journal" in self.properties:
            dict_tooltip["Journal"] = self.properties["journal"]

        return dict_tooltip
    
class Drug(Node):
    def __init__(self, node_class: str, node_id: int, node_name: str, \
                  node_properties: dict) -> None:
        super().__init__(node_class = node_class, node_id = node_id, node_name= node_name, \
                  node_properties = node_properties)

class Gene(Node):
    def __init__(self, node_class: str, node_id: int, node_name: str, \
                  node_properties: dict) -> None:
        super().__init__(node_class = node_class, node_id = node_id, node_name= node_name, \
                  node_properties = node_properties)
        if 'symbol' in self.properties:
            self.label = self.properties['symbol']
    
    @property
    def tooltip(self):
        dict_tooltip = {}
        
        if "entrezgene" in self.properties:
            entrezgene = self.properties["entrezgene"]
            dict_tooltip["Name"] = entrezgene
            dict_tooltip["NCBI Entrez Gene"] = f'''<a href="https://www.ncbi.nlm.nih.gov/gene/{entrezgene}" target="_blank" rel="noopener noreferrer">{entrezgene}</a>'''
        if "symbol" in self.properties:
            dict_tooltip["Symbol"] = self.properties["symbol"]
        if "taxid" in self.properties:
            dict_tooltip["Taxonomy ID"] = self.properties["taxid"]
        if "type_of_gene" in self.properties:
            dict_tooltip["Type of gene"] = self.properties["type_of_gene"]

        return dict_tooltip

class Chemical(Node):
    def __init__(self, node_class: str, node_id: int, node_name: str, \
                  node_properties: dict) -> None:
        super().__init__(node_class = node_class, node_id = node_id, node_name= node_name, \
                  node_properties = node_properties)
    
    @property
    def tooltip(self):
        dict_tooltip = {}
        
        if "name" in self.properties:
            chemical_mesh = self.properties["name"].split(":")[-1]
            if len(chemical_mesh) > 0:
                dict_tooltip["Chemical MESH"] = chemical_mesh
                dict_tooltip["NIH MESH"] = f'''<a href="https://meshb.nlm.nih.gov/record/ui?ui={chemical_mesh}" target="_blank" rel="noopener noreferrer">{chemical_mesh}</a>'''
        if "label" in self.properties:
            dict_tooltip["label"] = self.properties["label"]

        return dict_tooltip

class Disease(Node):
    def __init__(self, node_class: str, node_id: int, node_name: str, \
                  node_properties: dict) -> None:
        super().__init__(node_class = node_class, node_id = node_id, node_name= node_name, \
                  node_properties = node_properties)
    
    @property
    def tooltip(self):
        dict_tooltip = {}
        
        if "name" in self.properties:
            disease_mesh = self.properties["name"].split(":")[-1]
            if len(disease_mesh) > 0:
                dict_tooltip["Disease MESH"] = disease_mesh
                dict_tooltip["CTD MESH"] = f'''<a href="http://ctdbase.org/detail.go?type=disease&acc=MESH:{disease_mesh}" target="_blank" rel="noopener noreferrer">{disease_mesh}</a>'''
        if "label" in self.properties:
            dict_tooltip["label"] = self.properties["label"]


        return dict_tooltip
    
class Species(Node):
    def __init__(self, node_class: str, node_id: int, node_name: str, \
                  node_properties: dict) -> None:
        super().__init__(node_class = node_class, node_id = node_id, node_name= node_name, \
                  node_properties = node_properties)
    
    @property
    def tooltip(self):
        dict_tooltip = {}
        
        if "name" in self.properties:
            organism_id = self.properties["name"].split(":")[-1]
            if len(organism_id) > 0:
                dict_tooltip["Taxonomy entry"] = f'''<a href="https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={organism_id}&lvl=0" target="_blank" rel="noopener noreferrer">{organism_id}</a>'''
        if "label" in self.properties:
            dict_tooltip["label"] = self.properties["label"]
        if "common_name" in self.properties:
            dict_tooltip["common_name"] = self.properties["common_name"]
        if "current_name" in self.properties:
            dict_tooltip["current_name"] = self.properties["current_name"]
        if "blast_name" in self.properties:
            dict_tooltip["blast_name"] = self.properties["blast_name"]

        return dict_tooltip

class KEGG_Pathway(Node):
    def __init__(self, node_class: str, node_id: int, node_name: str, \
                  node_properties: dict) -> None:
        super().__init__(node_class = node_class, node_id = node_id, node_name= node_name, \
                  node_properties = node_properties)
        ## shorten the label for Kegg pathways
        ## -> cut the last part, which is redundant
        if " - " in self.label:
            kegg_label_list = self.label.split(" - ")
            if len(kegg_label_list) > 2:
                self.label = " ".join(kegg_label_list[0:-1])
            else:
                self.label = kegg_label_list[0]
    
    @property
    def tooltip(self):
        dict_tooltip = {}

        if "label" in self.properties:
            dict_tooltip["label"] = self.properties["label"]
        if "name" in self.properties:
            kegg_pathway = self.properties["name"].split(":")[-1]
            if len(kegg_pathway) > 0:
                dict_tooltip["KEGG Pathway"] = kegg_pathway
                dict_tooltip["KEGG entry"] = f'''<a href="https://www.genome.jp/entry/{kegg_pathway}" target="_blank" rel="noopener noreferrer">{kegg_pathway}</a>'''
                dict_tooltip["KEGG Pathway Graph"] = f'''<a href="https://www.genome.jp/pathway/{kegg_pathway}" target="_blank" rel="noopener noreferrer">{kegg_pathway}</a>'''

        return dict_tooltip

class GO_Term(Node):
    def __init__(self, node_class: str, node_id: int, node_name: str, \
                  node_properties: dict) -> None:
        super().__init__(node_class = node_class, node_id = node_id, node_name= node_name, \
                  node_properties = node_properties)
    
    @property
    def tooltip(self):
        dict_tooltip = {}
        for property in self.properties:
            dict_tooltip[property] = self.properties[property]
        if "name" in self.properties:
            go_name = self.properties["name"]
            if len(go_name) > 0:
                dict_tooltip["GO entry"] = f'''<a href="https://www.ebi.ac.uk/QuickGO/term/{go_name}" target="_blank" rel="noopener noreferrer">{go_name}</a>'''
        return dict_tooltip


class Edge:    
     def __init__(self, edge_class: str, edge_id: int) -> None:
            self.edge_class = edge_class
            self.edge_id = edge_id