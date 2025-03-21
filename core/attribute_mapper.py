"""
Attribute Mapper Module for mapping different attribute names
"""

class AttributeMapper:
    """Class for mapping different attribute names to standardized names"""
    
    def __init__(self, db_manager):
        """
        Initialize the Attribute Mapper.
        
        Args:
            db_manager: Instance of DatabaseManager
        """
        self.db_manager = db_manager
        self.mappings = {}  # Format: {(original_name, language): standard_name}
        self.load_mappings()
        
    def load_mappings(self):
        """Load existing attribute mappings from the database"""
        self.mappings = {}
        conn = self.db_manager.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT original_name, standard_name, language FROM PropertyMappings')
        rows = cursor.fetchall()
        
        for original_name, standard_name, language in rows:
            self.mappings[(original_name, language)] = standard_name
            
        self.db_manager.close()
        
    def add_mapping(self, original_name, standard_name, language):
        """
        Create a new mapping between original and standard names.
        
        Args:
            original_name (str): Original attribute name
            standard_name (str): Standardized name
            language (str): Language ('de' or 'en')
            
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.db_manager.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                'INSERT OR REPLACE INTO PropertyMappings (original_name, standard_name, language, confidence) VALUES (?, ?, ?, ?)',
                (original_name, standard_name, language, 1.0)  # Manual mappings have confidence 1.0
            )
            conn.commit()
            self.mappings[(original_name, language)] = standard_name
            return True
        except Exception as e:
            print(f"Error saving mapping: {str(e)}")
            return False
        finally:
            self.db_manager.close()
            
    def get_standard_name(self, original_name, language):
        """
        Get the standardized name for an original attribute name.
        
        Args:
            original_name (str): Original attribute name
            language (str): Language ('de' or 'en')
            
        Returns:
            str: Standardized name or original_name if no mapping exists
        """
        return self.mappings.get((original_name, language), original_name)
    
    def suggest_mappings(self, property_names):
        """
        Suggest possible mappings for unknown attribute names.
        
        Args:
            property_names (list): List of property names
            
        Returns:
            dict: Dictionary with suggestions {original_name: [(standard_name, confidence), ...]}
        """
        suggestions = {}
        
        # Load known standard names
        conn = self.db_manager.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT name_de, name_en FROM PropertyDefinitions')
        standard_names = cursor.fetchall()
        self.db_manager.close()
        
        # Flatten standard_names list
        all_standard_names = [name for pair in standard_names for name in pair if name]
        
        for prop_name in property_names:
            if not any(prop_name == orig for (orig, _) in self.mappings.keys()):
                # Calculate similarity to known standard names
                prop_suggestions = []
                
                for std_name in all_standard_names:
                    # Simple similarity calculation (can be replaced with more complex algorithms)
                    similarity = self._calculate_similarity(prop_name, std_name)
                    if similarity > 0.6:  # Threshold for suggestions
                        prop_suggestions.append((std_name, similarity))
                
                # Sort by similarity
                prop_suggestions.sort(key=lambda x: x[1], reverse=True)
                suggestions[prop_name] = prop_suggestions[:3]  # Up to 3 suggestions
                
        return suggestions
    
    def _calculate_similarity(self, str1, str2):
        """
        Calculate similarity between two strings (simple implementation).
        
        Args:
            str1 (str): First string
            str2 (str): Second string
            
        Returns:
            float: Similarity value between 0 and 1
        """
        # This implementation is simplified and can be replaced with better algorithms
        str1_lower = str1.lower()
        str2_lower = str2.lower()
        
        # Simple containment check
        if str1_lower in str2_lower or str2_lower in str1_lower:
            return 0.8
            
        # Count common characters
        common_chars = set(str1_lower) & set(str2_lower)
        return len(common_chars) / max(len(set(str1_lower)), len(set(str2_lower)))
