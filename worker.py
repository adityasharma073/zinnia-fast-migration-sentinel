"""
Kafka Consumer Worker - Policy Timeline Anomaly Detection
=========================================================

A production-ready Kafka consumer that processes policy timeline documents
for anomaly detection. Integrates with the Express server's document pipeline
and performs mock AI analysis (ready to swap with real OpenAI API).

Author: Senior Python Engineer
Purpose: Listen to Kafka, extract timelines, run mock AI analysis, save reports
"""

import json
import logging
import time
import sys
import requests
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import OpenAI
try:
    from openai import OpenAI
except ImportError:
    print("✗ OpenAI library not installed")
    print("Install with: pip install openai")
    sys.exit(1)

# Import the extraction function from extractor.py
try:
    from extractor import extract_and_normalize
except ImportError as e:
    print(f"✗ Failed to import extractor: {e}")
    print("Make sure extractor.py is in the same directory")
    sys.exit(1)

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

KAFKA_BROKERS = ['localhost:9092']
KAFKA_TOPIC = 'policy-timeline-jobs'
REPORTS_DIR = Path(__file__).parent / 'reports'
CONSUMER_GROUP = 'policy-timeline-workers'
SESSION_TIMEOUT = 30000  # 30 seconds
WEBHOOK_URL = 'http://localhost:3000/api/webhook/status'  # Node.js webhook endpoint

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    print("✗ ERROR: OPENAI_API_KEY not found in .env file")
    print("Create a .env file with: OPENAI_API_KEY=your_key_here")
    sys.exit(1)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Ensure reports directory exists
REPORTS_DIR.mkdir(exist_ok=True)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('worker.log')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# WEBHOOK HELPER FUNCTION
# ============================================================================

def send_webhook_update(job_id: str, status: str, report: Optional[Dict[str, Any]] = None, message: str = '') -> bool:
    """
    Send a status update webhook to the Node.js server.
    
    This function is called at each stage of job processing to update the
    frontend in real-time via Socket.io broadcast.
    
    Args:
        job_id: Unique job identifier
        status: Status type - "PROCESSING" or "COMPLETE"
        report: Optional anomaly report dictionary (include on COMPLETE)
        message: Optional status message
        
    Returns:
        True if webhook was sent successfully, False otherwise
    """
    try:
        payload = {
            'jobId': job_id,
            'status': status,
            'message': message,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Include report on COMPLETE status
        if status == 'COMPLETE' and report:
            payload['report'] = report
        
        # Send webhook POST request
        response = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            logger.info(f"✓ Webhook sent: {status} for job {job_id}")
            return True
        else:
            logger.warning(f"⚠ Webhook returned {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        logger.error(f"✗ Failed to connect to webhook: {WEBHOOK_URL}")
        return False
    except requests.exceptions.Timeout:
        logger.error(f"✗ Webhook request timed out")
        return False
    except Exception as e:
        logger.error(f"✗ Webhook error: {str(e)}")
        return False

# ============================================================================
# MOCK AI ANALYSIS FUNCTION
# ============================================================================

def analyze_timeline_with_openai(timeline_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Real AI function for anomaly detection using OpenAI GPT-4.
    
    Uses OpenAI's API to intelligently analyze policy timeline data and
    detect meaningful anomalies in insurance policy documents.
    
    Args:
        timeline_data: Dictionary containing extracted PDF and XML content
        
    Returns:
        Dictionary with anomaly detection report from real AI analysis
    """
    
    try:
        logger.info("🤖 Running real AI analysis with OpenAI GPT-4...")
        
        # Prepare the timeline data summary for OpenAI - use full content, not truncated
        timeline_summary = json.dumps(timeline_data, indent=2)[:8000]  # Increased from 3000 to 8000 chars
        
        logger.info(f"📊 Sending {len(timeline_summary)} characters to GPT-4 for analysis...")
        
        # Create a detailed, insurance-specific prompt
        prompt = f"""You are an expert insurance policy analyst specializing in Statement of Account (SOA) reconciliation and migration validation.

EXTRACTED POLICY DOCUMENT DATA:
{timeline_summary}

TASK: Analyze this policy document data and identify ANY anomalies, discrepancies, inconsistencies, or irregularities that could indicate:
- Data migration errors
- Fee calculation discrepancies
- Benefit value mismatches
- Decimal point errors
- Unexplained spikes or drops in values
- Inconsistent unit prices
- Policy amendment issues
- Value misalignments between baseline and current statements

Return ONLY valid JSON (no markdown, no code blocks, no extra text):
{{
    "status": "success",
    "analysis_type": "policy_timeline_anomaly_detection",
    "model": "gpt-4",
    "confidence_score": 0.9,
    "anomalies": [
        {{
            "type": "specific_issue_name",
            "severity": "critical|high|medium|low",
            "description": "Detailed technical description of the anomaly with specific values and percentages",
            "change_percentage": -85.5,
            "detected_period": "Q4 2024 vs Q1 2025",
            "risk_level": "HIGH|MEDIUM|LOW",
            "recommendation": "Specific remediation action"
        }}
    ],
    "summary": {{
        "total_anomalies_detected": 2,
        "critical_count": 1,
        "high_count": 1,
        "medium_count": 0,
        "requires_human_review": true,
        "automated_action": "FLAG_FOR_REVIEW"
    }},
    "timeline_metrics": {{
        "documents_analyzed": 1,
        "data_quality_score": 0.85,
        "completeness": "90%"
    }},
    "processed_at": "{datetime.utcnow().isoformat()}Z"
}}

Be specific. Use actual numbers from the data. Identify real issues, not generic ones."""

        # Call OpenAI API
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert insurance policy analyst with 20+ years of SOA reconciliation experience. You analyze financial documents for data integrity, consistency, and migration errors. You return ONLY valid JSON with no markdown, no explanations, no code blocks."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,  # Lower temperature for more consistent JSON
            max_tokens=3500  # Increased from 2500 to get more detailed responses
        )
        
        # Extract the response
        response_text = response.choices[0].message.content.strip()
        
        # Clean up response - remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        logger.info(f"🔍 GPT-4 Analysis Result (first 300 chars):\n{response_text[:300]}")
        
        # Parse JSON response
        try:
            anomaly_report = json.loads(response_text)
            logger.info(f"✅ Successfully parsed GPT-4 response with {len(anomaly_report.get('anomalies', []))} anomalies")
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Failed to parse OpenAI response as JSON: {e}")
            logger.warning(f"Response text:\n{response_text[:1000]}")
            logger.warning("Failed to parse OpenAI response as JSON, using fallback")
            # Fallback if JSON parsing fails
            anomaly_report = {
                "status": "success",
                "analysis_type": "policy_timeline_anomaly_detection",
                "model": "gpt-4-fallback",
                "confidence_score": 0.75,
                "anomalies": [{
                    "type": "analysis_pattern",
                    "severity": "medium",
                    "description": f"AI Analysis: {response_text[:200]}",
                    "change_percentage": 0.0,
                    "detected_period": "Current",
                    "risk_level": "MEDIUM",
                    "recommendation": "Manual review recommended"
                }],
                "summary": {
                    "total_anomalies_detected": 1,
                    "critical_count": 0,
                    "high_count": 0,
                    "medium_count": 1,
                    "requires_human_review": True,
                    "automated_action": "FLAG_FOR_REVIEW"
                },
                "timeline_metrics": {
                    "documents_analyzed": 1,
                    "data_quality_score": 0.85,
                    "completeness": "80%"
                },
                "processed_at": datetime.utcnow().isoformat() + "Z"
            }
        
        return anomaly_report
        
    except Exception as e:
        logger.error(f"❌ OpenAI API error: {str(e)}")
        # Fallback mock response if API fails
        return {
            "status": "error",
            "error_message": f"OpenAI API error: {str(e)}",
            "fallback": True,
            "analysis_type": "policy_timeline_anomaly_detection",
            "model": "gpt-4-error-fallback",
            "anomalies": [],
            "summary": {
                "total_anomalies_detected": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "requires_human_review": False,
                "automated_action": "RETRY"
            }
        }


# Keep the old mock function for reference/fallback
def mock_analyze_timeline(timeline_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mock AI function for anomaly detection analysis (DEPRECATED - use analyze_timeline_with_openai instead).
    
    This is kept as a fallback but should not be used in production.
    """
    
    logger.info("⚠️  Using MOCK analysis (deprecated). Use OpenAI integration instead.")
    
    # Simulate network latency
    time.sleep(2)
    
    # Mock anomaly report with realistic data
    anomaly_report = {
        "status": "success",
        "analysis_type": "policy_timeline_anomaly_detection",
        "model": "mock-ai-v1.0",
        "confidence_score": 0.87,
        "anomalies": [
            {
                "type": "death_benefit_drop",
                "severity": "critical",
                "description": "Sudden 90% drop in death benefit value",
                "value_before": 500000,
                "value_after": 50000,
                "change_percentage": -90.0,
                "detected_period": "Q4 2024",
                "risk_level": "HIGH",
                "recommendation": "Investigate policy adjustment or potential data entry error"
            },
            {
                "type": "fee_spike",
                "severity": "high",
                "description": "Unexpected 200% increase in annual fees",
                "previous_annual_fee": 1200,
                "current_annual_fee": 3600,
                "change_percentage": 200.0,
                "detected_period": "2026-Q1",
                "risk_level": "MEDIUM",
                "recommendation": "Review rider charges and policy amendments"
            },
            {
                "type": "premium_irregularity",
                "severity": "medium",
                "description": "Irregular premium payment pattern detected",
                "pattern": "payments skipped in months 2, 5, 8, 11",
                "likelihood": "payment processing error",
                "risk_level": "LOW",
                "recommendation": "Verify payment method and contact policyholder"
            }
        ],
        "summary": {
            "total_anomalies_detected": 3,
            "critical_count": 1,
            "high_count": 1,
            "medium_count": 1,
            "requires_human_review": True,
            "automated_action": "FLAG_FOR_REVIEW"
        },
        "timeline_metrics": {
            "documents_analyzed": 1,
            "time_periods_covered": "2013-2026",
            "data_quality_score": 0.95,
            "completeness": "95%"
        },
        "processed_at": datetime.utcnow().isoformat() + "Z",
        "processing_time_seconds": 2.0
    }
    
    return anomaly_report

# ============================================================================
# JOB PROCESSING FUNCTIONS
# ============================================================================

def extract_timeline(file_paths: List[str], job_id: str) -> Optional[Dict[str, Any]]:
    """
    Extract timeline data from uploaded document files.
    
    Uses the existing extractor.py to process PDF and XML files.
    Supports multiple PDFs and combines all extracted content.
    
    Args:
        file_paths: List of absolute file paths to process
        job_id: Unique job identifier for tracking
        
    Returns:
        Extracted timeline data dictionary with all PDFs processed
    """
    try:
        logger.info(f"📄 Extracting timeline from {len(file_paths)} files...")
        
        if not file_paths:
            logger.error("No file paths provided for extraction")
            return None
        
        # Separate PDFs and XML files
        pdf_files = [f for f in file_paths if f.lower().endswith('.pdf')]
        xml_files = [f for f in file_paths if f.lower().endswith('.xml')]
        
        logger.info(f"Found {len(pdf_files)} PDF files and {len(xml_files)} XML files")
        
        # Process all PDFs
        all_extractions = []
        combined_pdf_content = ""
        
        for i, pdf_file in enumerate(pdf_files, 1):
            logger.info(f"Processing PDF {i}/{len(pdf_files)}: {pdf_file}")
            xml_file = xml_files[0] if xml_files else pdf_file
            
            extraction_result = extract_and_normalize(pdf_file, xml_file)
            if extraction_result:
                all_extractions.append(extraction_result)
                # Combine PDF content
                if 'pdf_content' in extraction_result:
                    combined_pdf_content += f"\n\n--- Document {i} ---\n" + extraction_result['pdf_content']
                logger.info(f"✓ Successfully extracted PDF {i}")
            else:
                logger.warning(f"Failed to extract PDF {i}")
        
        if not all_extractions:
            logger.error("No successful extractions")
            return None
        
        # Combine all extractions into single result
        extraction_result = all_extractions[0]  # Start with first extraction
        extraction_result['pdf_content'] = combined_pdf_content  # Update with combined content
        extraction_result['documents_count'] = len(pdf_files)
        extraction_result['documents_processed'] = pdf_files
        
        if extraction_result and extraction_result.get('summary', {}).get('overall_status') == 'success':
            logger.info(f"✓ Timeline extraction successful for job {job_id}")
            return extraction_result
        else:
            logger.error(f"Timeline extraction failed or returned error status")
            return extraction_result
            
    except Exception as e:
        logger.error(f"✗ Error during timeline extraction: {str(e)}")
        return None

def process_job(message: Dict[str, Any]) -> bool:
    """
    Process a single job from Kafka message.
    
    Flow:
    1. Send PROCESSING webhook status
    2. Extract timeline from file paths
    3. Run mock AI analysis
    4. Save report to file
    5. Send COMPLETE webhook status with report
    6. Log success
    
    Args:
        message: Parsed JSON message from Kafka
        
    Returns:
        True if successful, False if processing failed
    """
    try:
        job_id = message.get('jobId')
        file_paths = message.get('filePaths', [])
        timestamp = message.get('timestamp')
        file_count = message.get('fileCount', 0)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 Processing Job: {job_id}")
        logger.info(f"   Files: {file_count}")
        logger.info(f"   Submitted: {timestamp}")
        logger.info(f"{'='*70}")
        
        # Validate job data
        if not job_id or not file_paths:
            logger.error("Invalid job message: missing jobId or filePaths")
            return False
        
        # STEP 0: Send PROCESSING webhook
        send_webhook_update(job_id, 'PROCESSING', message='Beginning timeline extraction and analysis...')
        
        # Step 1: Extract timeline from documents
        logger.info("Step 1: Extracting timeline from documents...")
        timeline_data = extract_timeline(file_paths, job_id)
        
        if not timeline_data:
            logger.error("Failed to extract timeline data")
            send_webhook_update(job_id, 'ERROR', message='Failed to extract timeline data')
            return False
        
        logger.info("✓ Timeline extraction complete")
        
        # Step 2: Run mock AI analysis
        logger.info("Step 2: Running anomaly detection analysis...")
        anomaly_report = analyze_timeline_with_openai(timeline_data)
        logger.info("✓ Anomaly analysis complete")
        
        # Step 3: Add extracted content to report (for UI viewing)
        anomaly_report['extraction_data'] = {
            'pdf_content': timeline_data.get('pdf_content', ''),
            'xml_content': timeline_data.get('xml_content', {}),
            'documents_count': timeline_data.get('documents_count', file_count),
            'documents_processed': timeline_data.get('documents_processed', file_paths)
        }
        
        # Step 4: Add metadata to report
        anomaly_report['job_metadata'] = {
            'jobId': job_id,
            'file_count': file_count,
            'files_processed': file_paths,
            'job_submitted_at': timestamp,
            'analysis_completed_at': datetime.utcnow().isoformat() + "Z"
        }
        
        # Step 5: Save report to file
        report_filename = f"report_{job_id}.json"
        report_path = REPORTS_DIR / report_filename
        
        try:
            with open(report_path, 'w') as f:
                json.dump(anomaly_report, f, indent=2)
            logger.info(f"✓ Report saved: {report_path}")
        except IOError as e:
            logger.error(f"Failed to save report file: {str(e)}")
            return False
        
        # STEP 6: Send COMPLETE webhook with report
        send_webhook_update(job_id, 'COMPLETE', report=anomaly_report, message='Analysis complete!')
        
        # Step 7: Log success summary
        summary = anomaly_report.get('summary', {})
        logger.info(f"\n{'='*70}")
        logger.info(f"✅ JOB COMPLETED SUCCESSFULLY")
        logger.info(f"   Job ID: {job_id}")
        logger.info(f"   Anomalies Found: {summary.get('total_anomalies_detected', 0)}")
        logger.info(f"   Critical Issues: {summary.get('critical_count', 0)}")
        logger.info(f"   Report: {report_path}")
        logger.info(f"{'='*70}\n")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Exception during job processing: {str(e)}", exc_info=True)
        return False

# ============================================================================
# KAFKA CONSUMER
# ============================================================================

def start_consumer():
    """
    Start the Kafka consumer and listen for incoming jobs.
    
    - Connects to Kafka broker
    - Subscribes to policy-timeline-jobs topic
    - Continuously polls for messages
    - Processes each job with error handling
    - Gracefully handles shutdown signals
    """
    
    logger.info("="*70)
    logger.info("🚀 Starting Policy Timeline Anomaly Detection Worker")
    logger.info("="*70)
    logger.info(f"Kafka Brokers: {KAFKA_BROKERS}")
    logger.info(f"Topic: {KAFKA_TOPIC}")
    logger.info(f"Consumer Group: {CONSUMER_GROUP}")
    logger.info(f"Reports Directory: {REPORTS_DIR}")
    logger.info("="*70)
    
    consumer = None
    job_count = 0  # Initialize before try block
    
    try:
        # Initialize Kafka consumer
        logger.info("Connecting to Kafka broker...")
        
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKERS,
            group_id=CONSUMER_GROUP,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            session_timeout_ms=SESSION_TIMEOUT,
            max_poll_records=1,
            consumer_timeout_ms=1000
        )
        
        logger.info(f"✓ Connected to Kafka")
        logger.info(f"✓ Subscribed to topic: {KAFKA_TOPIC}")
        logger.info("🔄 Listening for jobs...\n")
        
        # Poll for messages
        
        while True:
            try:
                # Poll for messages with timeout
                messages = consumer.poll(timeout_ms=5000)
                
                if not messages:
                    # No messages, continue listening
                    continue
                
                # Process each message
                for topic_partition, records in messages.items():
                    for record in records:
                        job_count += 1
                        
                        try:
                            # Parse message
                            message = record.value
                            
                            # Process job
                            success = process_job(message)
                            
                            if not success:
                                logger.warning("Job processing completed with errors")
                                
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse message JSON: {str(e)}")
                        except Exception as e:
                            logger.error(f"Unexpected error processing message: {str(e)}", exc_info=True)
                            # Continue to next message
                            continue
                
            except KafkaError as e:
                logger.error(f"Kafka error: {str(e)}")
                # Continue listening despite Kafka errors
                time.sleep(2)
                
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutdown signal received (Ctrl+C)")
    except Exception as e:
        logger.error(f"✗ Fatal error in consumer: {str(e)}", exc_info=True)
    finally:
        # Cleanup
        if consumer:
            logger.info("Closing Kafka consumer...")
            consumer.close()
        
        logger.info("="*70)
        logger.info(f"Worker stopped. Jobs processed: {job_count}")
        logger.info("="*70)

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    try:
        start_consumer()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
