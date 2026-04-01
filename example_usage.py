"""
Example usage and test cases for the Document Extraction Microservice.

This file demonstrates how to use the extractor module in various scenarios.
"""

import json
from pathlib import Path
from extractor import extract_and_normalize, DocumentExtractor


def example_basic_usage():
    """Basic usage example - extract both PDF and XML."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Usage - Full Document Extraction")
    print("="*70)
    
    # Assuming you have sample PDF and XML files
    pdf_path = "sample_document.pdf"
    xml_path = "sample_config.xml"
    
    try:
        result = extract_and_normalize(pdf_path, xml_path)
        
        # Pretty print the results
        print(json.dumps(result, indent=2))
        
        # Save to file for inspection
        with open('extraction_result.json', 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to: extraction_result.json")
        
    except Exception as e:
        print(f"Error during extraction: {e}")


def example_pdf_only():
    """Extract PDF only."""
    print("\n" + "="*70)
    print("EXAMPLE 2: PDF-Only Extraction")
    print("="*70)
    
    extractor = DocumentExtractor()
    pdf_result = extractor.extract_pdf("sample_document.pdf")
    
    print(f"Status: {pdf_result['status']}")
    
    if pdf_result['status'] == 'success':
        print(f"\nMetadata:")
        print(f"  Pages: {pdf_result['metadata']['page_count']}")
        print(f"  Source: {pdf_result['metadata']['source_file']}")
        
        print(f"\nContent Preview (first 500 chars):")
        print(pdf_result['content'][:500])
        
        print(f"\nTables Found: {len(pdf_result['tables'])}")
        for idx, table in enumerate(pdf_result['tables']):
            print(f"  Table {idx}: {table.get('index', 'N/A')}")
    else:
        print(f"Error: {pdf_result['error']}")


def example_xml_only():
    """Extract XML only."""
    print("\n" + "="*70)
    print("EXAMPLE 3: XML-Only Extraction")
    print("="*70)
    
    extractor = DocumentExtractor()
    xml_result = extractor.extract_xml("sample_config.xml")
    
    print(f"Status: {xml_result['status']}")
    
    if xml_result['status'] == 'success':
        print(f"\nMetadata:")
        print(f"  File Size: {xml_result['metadata']['file_size_bytes']} bytes")
        print(f"  Source: {xml_result['metadata']['source_file']}")
        print(f"  Encoding: {xml_result['metadata']['encoding']}")
        
        print(f"\nParsed XML (as dictionary):")
        print(json.dumps(xml_result['data'], indent=2)[:500])
    else:
        print(f"Error: {xml_result['error']}")


def example_error_handling():
    """Demonstrate error handling."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Error Handling")
    print("="*70)
    
    extractor = DocumentExtractor()
    
    # Test 1: Non-existent PDF
    print("\nTest 1: Non-existent PDF")
    result = extractor.extract_pdf("nonexistent.pdf")
    print(f"Status: {result['status']}")
    print(f"Error: {result['error']}")
    
    # Test 2: Invalid file extension
    print("\n\nTest 2: Invalid file extension")
    result = extractor.extract_xml("document.txt")
    print(f"Status: {result['status']}")
    print(f"Error: {result['error']}")
    
    # Test 3: Malformed XML
    print("\n\nTest 3: Malformed XML handling")
    # Create a test malformed XML file
    Path("malformed.xml").write_text("<root><unclosed>")
    result = extractor.extract_xml("malformed.xml")
    print(f"Status: {result['status']}")
    print(f"Error: {result['error']}")
    # Clean up
    Path("malformed.xml").unlink()


def example_integration():
    """Integration example - process results for downstream use."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Integration with Downstream Processing")
    print("="*70)
    
    result = extract_and_normalize("sample_document.pdf", "sample_config.xml")
    
    # Extract summary status
    summary = result['summary']
    print(f"\nExtraction Summary:")
    print(f"  Overall Status: {summary['overall_status']}")
    print(f"  PDF Status: {summary['pdf_status']}")
    print(f"  XML Status: {summary['xml_status']}")
    print(f"  Timestamp: {result['extraction_timestamp']}")
    
    # Conditional processing based on status
    if summary['pdf_status'] == 'success':
        pdf_content = result['pdf']['content']
        pdf_metadata = result['pdf']['metadata']
        print(f"\n  ✓ PDF extracted successfully ({pdf_metadata['page_count']} pages)")
        # Process content further...
    
    if summary['xml_status'] == 'success':
        xml_data = result['xml']['data']
        xml_size = result['xml']['metadata']['file_size_bytes']
        print(f"  ✓ XML parsed successfully ({xml_size} bytes)")
        # Process XML data further...
    
    # For database/API ingestion
    if summary['overall_status'] == 'success':
        print("\n✓ All extractions successful - ready for downstream pipeline")
        # Next step: LLM comparison, reconciliation, etc.
    else:
        print("\n⚠ Some extractions failed - review errors above")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("DOCUMENT RECONCILIATION PIPELINE - EXTRACTION EXAMPLES")
    print("="*70)
    
    # Uncomment the examples you want to run:
    
    # example_pdf_only()
    # example_xml_only()
    example_error_handling()
    # example_integration()
    
    # Run the full pipeline (requires sample files):
    # example_basic_usage()
    
    print("\n" + "="*70)
    print("Examples completed!")
    print("="*70)
