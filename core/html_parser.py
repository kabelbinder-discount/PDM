"""
HTML Parser Module for extracting structured data from HTML tables
"""
from bs4 import BeautifulSoup
import re

class HTMLParser:
    """Class to handle HTML parsing for product descriptions"""
    
    def parse_html_table(self, html_content):
        """Parse HTML tables from product descriptions"""
        soup = BeautifulSoup(html_content, 'html.parser')
        properties = {}
        
        # Find tables in the HTML
        tables = soup.find_all('table')
        
        # If no tables found directly, look for table rows which might be in a div
        if not tables:
            rows = soup.find_all('tr')
            if rows:
                # Create a virtual table
                properties = self._parse_rows(rows)
        else:
            # Process each table
            for table in tables:
                rows = table.find_all('tr')
                table_properties = self._parse_rows(rows)
                properties.update(table_properties)
                
        # Look for properties outside tables (sometimes they appear as key-value pairs in divs or paragraphs)
        property_patterns = [
            r'(\w+):\s*([^<]+)', 
            r'<strong>([^<]+)</strong>\s*([^<]+)'
        ]
        
        for pattern in property_patterns:
            matches = re.findall(pattern, str(soup))
            for match in matches:
                property_name = match[0].strip()
                property_value = match[1].strip()
                if property_name and property_value and property_name not in properties:
                    properties[property_name] = property_value
        
        return properties
    
    def _parse_rows(self, rows):
        """Parse table rows into property key-value pairs"""
        properties = {}
        
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                # First cell is usually property name
                property_name = cells[0].get_text().strip()
                # Second cell is usually property value
                property_value = cells[1].get_text().strip()
                
                # Clean up property name (remove colon if present)
                property_name = property_name.rstrip(':')
                
                # Store property if not empty
                if property_name and property_value:
                    properties[property_name] = property_value
                    
        return properties
    
    def normalize_property(self, property_name, property_value, language='de'):
        """Normalize property names and values"""
        # Map common German property names to standardized names
        de_to_standard = {
            'Farbe': 'color',
            'Material': 'material',
            'Zugkraft': 'tensile_strength',
            'Max. Bündeldurchmesser': 'max_bundle_diameter',
            'Min. Bündeldurchmesser': 'min_bundle_diameter',
            'Temperaturbeständigkeit': 'temperature_resistance',
            'Min. Installationstemperatur': 'min_installation_temperature',
            'Zulassungen': 'certifications',
            'Verpackungseinheit': 'packaging_unit',
            'Isolationsmaterial': 'insulation_material',
            'Werkstoff des Leiters': 'conductor_material',
            'Länge': 'length',
            'Nenngröße': 'nominal_size',
            'Kabelquerschnitt': 'cable_cross_section'
            # Add more mappings as needed
        }
        
        # Normalize property name
        if language == 'de':
            standard_name = de_to_standard.get(property_name, property_name.lower().replace(' ', '_'))
        else:
            # For English, just convert to lowercase with underscores
            standard_name = property_name.lower().replace(' ', '_')
        
        # Process value based on property type
        normalized_value = property_value
        unit = None
        
        # Extract units for numeric properties
        if standard_name in ['tensile_strength', 'max_bundle_diameter', 'min_bundle_diameter', 'length']:
            # Extract number and unit
            match = re.search(r'(\d+(?:[,.]\d+)?)\s*(\w+)?', property_value)
            if match:
                numeric_value = match.group(1).replace(',', '.')
                try:
                    normalized_value = float(numeric_value)
                    if match.group(2):
                        unit = match.group(2)
                except ValueError:
                    # Keep original if conversion fails
                    pass
        
        # Special handling for temperature ranges
        elif standard_name == 'temperature_resistance':
            match = re.search(r'(-?\d+)\s*°C\s*bis\s*(\+?\d+)\s*°C', property_value)
            if match:
                min_temp, max_temp = match.group(1), match.group(2)
                normalized_value = f"{min_temp} to {max_temp}"
                unit = "°C"
        
        return standard_name, normalized_value, unit
    
    def detect_new_properties(self, properties_dict, known_properties):
        """
        Identifies new properties that are not yet defined in the database.
        
        Args:
            properties_dict (dict): Extracted properties from HTML
            known_properties (list): List of known property names
            
        Returns:
            list: List of new property names
        """
        new_properties = []
        for prop_name in properties_dict.keys():
            # Normalize the property name
            std_name, _, _ = self.normalize_property(prop_name, "", "")
            
            # Check if the normalized property is already known
            if std_name not in known_properties:
                new_properties.append(std_name)
                
        return new_properties
