/**
 * SETUP & USAGE GUIDE - Insurance Timeline Anomaly Detection Server
 * 
 * This guide shows how to set up and use the Node.js orchestration layer.
 */

// ============================================================================
// 1. INSTALLATION
// ============================================================================

/*
# Install dependencies
npm install

# For development with auto-reload
npm install --save-dev nodemon
npm run dev

# For production
npm start
*/

// ============================================================================
// 2. PREREQUISITES
// ============================================================================

/*
Required:
- Node.js 16+ installed
- Apache Kafka running (default: localhost:9092)
- Kafka topic 'policy-timeline-jobs' created

Quick Kafka setup with Docker:
  docker run -d \
    -p 9092:9092 \
    -p 29092:29092 \
    -e KAFKA_LISTENERS=PLAINTEXT://:9092,PLAINTEXT_HOST://0.0.0.0:29092 \
    -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092 \
    -e KAFKA_INTER_BROKER_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT \
    -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka:29093 \
    confluentinc/cp-kafka:latest
*/

// ============================================================================
// 3. API ENDPOINTS
// ============================================================================

/**
 * HEALTH CHECK
 * 
 * GET http://localhost:3000/health
 * 
 * Response:
 * {
 *   "status": "healthy",
 *   "timestamp": "2026-03-27T12:42:14.590014Z",
 *   "kafka": "connected",
 *   "uptime": 123.456
 * }
 */

/**
 * UPLOAD & ANALYZE TIMELINE
 * 
 * POST http://localhost:3000/api/analyze-timeline
 * Content-Type: multipart/form-data
 * 
 * Body:
 * - statements: [multiple files]
 * 
 * Response (202 Accepted):
 * {
 *   "jobId": "550e8400-e29b-41d4-a716-446655440000",
 *   "fileCount": 3,
 *   "files": [
 *     {
 *       "originalName": "statement_2024.pdf",
 *       "savedName": "1710068334590_statement_2024.pdf",
 *       "size": 245678,
 *       "mimetype": "application/pdf"
 *     }
 *   ],
 *   "message": "Timeline queued for anomaly detection analysis",
 *   "status": "accepted",
 *   "timestamp": "2026-03-27T12:42:14.590014Z"
 * }
 */

// ============================================================================
// 4. CURL EXAMPLES
// ============================================================================

/*
# Check server health
curl http://localhost:3000/health

# Upload single PDF
curl -X POST http://localhost:3000/api/analyze-timeline \
  -F "statements=@document.pdf"

# Upload multiple files
curl -X POST http://localhost:3000/api/analyze-timeline \
  -F "statements=@statement_2024.pdf" \
  -F "statements=@statement_2023.pdf" \
  -F "statements=@config.xml"

# Upload with verbose output
curl -v -X POST http://localhost:3000/api/analyze-timeline \
  -F "statements=@document.pdf"
*/

// ============================================================================
// 5. ARCHITECTURE
// ============================================================================

/*
Client (uploads files)
    ↓
Express Server (Port 3000)
    ↓
Multer (saves files to /uploads)
    ↓
Kafka Producer (publishes job message)
    ↓
Kafka Topic: policy-timeline-jobs
    ↓
Consumer (processes anomaly detection)

Key Features:
- Immediate 202 response (async processing)
- Unique jobId for tracking
- File path mapping for consumer
- CORS enabled for cross-origin requests
- Global error handling
- Graceful shutdown support
*/

// ============================================================================
// 6. ENVIRONMENT VARIABLES (optional)
// ============================================================================

/*
Create .env file:

PORT=3000
KAFKA_BROKERS=localhost:9092,localhost:9093
NODE_ENV=production
*/

// ============================================================================
// 7. PRODUCTION CONSIDERATIONS
// ============================================================================

/*
TODO: Add to production setup:
1. Database for job status tracking
2. Redis for caching
3. Job retry logic
4. File cleanup after processing
5. Request rate limiting
6. API authentication/JWT
7. Metrics collection (Prometheus)
8. Structured logging (Winston/Pino)
9. Health checks with database connectivity
10. Load balancing with multiple instances
11. File upload virus scanning
12. Encryption for sensitive data
*/

// ============================================================================
// 8. TROUBLESHOOTING
// ============================================================================

/*
Q: "Cannot find module 'express'"
A: Run: npm install

Q: "Kafka producer not connected"
A: Ensure Kafka is running on localhost:9092
   Check: npm run dev (logs will show connection status)

Q: "Files not uploading"
A: Check /uploads directory exists
   Check file size < 50MB
   Check file type is PDF/XML/JSON/CSV

Q: "CORS errors"
A: Server has CORS enabled by default
   Verify request headers are correct
*/

export {};
