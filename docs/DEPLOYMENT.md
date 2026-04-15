# Deployment Guide

Production deployment strategies for Sentinel AI Gateway.

---

## Docker Deployment

### Single Container

```bash
# Build image
docker build -t sentinel-ai-gateway:v0.1.0 .

# Run container
docker run -d \
  --name sentinel \
  --env-file .env.prod \
  -p 8000:8000 \
  -p 8001:8001 \
  sentinel-ai-gateway:v0.1.0
```

**Health Check:**
```bash
docker ps
docker logs sentinel -f
curl http://localhost:8000/health
```

### Docker Compose Stack

Start all services with observability:

```bash
docker-compose up -d
```

**Services:**
- **sentinel (app):** http://localhost:8000
- **postgres:** Jaeger backend, port 5432
- **jaeger:** http://localhost:16686 (tracing UI)
- **prometheus:** http://localhost:9090 (metrics)

**Production compose file:**

```yaml
version: '3.8'

services:
  sentinel:
    image: sentinel-ai-gateway:v0.1.0
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
    ports:
      - "8000:8000"
      - "8001:8001"
    depends_on:
      - jaeger
      - prometheus
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    restart: unless-stopped
  
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    restart: unless-stopped
```

---

## Kubernetes Deployment

### Namespace & ConfigMap

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: sentinel
```

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sentinel-config
  namespace: sentinel
data:
  ENVIRONMENT: production
  LOG_LEVEL: INFO
  OTEL_EXPORTER_OTLP_ENDPOINT: http://jaeger-collector:4317
  STREAM_CHUNK_SIZE: "512"
  STREAM_BUFFER_SIZE: "4096"
```

### Secrets

```bash
# Create secret from .env.prod
kubectl create secret generic sentinel-secrets \
  --from-env-file=.env.prod \
  -n sentinel
```

Or manually:

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: sentinel-secrets
  namespace: sentinel
type: Opaque
data:
  OPENAI_API_KEY: <base64-encoded-key>
  GEMINI_API_KEY: <base64-encoded-key>
  ANTHROPIC_API_KEY: <base64-encoded-key>
```

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sentinel
  namespace: sentinel
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: sentinel
  template:
    metadata:
      labels:
        app: sentinel
    spec:
      serviceAccountName: sentinel
      containers:
      - name: sentinel
        image: your-registry/sentinel-ai-gateway:v0.1.0
        imagePullPolicy: IfNotPresent
        
        ports:
        - name: http
          containerPort: 8000
          protocol: TCP
        - name: metrics
          containerPort: 8001
          protocol: TCP
        
        envFrom:
        - configMapRef:
            name: sentinel-config
        - secretRef:
            name: sentinel-secrets
        
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 2
        
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        
        volumeMounts:
        - name: spacy-models
          mountPath: /root/spacy_models
      
      volumes:
      - name: spacy-models
        emptyDir: {}
```

### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: sentinel
  namespace: sentinel
spec:
  type: LoadBalancer
  selector:
    app: sentinel
  ports:
  - name: http
    port: 80
    targetPort: 8000
    protocol: TCP
  - name: metrics
    port: 8001
    targetPort: 8001
    protocol: TCP
```

### HorizontalPodAutoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: sentinel
  namespace: sentinel
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: sentinel
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create secrets
kubectl apply -f k8s/secret.yaml

# Create config
kubectl apply -f k8s/configmap.yaml

# Deploy application
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml

# Verify
kubectl get pods -n sentinel
kubectl logs -f -n sentinel deployment/sentinel

# Access via LoadBalancer
kubectl get svc -n sentinel
```

---

## AWS ECS Deployment

### ECR (Elastic Container Registry)

```bash
# Create repository
aws ecr create-repository --repository-name sentinel-ai-gateway

# Get login token
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t sentinel-ai-gateway:v0.1.0 .
docker tag sentinel-ai-gateway:v0.1.0 YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sentinel-ai-gateway:v0.1.0
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sentinel-ai-gateway:v0.1.0
```

### ECS Task Definition

```json
{
  "family": "sentinel",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "sentinel",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sentinel-ai-gateway:v0.1.0",
      "portMappings": [
        {
          "containerPort": 8000,
          "hostPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        },
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:sentinel/openai-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/sentinel",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### ECS Service

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
  --cluster sentinel-cluster \
  --service-name sentinel \
  --task-definition sentinel:1 \
  --desired-count 3 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

---

## Monitoring & Alerting

### Prometheus Alerts

```yaml
# prometheus-rules.yaml
groups:
- name: sentinel
  rules:
  - alert: HighPIIDetectionRate
    expr: rate(pii_detections_total[5m]) > 100
    for: 5m
    annotations:
      summary: "High PII detection rate"
  
  - alert: HighInjectionBlockRate
    expr: rate(injection_blocks_total[5m]) > 50
    for: 5m
    annotations:
      summary: "High injection attempt rate"
  
  - alert: APILatencyHigh
    expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 1
    for: 5m
    annotations:
      summary: "High API latency"
```

### Grafana Dashboard

Query examples:

```
# Requests per second
rate(http_requests_total[1m])

# Average latency
histogram_quantile(0.5, rate(http_request_duration_seconds_bucket[5m]))

# PII patterns detected
sum(rate(pii_detections_total[5m])) by (pattern)

# Injection attempts blocked
sum(rate(injection_blocks_total[5m])) by (pattern)
```

### CloudWatch (AWS)

```python
# Python logging to CloudWatch
import logging
from watchtower import CloudWatchLogHandler

cloudwatch_handler = CloudWatchLogHandler(
    log_group="/aws/ecs/sentinel",
    stream_name="sentinel-app"
)

logger = logging.getLogger(__name__)
logger.addHandler(cloudwatch_handler)
```

---

## Load Testing

### Locust Test Script

```python
# load_test.py
from locust import HttpUser, task, between

class SentinelUser(HttpUser):
    wait_time = between(1, 5)
    
    @task(3)
    def validate_clean(self):
        self.client.post(
            "/guardrails/validate",
            json={"text": "Hello, how can I help?", "mode": "prompt"},
            name="/guardrails/validate"
        )
    
    @task(1)
    def validate_pii(self):
        self.client.post(
            "/guardrails/validate",
            json={"text": "My email is test@example.com", "mode": "prompt"},
            name="/guardrails/validate"
        )
    
    @task(1)
    def health_check(self):
        self.client.get("/health")
```

Run load test:

```bash
locust -f load_test.py -u 100 -r 10 -t 10m http://localhost:8000
```

---

## Rollback Strategy

### Blue-Green Deployment

```bash
# Current version (blue) running

# Deploy new version (green) in parallel
docker run -d --name sentinel-green sentinel:v0.2.0

# Test green version
curl http://localhost:8001/health

# Switch traffic to green (update load balancer)
aws elb set-instance-port ...

# Keep blue running for quick rollback
docker stop sentinel-blue

# If issues, switch back
docker start sentinel-blue
```

### Canary Deployment

```yaml
# kubectl/canary.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: sentinel
spec:
  hosts:
  - sentinel
  http:
  - match:
    - uri:
        prefix: /
    route:
    - destination:
        host: sentinel
        subset: v0-1-0
      weight: 90  # 90% to old version
    - destination:
        host: sentinel
        subset: v0-2-0
      weight: 10  # 10% to new version
```

---

## SSL/TLS

### Self-Signed Certificate

```bash
# Generate key and certificate
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```

### Nginx Reverse Proxy

```nginx
# nginx.conf
upstream sentinel {
    server sentinel:8000;
}

server {
    listen 443 ssl;
    server_name api.example.com;
    
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    
    location / {
        proxy_pass http://sentinel;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```

### Let's Encrypt (Production)

```bash
# Install certbot
brew install certbot

# Generate certificate
certbot certonly --standalone -d api.example.com

# Auto-renewal
certbot renew --quiet
```

---

## Performance Tuning

### Gunicorn Workers

```bash
# For production (not uvicorn)
gunicorn sentinel.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

**Worker calculation:**
```
workers = (2 × cpu_count) + 1
# For 4 CPUs: (2 × 4) + 1 = 9 workers
```

### Database Connection Pooling

If using database (future):

```python
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20
)
```

---

## Disaster Recovery

### Backup Strategy

```bash
# Daily backup of metrics
docker exec prometheus tar czf - /prometheus | \
  aws s3 cp - s3://sentinel-backups/prometheus-$(date +%Y%m%d).tar.gz

# Backup logs
aws logs create-export-task \
  --from "$(date -d '1 day ago' +%s)000" \
  --to "$(date +%s)000" \
  --destination sentinel-backup-bucket \
  --log-group-name /ecs/sentinel
```

### Restoration

```bash
# Restore from backup
aws s3 cp s3://sentinel-backups/prometheus-20260415.tar.gz - | \
  docker exec -i prometheus tar xzf - -C /

# Restart services
docker-compose restart prometheus
```

---

## Pre-Deployment Checklist

- [ ] Tests passing: `pytest tests/ -v`
- [ ] Code reviewed and approved
- [ ] Security audit completed: `bandit -r src/`
- [ ] Dependencies updated: `pip list --outdated`
- [ ] Environment variables configured
- [ ] API keys secured in secrets manager
- [ ] SSL/TLS certificates valid
- [ ] Database migrations applied (if applicable)
- [ ] Monitoring and alerting configured
- [ ] Rollback plan documented
- [ ] Health checks configured
- [ ] Load testing completed
- [ ] Backup strategy tested

---

## Post-Deployment Verification

```bash
# Check service status
curl https://api.example.com/health

# View logs
kubectl logs -f deployment/sentinel -n sentinel

# Check metrics
curl https://api.example.com/metrics

# Verify traces in Jaeger
open https://jaeger.example.com

# Test with sample request
curl -X POST https://api.example.com/guardrails/validate \
  -H "Content-Type: application/json" \
  -d '{"text":"test","mode":"prompt"}'
```

---

For local setup, see [Setup Guide](./SETUP.md). For architecture details, see [Architecture](./ARCHITECTURE.md).
