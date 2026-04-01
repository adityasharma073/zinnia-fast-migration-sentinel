/**
 * Insurance Timeline Anomaly Detection - Express Orchestration Layer
 * 
 * A production-ready Node.js server that handles document ingestion for AI-powered
 * anomaly detection in insurance statement timelines. Uses Apache Kafka for
 * asynchronous processing and Multer for robust file handling.
 * 
 * Author: Senior Backend Engineer
 * Purpose: Orchestrate document uploads and queue them for timeline anomaly analysis
 */

import express from 'express';
import multer from 'multer';
import cors from 'cors';
import { Kafka } from 'kafkajs';
import { Server } from 'socket.io';
import http from 'http';
import crypto from 'crypto';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

// ============================================================================
// CONFIGURATION & CONSTANTS
// ============================================================================

// Get __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Server configuration
const PORT = process.env.PORT || 3000;
const KAFKA_BROKERS = (process.env.KAFKA_BROKERS || 'localhost:9092').split(',');
const KAFKA_TOPIC = 'policy-timeline-jobs';
const UPLOADS_DIR = path.join(__dirname, 'uploads');

// Ensure uploads directory exists
if (!fs.existsSync(UPLOADS_DIR)) {
  fs.mkdirSync(UPLOADS_DIR, { recursive: true });
  console.log(`✓ Created uploads directory: ${UPLOADS_DIR}`);
}

// ============================================================================
// EXPRESS APP SETUP
// ============================================================================

const app = express();

// Enable CORS for cross-origin requests
app.use(cors());

// Parse JSON request bodies
app.use(express.json());

// Serve static files from public directory
app.use(express.static(path.join(__dirname, 'public')));

// ============================================================================
// SOCKET.IO SETUP - WebSocket Server
// ============================================================================

/**
 * Socket.io server will be created after HTTP server is initialized
 * We'll set this up in the startServer function below
 */
let io = null;

// ============================================================================
// MULTER CONFIGURATION - File Upload Handler
// ============================================================================

/**
 * Storage configuration for multer
 * - Saves files to /uploads directory
 * - Preserves original filename with timestamp to avoid collisions
 */
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    // Save all files to uploads directory
    cb(null, UPLOADS_DIR);
  },
  filename: (req, file, cb) => {
    // Generate unique filename: timestamp_originalname
    const timestamp = Date.now();
    const filename = `${timestamp}_${file.originalname}`;
    cb(null, filename);
  }
});

/**
 * Multer instance configured to:
 * - Accept multiple files under 'statements' field
 * - Limit file size to 50MB per file
 * - Store files with original extensions preserved
 */
const upload = multer({
  storage: storage,
  limits: {
    fileSize: 50 * 1024 * 1024, // 50MB per file
    files: 100 // Max 100 files per request
  },
  fileFilter: (req, file, cb) => {
    // Accept PDF, XML, JSON, and CSV files
    const allowedMimes = ['application/pdf', 'application/xml', 'text/xml', 'application/json', 'text/csv'];
    if (allowedMimes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error(`File type not supported: ${file.mimetype}`));
    }
  }
});

// ============================================================================
// KAFKA PRODUCER INITIALIZATION
// ============================================================================

/**
 * Initialize Kafka client and producer
 * Connects to specified brokers for message publishing
 */
const kafka = new Kafka({
  clientId: 'insurance-timeline-orchestrator',
  brokers: KAFKA_BROKERS,
  connectionTimeout: 10000,
  requestTimeout: 30000,
  retry: {
    initialRetryTime: 100,
    retries: 8,
    maxRetryTime: 30000
  }
});

const producer = kafka.producer({
  transactionTimeout: 30000,
  idempotent: true
});

// Flag to track producer connection status
let producerConnected = false;

/**
 * Connect Kafka producer on server startup
 */
async function connectProducer() {
  try {
    await producer.connect();
    producerConnected = true;
    console.log('✓ Kafka producer connected successfully');
  } catch (error) {
    console.error('✗ Failed to connect Kafka producer:', error.message);
    // Continue server startup even if Kafka unavailable for graceful degradation
  }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Generate a unique job ID using crypto
 * Format: UUID v4 (randomized)
 * 
 * @returns {string} Unique job identifier
 */
function generateJobId() {
  return crypto.randomUUID();
}

/**
 * Get absolute file paths from multer file objects
 * 
 * @param {Array} files - Array of multer file objects
 * @returns {Array} Array of absolute file paths
 */
function getAbsoluteFilePaths(files) {
  return files.map(file => path.resolve(file.path));
}

/**
 * Publish a message to Kafka topic
 * 
 * @param {string} jobId - Unique job identifier
 * @param {Array} filePaths - Array of file paths for processing
 * @throws {Error} If Kafka publishing fails
 */
async function publishTimelineJob(jobId, filePaths) {
  if (!producerConnected) {
    console.warn('⚠ Kafka producer not connected, queueing locally');
    // In production, implement local queue or retry logic
    return;
  }

  try {
    const message = {
      jobId,
      filePaths,
      timestamp: new Date().toISOString(),
      fileCount: filePaths.length
    };

    // Send message to Kafka topic
    await producer.send({
      topic: KAFKA_TOPIC,
      messages: [
        {
          key: jobId, // Use jobId as partition key for ordering
          value: JSON.stringify(message),
          headers: {
            'content-type': 'application/json',
            'job-id': jobId
          }
        }
      ]
    });

    console.log(`✓ Published job ${jobId} to Kafka with ${filePaths.length} files`);
  } catch (error) {
    console.error(`✗ Error publishing to Kafka:`, error.message);
    throw error;
  }
}

// ============================================================================
// ROUTE HANDLERS
// ============================================================================

/**
 * Health check endpoint
 * Verifies server is running and Kafka connection status
 * 
 * @route GET /health
 * @returns {200} Server status and Kafka connectivity
 */
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    kafka: producerConnected ? 'connected' : 'disconnected',
    uptime: process.uptime()
  });
});

/**
 * Timeline Anomaly Detection API Endpoint
 * 
 * Accepts multiple insurance statement documents and queues them for
 * asynchronous anomaly detection analysis via Kafka.
 * 
 * @route POST /api/analyze-timeline
 * @param {File[]} statements - Array of statement files (PDF, XML, JSON, CSV)
 * 
 * @returns {202} Accepted - Job queued for processing
 * @returns {400} Bad Request - No files uploaded
 * @returns {500} Internal Server Error - Server processing error
 * 
 * @example
 * POST /api/analyze-timeline
 * Content-Type: multipart/form-data
 * 
 * statements: [file1.pdf, file2.pdf, file3.xml]
 * 
 * Response:
 * {
 *   "jobId": "550e8400-e29b-41d4-a716-446655440000",
 *   "fileCount": 3,
 *   "message": "Timeline queued for anomaly detection",
 *   "status": "accepted"
 * }
 */
app.post(
  '/api/analyze-timeline',
  upload.array('statements'), // Handle multiple files under 'statements' field
  async (req, res) => {
    try {
      // Validate that files were uploaded
      if (!req.files || req.files.length === 0) {
        return res.status(400).json({
          status: 'error',
          message: 'No files uploaded. Please provide at least one statement file.',
          receivedFiles: 0
        });
      }

      // Generate unique job identifier for tracking
      const jobId = generateJobId();

      // Extract absolute file paths from uploaded files
      const filePaths = getAbsoluteFilePaths(req.files);

      // Log incoming request
      console.log(`\n📥 New timeline analysis request received:`);
      console.log(`   Job ID: ${jobId}`);
      console.log(`   Files: ${req.files.length}`);
      console.log(`   Files: ${req.files.map(f => f.originalname).join(', ')}`);

      // Publish job to Kafka for asynchronous processing
      await publishTimelineJob(jobId, filePaths);

      // Immediately return 202 Accepted response (do not wait for processing)
      return res.status(202).json({
        jobId,
        fileCount: req.files.length,
        files: req.files.map(f => ({
          originalName: f.originalname,
          savedName: f.filename,
          size: f.size,
          mimetype: f.mimetype
        })),
        message: 'Timeline queued for anomaly detection analysis',
        status: 'accepted',
        timestamp: new Date().toISOString()
      });

    } catch (error) {
      // Log error details
      console.error(`✗ Error processing timeline request:`, error.message);

      // Return 500 Internal Server Error
      return res.status(500).json({
        status: 'error',
        message: 'Failed to queue timeline for analysis',
        error: error.message
      });
    }
  }
);

/**
 * Retrieve job status endpoint (optional)
 * 
 * In production, this would query a database for job status
 * For now, returns placeholder response
 * 
 * @route GET /api/jobs/:jobId
 * @param {string} jobId - Job identifier
 * @returns {200} Job status information
 */
app.get('/api/jobs/:jobId', (req, res) => {
  const { jobId } = req.params;

  // TODO: Implement job status retrieval from database
  // For now, return placeholder response
  return res.status(200).json({
    jobId,
    status: 'processing',
    message: 'Job status endpoint - implement status tracking via database',
    timestamp: new Date().toISOString()
  });
});

/**
 * Webhook Endpoint for Python Worker Status Updates
 * 
 * The Python worker calls this endpoint to send real-time status updates.
 * Each update is broadcast to connected frontend clients via Socket.io.
 * 
 * @route POST /api/webhook/status
 * @param {Object} body - Webhook payload
 *   @param {string} jobId - Job identifier (required)
 *   @param {string} status - Status type: "PROCESSING" or "COMPLETE" (required)
 *   @param {Object} report - Anomaly report (only on COMPLETE status)
 *   @param {string} message - Optional status message
 * 
 * @returns {200} OK - Webhook received and broadcasted
 * @returns {400} Bad Request - Missing required fields
 * @returns {500} Internal Server Error
 */
app.post('/api/webhook/status', (req, res) => {
  try {
    const { jobId, status, report, message } = req.body;

    // Validate required fields
    if (!jobId || !status) {
      return res.status(400).json({
        status: 'error',
        message: 'Missing required fields: jobId, status'
      });
    }

    // Log webhook receipt
    console.log(`\n📡 Webhook received for job ${jobId}: ${status}`);
    if (message) console.log(`   Message: ${message}`);

    // Prepare broadcast payload
    const broadcastPayload = {
      jobId,
      status,
      timestamp: new Date().toISOString(),
      message: message || ''
    };

    // Include report if COMPLETE status
    if (status === 'COMPLETE' && report) {
      broadcastPayload.report = report;
      console.log(`   Anomalies detected: ${report.summary?.total_anomalies_detected || 0}`);
    }

    // Broadcast to all connected clients
    io.emit('job:update', broadcastPayload);
    console.log(`✓ Broadcasted update to all connected clients`);

    // Return success immediately
    return res.status(200).json({
      status: 'success',
      message: 'Status update received and broadcasted',
      jobId,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error(`✗ Webhook error:`, error.message);
    return res.status(500).json({
      status: 'error',
      message: 'Failed to process webhook',
      error: error.message
    });
  }
});

/**
 * GET /api/get-report/:jobId
 * Retrieves the anomaly detection report for a given job
 */
app.get('/api/get-report/:jobId', (req, res) => {
  const { jobId } = req.params;
  const reportPath = path.join(__dirname, 'reports', `report_${jobId}.json`);

  try {
    if (!fs.existsSync(reportPath)) {
      return res.status(404).json({
        status: 'error',
        message: 'Report not found',
        jobId
      });
    }

    const reportContent = fs.readFileSync(reportPath, 'utf-8');
    const report = JSON.parse(reportContent);

    return res.status(200).json(report);
  } catch (error) {
    console.error(`✗ Error reading report for job ${jobId}:`, error.message);
    return res.status(500).json({
      status: 'error',
      message: 'Failed to read report',
      error: error.message
    });
  }
});

/**
 * GET /api/get-extraction/:jobId
 * Retrieves the extracted PDF and XML content for a given job
 * Useful for testing and verifying data extraction
 */
app.get('/api/get-extraction/:jobId', (req, res) => {
  const { jobId } = req.params;
  
  try {
    const reportPath = path.join(__dirname, 'reports', `report_${jobId}.json`);
    
    if (!fs.existsSync(reportPath)) {
      return res.status(404).json({
        status: 'error',
        message: 'Extraction data not found for this job',
        jobId
      });
    }

    const reportContent = fs.readFileSync(reportPath, 'utf-8');
    const report = JSON.parse(reportContent);

    // Get extraction data
    const extractionData = report.extraction_data || {};
    const pdfContent = extractionData.pdf_content || '';
    const xmlContent = extractionData.xml_content || {};

    return res.status(200).json({
      status: 'success',
      jobId: report.job_metadata?.jobId,
      filesProcessed: report.job_metadata?.files_processed || [],
      fileCount: report.job_metadata?.file_count,
      documentsAnalyzed: extractionData.documents_count,
      pdfContent: pdfContent,  // Send FULL content, not truncated
      fullPdfLength: pdfContent.length,
      xmlContent: xmlContent,
      extractionStatus: 'complete',
      analysisTimestamp: report.processed_at,
      anomaliesFound: report.summary?.total_anomalies_detected || 0
    });
  } catch (error) {
    console.error(`✗ Error reading extraction for job ${jobId}:`, error.message);
    return res.status(500).json({
      status: 'error',
      message: 'Failed to read extraction data',
      error: error.message
    });
  }
});

/**
 * 404 Not Found handler
 */
app.use((req, res) => {
  res.status(404).json({
    status: 'error',
    message: 'Endpoint not found',
    path: req.path,
    method: req.method
  });
});

/**
 * Global error handler
 * Catches any unhandled errors in middleware or route handlers
 */
app.use((err, req, res, next) => {
  console.error('✗ Unhandled error:', err);

  // Handle Multer-specific errors
  if (err instanceof multer.MulterError) {
    if (err.code === 'FILE_TOO_LARGE') {
      return res.status(400).json({
        status: 'error',
        message: 'File size exceeds 50MB limit',
        error: err.message
      });
    }
    if (err.code === 'LIMIT_FILE_COUNT') {
      return res.status(400).json({
        status: 'error',
        message: 'Too many files. Maximum 100 files per request.',
        error: err.message
      });
    }
  }

  // Generic error response
  res.status(500).json({
    status: 'error',
    message: 'Internal server error',
    error: err.message
  });
});

// ============================================================================
// SERVER STARTUP
// ============================================================================

/**
 * Start the Express server and initialize Kafka connection
 */
async function startServer() {
  try {
    // Connect Kafka producer
    await connectProducer();

    // Create HTTP server for Express + Socket.io
    const server = http.createServer(app);
    
    // Initialize Socket.io with HTTP server
    io = new Server(server, {
      cors: {
        origin: '*',
        methods: ['GET', 'POST']
      }
    });
    
    // Socket.io connection handler
    io.on('connection', (socket) => {
      console.log(`✓ WebSocket client connected: ${socket.id}`);
      
      socket.on('disconnect', () => {
        console.log(`✗ WebSocket client disconnected: ${socket.id}`);
      });
    });

    // Start HTTP server
    server.listen(PORT, () => {
      console.log(`\n${'='.repeat(70)}`);
      console.log(`✓ Insurance Timeline Anomaly Detection Server`);
      console.log(`${'='.repeat(70)}`);
      console.log(`Server running on: http://localhost:${PORT}`);
      console.log(`WebSocket (Socket.io) running on: ws://localhost:${PORT}`);
      console.log(`Uploads directory: ${UPLOADS_DIR}`);
      console.log(`Kafka topic: ${KAFKA_TOPIC}`);
      console.log(`Kafka brokers: ${KAFKA_BROKERS.join(', ')}`);
      console.log(`${'='.repeat(70)}\n`);
    });
  } catch (error) {
    console.error('✗ Failed to start server:', error);
    process.exit(1);
  }
}

/**
 * Graceful shutdown handler
 * Closes Kafka connection and server on SIGTERM
 */
process.on('SIGTERM', async () => {
  console.log('\n🛑 Received SIGTERM, shutting down gracefully...');
  try {
    await producer.disconnect();
    console.log('✓ Kafka producer disconnected');
    process.exit(0);
  } catch (error) {
    console.error('✗ Error during shutdown:', error);
    process.exit(1);
  }
});

/**
 * Start the server
 */
startServer();

export default app;
