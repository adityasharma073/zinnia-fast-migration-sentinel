/**
 * KAFKA SETUP & TESTING GUIDE
 * 
 * Complete guide for running Kafka locally with Docker Compose
 * and testing the Express server integration
 */

// ============================================================================
// 1. QUICK START (3 COMMANDS)
// ============================================================================

/*
# Start Kafka broker in background
docker-compose up -d

# Verify Kafka is running
docker-compose ps

# View logs
docker-compose logs -f kafka

# Stop Kafka
docker-compose down
*/

// ============================================================================
// 2. WHAT IS KRAFT MODE?
// ============================================================================

/*
KRaft = Kafka Raft

Traditional Kafka uses Apache Zookeeper to manage cluster metadata.
KRaft replaces Zookeeper with Raft consensus protocol.

Benefits:
  ✓ Simpler deployment (no Zookeeper needed)
  ✓ Single container instead of two
  ✓ Faster leader election
  ✓ Fewer moving parts
  ✓ Better for development/testing

Our Configuration:
  - Node ID: 1 (single broker)
  - Process Roles: controller,broker (combined role)
  - No Zookeeper required
  - Port 9092: Client connections
  - Port 9093: Controller communications
  - Port 29092: Broker-to-broker
*/

// ============================================================================
// 3. ENVIRONMENT VARIABLES EXPLAINED
// ============================================================================

/*
KAFKA_CFG_NODE_ID=1
  → Unique identifier for this broker node (use 1 for single broker)

KAFKA_CFG_PROCESS_ROLES=controller,broker
  → This node handles both controller (metadata) and broker (data) roles
  → For cluster: controller (metadata only) or broker (data only)

KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=1@kafka:9093
  → Lists all controller nodes for voting
  → Format: id@hostname:port
  → For single broker: just "1@kafka:9093"

KAFKA_CFG_LISTENERS=PLAINTEXT://kafka:29092,CONTROLLER://kafka:9093,PLAINTEXT_HOST://0.0.0.0:9092
  → Network protocols and addresses Kafka listens on
  → Internal (29092): Broker-to-broker
  → Controller (9093): Controller communications
  → Client (9092): External clients

KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
  → What brokers advertise to clients
  → Docker: kafka:29092 (internal)
  → Host: localhost:9092 (external)

KAFKA_CFG_INTER_BROKER_LISTENER_SECURITY_PROTOCOL_MAP
  → Maps listener names to security protocols
  → PLAINTEXT = no authentication/encryption

KAFKA_CFG_OFFSETS_TOPIC_REPLICATION_FACTOR=1
  → Single broker = replication factor 1
  → Cluster: use 3 for production

KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE=true
  → Automatically create topics when first accessed
  → Useful for development/testing
*/

// ============================================================================
// 4. TESTING KAFKA CONNECTION
// ============================================================================

/*
Option 1: Using Docker (inside container)
  docker-compose exec kafka kafka-broker-api-versions.sh --bootstrap-server=localhost:9092

Option 2: Using Node.js + KafkaJS
  // Create test-kafka.js
  import { Kafka } from 'kafkajs';

  const kafka = new Kafka({
    clientId: 'test-client',
    brokers: ['localhost:9092']
  });

  const admin = kafka.admin();
  await admin.connect();
  console.log('✓ Connected to Kafka');
  await admin.disconnect();

  // Run: node test-kafka.js

Option 3: Using curl (not direct, but validates connectivity)
  docker run --rm --network host \
    confluentinc/confluent-kafka:latest \
    kafka-broker-api-versions.sh --bootstrap-server=localhost:9092
*/

// ============================================================================
// 5. CREATE TOPICS FOR TESTING
// ============================================================================

/*
Create the policy-timeline-jobs topic:

docker-compose exec kafka kafka-topics.sh \
  --create \
  --bootstrap-server=localhost:9092 \
  --topic=policy-timeline-jobs \
  --partitions=3 \
  --replication-factor=1

List topics:
docker-compose exec kafka kafka-topics.sh \
  --list \
  --bootstrap-server=localhost:9092

Describe topic:
docker-compose exec kafka kafka-topics.sh \
  --describe \
  --bootstrap-server=localhost:9092 \
  --topic=policy-timeline-jobs
*/

// ============================================================================
// 6. TESTING EXPRESS SERVER + KAFKA
// ============================================================================

/*
Step 1: Start Kafka
  docker-compose up -d

Step 2: Verify Kafka is ready
  docker-compose ps
  (wait for "healthy" status)

Step 3: Create topic
  docker-compose exec kafka kafka-topics.sh \
    --create \
    --bootstrap-server=localhost:9092 \
    --topic=policy-timeline-jobs \
    --partitions=3 \
    --replication-factor=1

Step 4: Start Express server
  npm start

Step 5: Upload files
  curl -X POST http://localhost:3000/api/analyze-timeline \
    -F "statements=@sample_sor.pdf"

Step 6: Verify message in Kafka
  docker-compose exec kafka kafka-console-consumer.sh \
    --bootstrap-server=localhost:9092 \
    --topic=policy-timeline-jobs \
    --from-beginning

Expected output:
  {"jobId":"550e8400-e29b-41d4-a716-446655440000","filePaths":[...],...}
*/

// ============================================================================
// 7. DOCKER COMPOSE COMMANDS
// ============================================================================

/*
Start services
  docker-compose up

Start in background
  docker-compose up -d

View status
  docker-compose ps

View logs
  docker-compose logs -f kafka

View specific log lines
  docker-compose logs -f kafka | grep -i "started"

Execute command in container
  docker-compose exec kafka <command>

Stop services
  docker-compose stop

Remove containers
  docker-compose down

Remove containers + volumes (clean reset)
  docker-compose down -v

View resource usage
  docker stats kafka

Inspect container
  docker-compose exec kafka bash

Rebuild image
  docker-compose up --build
*/

// ============================================================================
// 8. KAFKA CLI TOOLS (Inside Container)
// ============================================================================

/*
List brokers
  kafka-broker-api-versions.sh --bootstrap-server=localhost:9092

Create topic
  kafka-topics.sh --create --bootstrap-server=localhost:9092 --topic=test

List topics
  kafka-topics.sh --list --bootstrap-server=localhost:9092

Describe topic
  kafka-topics.sh --describe --bootstrap-server=localhost:9092 --topic=policy-timeline-jobs

Produce message (manual)
  kafka-console-producer.sh --broker-list=localhost:9092 --topic=policy-timeline-jobs

Consume messages (from start)
  kafka-console-consumer.sh --bootstrap-server=localhost:9092 \
    --topic=policy-timeline-jobs --from-beginning

Consume messages (live only)
  kafka-console-consumer.sh --bootstrap-server=localhost:9092 \
    --topic=policy-timeline-jobs --skip-message-on-error

Check offset
  kafka-consumer-groups.sh --bootstrap-server=localhost:9092 \
    --list
*/

// ============================================================================
// 9. TROUBLESHOOTING
// ============================================================================

/*
Issue: "Connection refused on 9092"
Solution: Check if Kafka container is running
          docker-compose ps
          If not, start it: docker-compose up -d
          Wait 15+ seconds for startup (healthcheck)

Issue: "Topic not found"
Solution: Create the topic before publishing
          docker-compose exec kafka kafka-topics.sh --create ...

Issue: "Broker not available"
Solution: Check logs: docker-compose logs kafka
          Look for startup errors
          Restart: docker-compose restart kafka

Issue: "Container already exists"
Solution: Remove and recreate
          docker-compose down -v
          docker-compose up -d

Issue: "Port 9092 already in use"
Solution: Change port in docker-compose.yml
          ports:
            - "9093:9092"  # Use 9093 instead
          Update server.js KAFKA_BROKERS accordingly

Issue: "Out of memory"
Solution: Increase Docker resources
          Preferences → Resources → Memory
          Allocate more GB to Docker

Issue: "Slow message consumption"
Solution: Verify broker health
          docker-compose exec kafka bash
          kafka-broker-api-versions.sh --bootstrap-server=localhost:9092
*/

// ============================================================================
// 10. PRODUCTION VS LOCAL
// ============================================================================

/*
Local Setup (this docker-compose.yml):
  - Single broker
  - No replication
  - KRaft mode for simplicity
  - Auto topic creation enabled
  - Perfect for development/testing

Production Setup (would need):
  - 3+ brokers (high availability)
  - Replication factor 3
  - Persistence volumes on SSD
  - Monitoring (Prometheus)
  - SSL/TLS encryption
  - Authentication (SASL)
  - Backup strategy
  - Disaster recovery plan
  - Kafka Connect for integrations
  - Schema Registry for data contracts
*/

// ============================================================================
// 11. MONITORING KAFKA
// ============================================================================

/*
Monitor in real-time
  docker stats kafka

Check broker info
  docker-compose exec kafka kafka-broker-api-versions.sh --bootstrap-server=localhost:9092

Check cluster
  docker-compose exec kafka kafka-metadata.sh --snapshot /var/lib/kafka/data/__cluster_metadata-0/00000000000000000000.log

View config
  docker-compose exec kafka kafka-configs.sh --bootstrap-server=localhost:9092 --entity-type brokers --entity-name 1 --describe

Consumer lag
  docker-compose exec kafka kafka-consumer-groups.sh \
    --bootstrap-server=localhost:9092 \
    --group=test-group \
    --describe
*/

// ============================================================================
// 12. WORKFLOW - FROM DOCKER TO TESTING
// ============================================================================

/*
Complete workflow:

1. Start Docker Compose
   docker-compose up -d
   
2. Wait for health check
   docker-compose ps  # Wait for "healthy"
   
3. Create topic
   docker-compose exec kafka kafka-topics.sh --create \
     --bootstrap-server=localhost:9092 \
     --topic=policy-timeline-jobs --partitions=3 --replication-factor=1
   
4. Start consumer (monitoring)
   docker-compose exec kafka kafka-console-consumer.sh \
     --bootstrap-server=localhost:9092 \
     --topic=policy-timeline-jobs \
     --from-beginning

5. In another terminal, start Express server
   npm start

6. In another terminal, upload files
   curl -X POST http://localhost:3000/api/analyze-timeline \
     -F "statements=@sample_sor.pdf" \
     -F "statements=@sample_data.xml"

7. Watch consumer terminal for messages
   (Should show JSON payload with jobId)

8. Verify Express response
   HTTP 202 Accepted with jobId

9. Stop everything
   docker-compose down
*/

export {};
