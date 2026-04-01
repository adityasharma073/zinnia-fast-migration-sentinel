"""
Document Reconciliation Pipeline - Data Extraction Microservice

A production-ready microservice for extracting and normalizing data from PDF and XML documents.
Uses Docling for PDF parsing with structural preservation and xmltodict for XML parsing.

Author: Senior Data Engineer
Purpose: Extract, parse, and normalize document content into unified JSON format
"""

import json
import logging
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Optional, Union

# Suppress deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

try:
    import xmltodict
except ImportError:
    xmltodict = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# Configure logging for production environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Custom exception for PDF extraction failures."""
    pass


class XMLExtractionError(Exception):
    """Custom exception for XML extraction failures."""
    pass


class DocumentExtractor:
    """
    Handles extraction and normalization of PDF and XML documents.
    
    This class provides methods to:
    - Parse PDFs using Docling with structural preservation
    - Parse XML files into Python dictionaries
    - Combine both extractions into unified JSON output
    """
    
    def __init__(self):
        """Initialize the DocumentExtractor with PDF and XML parsers."""
        logger.info("DocumentExtractor initialized successfully")
    
    def extract_pdf(self, pdf_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Extract content from a PDF file using PyMuPDF (fitz).
        
        Extracts text content and basic metadata from PDF files without requiring
        external model downloads or network access.
        
        Args:
            pdf_path: Path to the PDF file (string or Path object)
            
        Returns:
            Dictionary containing:
            - 'status': 'success' or 'error'
            - 'content': Extracted text content
            - 'metadata': Document metadata (page count, etc.)
            - 'error': Error message if extraction failed
            
        Raises:
            PDFExtractionError: If PDF parsing fails
        """
        pdf_path = Path(pdf_path)
        
        # Validate file existence
        if not pdf_path.exists():
            error_msg = f"PDF file not found: {pdf_path}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'file_path': str(pdf_path)
            }
        
        # Validate file extension
        if pdf_path.suffix.lower() != '.pdf':
            error_msg = f"Invalid file format. Expected .pdf, got {pdf_path.suffix}"
            logger.warning(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'file_path': str(pdf_path)
            }
        
        # Check if PyMuPDF is available
        if fitz is None:
            error_msg = "PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF"
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'file_path': str(pdf_path)
            }
        
        try:
            logger.info(f"Starting PDF extraction from: {pdf_path}")
            
            # Open PDF with PyMuPDF
            pdf_doc = fitz.open(str(pdf_path))
            
            # Extract text from all pages
            content_parts = []
            for page_num in range(len(pdf_doc)):
                page = pdf_doc[page_num]
                text = page.get_text()
                if text.strip():
                    content_parts.append(f"--- Page {page_num + 1} ---\n{text}")
            
            content = "\n\n".join(content_parts)
            
            # Extract metadata
            metadata = {
                'page_count': len(pdf_doc),
                'source_file': str(pdf_path),
                'extraction_method': 'PyMuPDF'
            }
            
            pdf_doc.close()
            
            logger.info(f"Successfully extracted PDF: {pdf_path} ({metadata['page_count']} pages)")
            
            return {
                'status': 'success',
                'content': content,
                'metadata': metadata,
                'file_path': str(pdf_path)
            }
        
        except Exception as e:
            error_msg = f"Unexpected error during PDF extraction: {type(e).__name__} - {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'file_path': str(pdf_path)
            }
    
    def extract_xml(self, xml_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Extract and parse XML file into a Python dictionary.
        
        Uses xmltodict for clean dictionary conversion if available,
        falls back to ElementTree for robust parsing.
        
        Args:
            xml_path: Path to the XML file (string or Path object)
            
        Returns:
            Dictionary containing:
            - 'status': 'success' or 'error'
            - 'data': Parsed XML as dictionary
            - 'metadata': File metadata
            - 'error': Error message if parsing failed
            
        Raises:
            XMLExtractionError: If XML parsing fails
        """
        xml_path = Path(xml_path)
        
        # Validate file existence
        if not xml_path.exists():
            error_msg = f"XML file not found: {xml_path}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'file_path': str(xml_path)
            }
        
        # Validate file extension
        if xml_path.suffix.lower() not in ['.xml', '.xsd']:
            error_msg = f"Invalid file format. Expected .xml or .xsd, got {xml_path.suffix}"
            logger.warning(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'file_path': str(xml_path)
            }
        
        try:
            logger.info(f"Starting XML extraction from: {xml_path}")
            
            with open(xml_path, 'r', encoding='utf-8') as xml_file:
                xml_content = xml_file.read()
            
            # Try xmltodict first for cleaner output
            if xmltodict:
                parsed_data = xmltodict.parse(xml_content)
                logger.info(f"Successfully parsed XML using xmltodict: {xml_path}")
            else:
                # Fallback to ElementTree
                root = ET.fromstring(xml_content)
                parsed_data = self._element_tree_to_dict(root)
                logger.info(f"Successfully parsed XML using ElementTree: {xml_path}")
            
            metadata = {
                'file_size_bytes': xml_path.stat().st_size,
                'source_file': str(xml_path),
                'encoding': 'utf-8'
            }
            
            return {
                'status': 'success',
                'data': parsed_data,
                'metadata': metadata,
                'file_path': str(xml_path)
            }
        
        except ET.ParseError as e:
            error_msg = f"XML parsing error: Malformed XML - {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'file_path': str(xml_path)
            }
        
        except UnicodeDecodeError as e:
            error_msg = f"XML encoding error: Unable to decode file - {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'file_path': str(xml_path)
            }
        
        except Exception as e:
            error_msg = f"Unexpected error during XML extraction: {type(e).__name__} - {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'file_path': str(xml_path)
            }
    
    @staticmethod
    def _element_tree_to_dict(element: ET.Element) -> Dict[str, Any]:
        """
        Convert ElementTree element to dictionary recursively.
        
        Args:
            element: ElementTree element to convert
            
        Returns:
            Dictionary representation of the XML element
        """
        result = {}
        
        # Add element attributes
        if element.attrib:
            result['@attributes'] = element.attrib
        
        # Process child elements
        children = {}
        for child in element:
            child_data = DocumentExtractor._element_tree_to_dict(child)
            if child.tag in children:
                # Handle multiple children with same tag
                if not isinstance(children[child.tag], list):
                    children[child.tag] = [children[child.tag]]
                children[child.tag].append(child_data)
            else:
                children[child.tag] = child_data
        
        result.update(children)
        
        # Add element text if present
        if element.text and element.text.strip():
            if children:
                result['#text'] = element.text.strip()
            else:
                return element.text.strip()
        
        return result if result else None


def extract_and_normalize(
    pdf_path: Union[str, Path],
    xml_path: Union[str, Path]
) -> Dict[str, Any]:
    """
    Main wrapper function for document reconciliation pipeline.
    
    Extracts content from both PDF and XML files, then combines them into
    a single unified JSON object for downstream processing.
    
    Args:
        pdf_path: Path to the PDF file
        xml_path: Path to the XML file
        
    Returns:
        Unified dictionary containing:
        - 'extraction_timestamp': ISO format timestamp of extraction
        - 'pdf': PDF extraction results
        - 'xml': XML extraction results
        - 'summary': High-level status information
        
    Example:
        >>> result = extract_and_normalize('document.pdf', 'config.xml')
        >>> print(json.dumps(result, indent=2))
    """
    import datetime
    
    logger.info("=" * 60)
    logger.info("Starting document reconciliation extraction pipeline")
    logger.info("=" * 60)
    
    # Initialize extractor
    extractor = DocumentExtractor()
    
    # Extract PDF
    logger.info(f"Processing PDF: {pdf_path}")
    pdf_result = extractor.extract_pdf(pdf_path)
    
    # Extract XML
    logger.info(f"Processing XML: {xml_path}")
    xml_result = extractor.extract_xml(xml_path)
    
    # Determine overall extraction status
    extraction_success = (
        pdf_result.get('status') == 'success' and 
        xml_result.get('status') == 'success'
    )
    
    # Combine results into single unified dictionary
    combined_result = {
        'extraction_timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        'pdf_content': pdf_result.get('content', '') if pdf_result.get('status') == 'success' else None,
        'xml_content': xml_result.get('data', {}) if xml_result.get('status') == 'success' else None,
        'pdf': pdf_result,
        'xml': xml_result,
        'summary': {
            'overall_status': 'success' if extraction_success else 'partial_failure',
            'pdf_status': pdf_result.get('status', 'unknown'),
            'xml_status': xml_result.get('status', 'unknown'),
            'pdf_file': str(pdf_path),
            'xml_file': str(xml_path)
        }
    }
    
    logger.info("=" * 60)
    logger.info(f"Extraction pipeline completed: {combined_result['summary']['overall_status']}")
    logger.info("=" * 60)
    
    return combined_result


if __name__ == '__main__':
    # Example usage
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python extractor.py <pdf_path> <xml_path>")
        print("\nExample:")
        print("  python extractor.py document.pdf config.xml")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    xml_file = sys.argv[2]
    
    # Suppress logging to keep output clean JSON
    logging.getLogger().setLevel(logging.CRITICAL)
    
    # Run extraction
    result = extract_and_normalize(pdf_file, xml_file)
    
    # Output results as formatted JSON (no logs)
    print(json.dumps(result, indent=2))
