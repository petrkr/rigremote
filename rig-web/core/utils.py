"""Utility functions for RIG Remote Control."""

import re
import unicodedata
from typing import List


def generate_radio_id(name: str, existing_ids: List[str] = None) -> str:
    """Generate a unique radio ID from human-readable name.
    
    Args:
        name: Human-readable radio name (e.g., "My FT-991A")
        existing_ids: List of existing IDs to avoid conflicts
        
    Returns:
        Unique ID suitable for internal use (e.g., "my_ft991a")
    """
    if existing_ids is None:
        existing_ids = []
    
    # Normalize unicode characters
    normalized = unicodedata.normalize('NFKD', name)
    
    # Convert to ASCII, lowercase, and replace spaces/special chars with underscores
    ascii_name = normalized.encode('ascii', 'ignore').decode('ascii')
    clean_name = re.sub(r'[^a-zA-Z0-9\s\-_]', '', ascii_name)
    id_base = re.sub(r'[\s\-]+', '_', clean_name.strip()).lower()
    
    # Remove multiple underscores
    id_base = re.sub(r'_+', '_', id_base).strip('_')
    
    # Ensure it's not empty
    if not id_base:
        id_base = "radio"
    
    # Ensure it starts with a letter (required for some systems)
    if id_base[0].isdigit():
        id_base = f"radio_{id_base}"
    
    # Make it unique by adding number suffix if needed
    radio_id = id_base
    counter = 1
    while radio_id in existing_ids:
        radio_id = f"{id_base}_{counter}"
        counter += 1
    
    return radio_id


def generate_plugin_id(name: str, existing_ids: List[str] = None) -> str:
    """Generate a unique plugin ID from human-readable name."""
    return generate_radio_id(name, existing_ids)  # Same logic