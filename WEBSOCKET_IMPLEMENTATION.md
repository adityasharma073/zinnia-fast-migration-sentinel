# WebSocket Telemetry Implementation Guide

## Overview

You've successfully upgraded your "Zinnia Life: FAST Migration Sentinel" hackathon project with real-time WebSocket telemetry using Socket.io. The fake timers have been replaced with actual status updates from the Python worker.

## Architecture

```
Frontend (Browser)
    ↓ Upload Files
Node.js Server (Express + Socket.io)
    ↓ Queue Job to Kafka
Apache Kafka
    ↓ Consume Job
Python Worker
    ↓ POST Status Updates
Node.js Webhook Endpoint
    ↓ Socket.io Broadcast
Frontend (Real-Time Updates)
```

## Key Changes Made

### 1. **server.js** - Node.js Express Server

#### What was added:

**Imports:**
```javascript
import { Server } from 'socket.io';
```

**Socket.io Initialization (after Express app setup):**
```javascript
const io = new Server(app, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST']
  }
});

const activeJobs = new Map();

io.on('connection', (socket) => {
  console.log(`✓ WebSocket client connected: ${socket.id}`);
  socket.on('disconnect', () => {
    console.log(`✗ WebSocket client disconnected: ${socket.id}`);
    activeJobs.forEach((sockId, jobId) => {
      if (sockId === socket.id) {
        activeJobs.delete(jobId);
      }
    });
  });
});
```

**New Webhook Endpoint (POST /api/webhook/status):**
- Receives status updates from Python worker
- Broadcasts updates to all connected clients via Socket.io
- Includes the complete anomaly report on COMPLETE status
- Returns 200 OK immediately

**Location in file:** After the `/api/jobs/:jobId` endpoint

---

### 2. **worker.py** - Python Kafka Consumer

#### What was added:

**New Import:**
```python
import requests
```

**Configuration:**
```python
WEBHOOK_URL = 'http://localhost:3000/api/webhook/status'
```

**New Helper Function (`send_webhook_update`):**
- Sends HTTP POST to Node.js webhook
- Includes job ID, status, optional report, and timestamp
- Handles connection errors gracefully
- Returns True/False for success/failure

**Updated Job Processing:**
- **Before extraction:** `send_webhook_update(job_id, 'PROCESSING')`
  - Signals to frontend that worker has started processing
  
- **After analysis:** `send_webhook_update(job_id, 'COMPLETE', report=anomaly_report)`
  - Sends the full anomaly report with all findings
  - Triggers report display on frontend

---

### 3. **public/index.html** - Frontend Dashboard

#### What was added:

**Socket.io CDN Script:**
```html
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
```

**Global WebSocket Connection:**
```javascript
let socket = null;
let currentJobId = null;

function initializeSocket() {
    socket = io();
    
    socket.on('connect', () => {
        console.log('✓ Connected to WebSocket server');
    });
    
    socket.on('job:update', (data) => {
        // Handle real-time updates
    });
}
```

**Real-Time Status Handlers:**
- `handleProcessingStatus(data)`: Lights up node 3 (AI Analysis) when worker starts
- `handleCompleteStatus(data)`: Displays final report with anomalies
- `handleErrorStatus(data)`: Shows error messages and resets UI

**Dynamic Report Display:**
- `displayRealReport(report)`: Renders the actual anomalies from worker
- Shows severity badges (Critical/High/Medium)
- Displays recommendations
- Updates status badge (MIGRATION SAFE or CRITICAL ANOMALY DETECTED)

**Removed:**
- All `setTimeout` fake loading animations
- Mock status transitions
- Polling mechanism for report fetching

---

## How It Works (Complete Flow)

### Step 1: User Uploads Files
1. User selects PDFs via drag-drop or file input
2. Frontend shows pipeline visualizer
3. Node 1 activates: "Ingesting files into pipeline..."

### Step 2: Frontend Sends to Server
1. POST `/api/analyze-timeline` with FormData
2. Server receives and generates unique `jobId`
3. Server publishes job to Kafka topic
4. Server returns 202 Accepted with `jobId`
5. Frontend stores `currentJobId = jobId`

### Step 3: Worker Processes Job
1. Worker consumes job from Kafka
2. **🔴 WEBHOOK CALL 1**: Worker sends `PROCESSING` status
   ```python
   send_webhook_update(job_id, 'PROCESSING', message='Beginning extraction and analysis...')
   ```

### Step 4: Socket.io Broadcasts (Webhook #1)
1. Node.js receives webhook POST at `/api/webhook/status`
2. Broadcasts via Socket.io: `io.emit('job:update', { jobId, status: 'PROCESSING' })`
3. All connected clients receive update
4. Frontend activates node 2 and node 3
5. Status message updates: "Analyzing with AI..."

### Step 5: Worker Completes Analysis
1. Worker extracts PDFs/XML
2. Worker runs mock AI (or real OpenAI when API key available)
3. Worker generates anomaly report
4. **🔴 WEBHOOK CALL 2**: Worker sends `COMPLETE` status with full report
   ```python
   send_webhook_update(job_id, 'COMPLETE', report=anomaly_report)
   ```

### Step 6: Socket.io Broadcasts (Webhook #2)
1. Node.js receives webhook POST with full report
2. Broadcasts via Socket.io: `io.emit('job:update', { jobId, status: 'COMPLETE', report })`
3. All connected clients receive report data
4. Frontend activates node 4
5. Frontend calls `displayRealReport(report)`
6. Dashboard populates with real anomalies
7. Status badge turns Red (if critical) or Green (if safe)

---

## Implementation Checklist

✅ **Dependencies Updated:**
- `package.json`: Added `socket.io@^4.5.4`
- `worker_requirements.txt`: Added `requests>=2.28.0`

✅ **Files Modified:**
1. `server.js`
   - Import: `{ Server } from 'socket.io'`
   - Setup: Socket.io server initialization
   - Route: POST `/api/webhook/status`

2. `worker.py`
   - Import: `requests`
   - Config: `WEBHOOK_URL`
   - Function: `send_webhook_update()`
   - Updates: Two webhook calls in `process_job()`

3. `public/index.html`
   - CDN: Socket.io client
   - State: `socket`, `currentJobId`
   - Functions: `initializeSocket()`, handlers, `displayRealReport()`
   - Removed: All `setTimeout` fake timers

---

## Testing Instructions

### Terminal 1: Start Kafka
```bash
cd /Users/zinnia_india/Documents/Zinniovate
docker-compose up -d
```

### Terminal 2: Start Node.js Server
```bash
cd /Users/zinnia_india/Documents/Zinniovate
npm install  # If not done already
node server.js
```

### Terminal 3: Start Python Worker
```bash
cd /Users/zinnia_india/Documents/Zinniovate
source venv/bin/activate
python3 worker.py
```

### Terminal 4 (or Browser): Test the Pipeline
1. Open browser: `http://localhost:3000`
2. Upload 1-5 PDF files
3. Watch the pipeline:
   - Node 1 activates immediately
   - Node 2 activates after 500ms
   - **Real-time from worker:**
     - Node 3 activates when worker starts processing (PROCESSING webhook)
     - Node 4 activates when analysis completes (COMPLETE webhook)
   - Report appears with **real anomalies from your mock AI**

### Verify Console Logs

**Node.js Server Console:**
```
📡 Webhook received for job 550e8400-e29b-41d4-a716-446655440000: PROCESSING
   Message: Beginning extraction and analysis...
✓ Broadcasted update to all connected clients

📡 Webhook received for job 550e8400-e29b-41d4-a716-446655440000: COMPLETE
   Anomalies detected: 3
✓ Broadcasted update to all connected clients
```

**Python Worker Console:**
```
🎯 Processing Job: 550e8400-e29b-41d4-a716-446655440000
✓ Webhook sent: PROCESSING for job 550e8400-e29b-41d4-a716-446655440000
Step 1: Extracting timeline from documents...
✓ Timeline extraction complete
Step 2: Running anomaly detection analysis...
✓ Webhook sent: COMPLETE for job 550e8400-e29b-41d4-a716-446655440000
✅ JOB COMPLETED SUCCESSFULLY
```

**Browser Console:**
```
✓ Connected to WebSocket server
📡 Job update received: PROCESSING
🔄 Worker is processing...
📡 Job update received: COMPLETE
✅ Analysis complete!
```

---

## When You Get Your OpenAI API Key

To replace the mock AI with real analysis:

1. **Update `worker.py`:**
   ```python
   import openai
   
   def mock_analyze_timeline(timeline_data):
       openai.api_key = os.getenv('OPENAI_API_KEY')
       response = openai.ChatCompletion.create(
           model="gpt-4",
           messages=[{"role": "user", "content": f"Analyze this insurance timeline: {json.dumps(timeline_data)}"}]
       )
       # Parse response and return anomaly_report
   ```

2. **Set environment variable:**
   ```bash
   export OPENAI_API_KEY=sk-...
   ```

3. **Restart worker** - Everything else stays the same! The webhook system works with both mock and real AI.

---

## Production Considerations

### Scaling the Webhook
Currently webhooks are fire-and-forget. For production:

1. **Add webhook retries** in `worker.py`:
   ```python
   retry_count = 0
   max_retries = 3
   while retry_count < max_retries:
       try:
           response = requests.post(...)
           if response.status_code == 200:
               break
       except:
           retry_count += 1
           time.sleep(2 ** retry_count)
   ```

2. **Add webhook queue** in `server.js`:
   ```javascript
   const webhook_queue = [];
   // Store webhooks if broadcast fails
   // Retry periodically
   ```

### Persistence
Add a database to track job status:

```javascript
// server.js webhook handler
const jobStatus = await db.jobs.findByIdAndUpdate(jobId, {
    status: data.status,
    updatedAt: new Date(),
    report: data.report
});
```

### Multi-Client Broadcasting
Current implementation broadcasts to ALL connected clients. For production:

```javascript
// Store job-to-socket mapping
activeJobs.set(jobId, socket.id);

// Broadcast only to specific client
socket.to(socket.id).emit('job:update', broadcastPayload);
```

---

## Architecture Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | HTML + Socket.io Client | Displays pipeline in real-time |
| **Server** | Express + Socket.io Server | Receives webhooks, broadcasts to clients |
| **Queue** | Apache Kafka | Decouples server from worker |
| **Worker** | Python + requests | Processes jobs, sends webhook updates |
| **Protocol** | HTTP Webhooks + WebSockets | Real-time bidirectional communication |

---

## Common Issues & Fixes

### Problem: "Cannot GET /" 
**Solution:** Ensure `app.use(express.static(...))` is set before Socket.io routes

### Problem: WebSocket connection refused
**Solution:** Check that server is running and port 3000 is accessible

### Problem: Webhook not received
**Solution:** Verify `WEBHOOK_URL` in worker.py matches your server address

### Problem: Report shows old data
**Solution:** Make sure `currentJobId` is updated before uploading new files

---

## Next Steps

1. **Deploy to cloud** - Test with real infrastructure
2. **Add authentication** - Secure the webhook endpoint
3. **Implement job history** - Store reports in database
4. **Add real OpenAI integration** - Replace mock with production AI
5. **Monitor performance** - Track webhook latency and success rates

Congratulations! Your system now has enterprise-grade real-time telemetry. 🎉
