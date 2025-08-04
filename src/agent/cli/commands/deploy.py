from pathlib import Path

import click
import yaml


@click.command()
@click.option(
    "--type", "-t", type=click.Choice(["docker", "k8s", "helm"]), required=True, help="Deployment type to generate"
)
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--port", "-p", default=8080, help="Application port (default: 8080)")
@click.option("--replicas", "-r", default=1, help="Number of replicas (k8s/helm only)")
@click.option("--image-name", help="Docker image name")
@click.option("--image-tag", default="latest", help="Docker image tag")
def deploy(type: str, output: str | None, port: int, replicas: int, image_name: str | None, image_tag: str):
    """Generate deployment files for your agent.

    Supported deployment types:
    - docker: Dockerfile and docker-compose.yml
    - k8s: Kubernetes manifests
    - helm: Helm chart
    """
    # Check if we're in an agent project
    if not Path("agentup.yml").exists():
        click.echo(click.style("✗ Error: No agentup.yml found!", fg="red"))
        click.echo("Are you in an agent project directory?")
        return

    # Load agent config to get name
    try:
        with open("agentup.yml", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            agent_name = config.get("agent", {}).get("name", "agent")
            agent_name_clean = agent_name.lower().replace(" ", "-").replace("_", "-")
    except (yaml.YAMLError, OSError, ValueError) as e:
        click.echo(click.style(f"✗ Error loading agentup.yml: {str(e)}", fg="red"))
        agent_name = "agent"
        agent_name_clean = "agent"

    # Set default image name if not provided
    if not image_name:
        image_name = agent_name_clean

    # Set output directory
    output_dir = Path(output) if output else Path(".")

    click.echo(f"📦 Generating {type} deployment files...")

    try:
        if type == "docker":
            generate_docker_files(output_dir, agent_name, image_name, port)
        elif type == "k8s":
            generate_k8s_files(output_dir, agent_name_clean, image_name, image_tag, port, replicas)
        elif type == "helm":
            generate_helm_files(output_dir, agent_name_clean, image_name, port)

        click.echo(f"\n{click.style('✓ Deployment files generated successfully!', fg='green', bold=True)}")

        # Show next steps
        click.echo("\nNext steps:")
        if type == "docker":
            click.echo(f"1. Build image: docker build -t {image_name}:{image_tag} .")
            click.echo(f"2. Run container: docker run -p {port}:{port} {image_name}:{image_tag}")
            click.echo("3. Or use docker-compose: docker-compose up")
        elif type == "k8s":
            k8s_dir = output_dir / "k8s" if output_dir != Path(".") else Path("k8s")
            click.echo(f"1. Apply manifests: kubectl apply -f {k8s_dir}/")
            click.echo(f"2. Check status: kubectl get pods -l app={agent_name_clean}")
            click.echo(f"3. Access service: kubectl port-forward svc/{agent_name_clean} {port}:{port}")
        elif type == "helm":
            helm_dir = output_dir / "helm" if output_dir != Path(".") else Path("helm")
            click.echo(f"1. Install chart: helm install {agent_name_clean} {helm_dir}/")
            click.echo(f"2. Check status: helm status {agent_name_clean}")
            click.echo(f"3. Upgrade: helm upgrade {agent_name_clean} {helm_dir}/")

    except Exception as e:
        click.echo(f"{click.style('✗ Error generating files:', fg='red')} {str(e)}")


def _write_deployment_file(file_path: Path, content: str) -> None:
    """Writes content to a file and prints a success message."""
    try:
        file_path.write_text(content, encoding="utf-8")
        click.echo(f"{click.style('✓', fg='green')} Created {file_path}")
    except OSError as e:
        click.echo(f"{click.style('✗', fg='red')} Error creating {file_path}: {e}")
        raise


def generate_docker_files(output_dir: Path, agent_name: str, image_name: str, port: int):
    # Create Dockerfile
    dockerfile_content = f"""FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install Python dependencies
RUN uv sync --no-dev || pip install -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE {port}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:{port}/health || exit 1

# Run application
CMD ["uv", "run", "uvicorn", "src.agent.main:app", "--host", "0.0.0.0", "--port", "{port}"]
"""

    _write_deployment_file(output_dir / "Dockerfile", dockerfile_content)

    # Create docker-compose.yml
    compose_content = f"""version: '3.8'

services:
  {image_name}:
    build: .
    image: {image_name}:latest
    container_name: {image_name}
    ports:
      - "{port}:{port}"
    environment:
      - API_KEY=${{API_KEY:-your-api-key}}
      - DEBUG=${{DEBUG:-false}}
    volumes:
      - ./agentup.yml:/app/agentup.yml:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

# Optional services
# Uncomment and configure as needed

#  valkey:
#    image: valkey/valkey:7-alpine
#    container_name: {image_name}-valkey
#    restart: unless-stopped
#    volumes:
#      - valkey_data:/data
#volumes:
#  valkey_data:
"""

    _write_deployment_file(output_dir / "docker-compose.yml", compose_content)

    # Create .dockerignore
    dockerignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/
env/

# Testing
.coverage
htmlcov/
.pytest_cache/
tests/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store

# Project
.env
*.log
.git/
.gitignore
README.md
docs/
k8s/
helm/
"""

    _write_deployment_file(output_dir / ".dockerignore", dockerignore_content)


def generate_k8s_files(output_dir: Path, agent_name: str, image_name: str, image_tag: str, port: int, replicas: int):
    # Create k8s directory
    k8s_dir = output_dir / "k8s"
    k8s_dir.mkdir(exist_ok=True)

    # Deployment manifest
    deployment_content = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {agent_name}
  labels:
    app: {agent_name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {agent_name}
  template:
    metadata:
      labels:
        app: {agent_name}
    spec:
      containers:
      - name: {agent_name}
        image: {image_name}:{image_tag}
        ports:
        - containerPort: {port}
          protocol: TCP
        env:
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: {agent_name}-secrets
              key: api-key
        - name: DEBUG
          value: "false"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: {port}
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: {port}
          initialDelaySeconds: 10
          periodSeconds: 10
        volumeMounts:
        - name: config
          mountPath: /app/agentup.yml
          subPath: agentup.yml
      volumes:
      - name: config
        configMap:
          name: {agent_name}-config
"""

    _write_deployment_file(k8s_dir / "deployment.yaml", deployment_content)

    # Service manifest
    service_content = f"""apiVersion: v1
kind: Service
metadata:
  name: {agent_name}
  labels:
    app: {agent_name}
spec:
  type: ClusterIP
  ports:
  - port: {port}
    targetPort: {port}
    protocol: TCP
    name: http
  selector:
    app: {agent_name}
"""

    _write_deployment_file(k8s_dir / "service.yaml", service_content)

    # ConfigMap manifest
    configmap_content = f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {agent_name}-config
data:
  agentup.yml: |
    # This is a placeholder - replace with your actual agentup.yml content
    # You can also use kubectl create configmap to create this from your file:
    # kubectl create configmap {agent_name}-config --from-file=agentup.yml

    api_key: ${{API_KEY}}
    agent:
      name: {agent_name}
      description: A2A Agent deployed on Kubernetes
      version: 0.5.1
    skills:
      - skill_id: hello_world
        name: Hello World
        description: A simple greeting
        input_mode: text
        output_mode: text
"""

    _write_deployment_file(k8s_dir / "configmap.yaml", configmap_content)

    # Secret manifest
    secret_content = f"""apiVersion: v1
kind: Secret
metadata:
  name: {agent_name}-secrets
type: Opaque
stringData:
  api-key: your-api-key-here
  # Add other secrets as needed
  # openai-api-key: your-openai-key
"""

    _write_deployment_file(k8s_dir / "secret.yaml", secret_content)

    # Ingress manifest (optional)
    ingress_content = f"""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {agent_name}
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
  - host: {agent_name}.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {agent_name}
            port:
              number: {port}
"""

    _write_deployment_file(k8s_dir / "ingress.yaml", ingress_content)


def generate_helm_files(output_dir: Path, agent_name: str, image_name: str, port: int):
    # Create helm directory structure
    helm_dir = output_dir / "helm" / agent_name
    templates_dir = helm_dir / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)

    # Chart.yaml
    chart_content = f"""apiVersion: v2
name: {agent_name}
description: A Helm chart for {agent_name} A2A Agent
type: application
version: 0.5.1
appVersion: "0.5.1"
keywords:
  - a2a
  - agent
  - ai
maintainers:
  - name: Your Name
    email: your.email@example.com
"""

    _write_deployment_file(helm_dir / "Chart.yaml", chart_content)

    # values.yaml
    values_content = f"""# Default values for {agent_name}

replicaCount: 1

image:
  repository: {image_name}
  pullPolicy: IfNotPresent
  tag: "latest"

imagePullSecrets: []
nameOverride: ""
fullnameOverride: ""

service:
  type: ClusterIP
  port: {port}

ingress:
  enabled: false
  className: "nginx"
  annotations: {{}}
  hosts:
    - host: {agent_name}.local
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls: []

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 80
  targetMemoryUtilizationPercentage: 80

nodeSelector: {{}}
tolerations: []
affinity: {{}}

# Application configuration
config:
  apiKey: "your-api-key-here"
  debug: false

# External services
services:
  valkey:
    enabled: false
    host: valkey
    port: 6379

# Agent configuration (will be mounted as agentup.yml)
agentConfig: |
  api_key: ${{API_KEY}}
  agent:
    name: {agent_name}
    description: A2A Agent deployed with Helm
    version: 0.5.1
  skills:
    - skill_id: hello_world
      name: Hello World
      description: A simple greeting
      input_mode: text
      output_mode: text
"""

    _write_deployment_file(helm_dir / "values.yaml", values_content)

    # Create template files
    create_helm_templates(templates_dir, agent_name)

    # .helmignore
    helmignore_content = """.DS_Store
.git/
.gitignore
.vscode/
*.swp
*.bak
*.tmp
*.orig
*~
.project
.idea/
*.tmproj
.vscode/
"""

    _write_deployment_file(helm_dir / ".helmignore", helmignore_content)


def create_helm_templates(templates_dir: Path, agent_name: str):
    # _helpers.tpl
    helpers_content = f"""{{{{/*
Expand the name of the chart.
*/}}}}
{{{{- define "{agent_name}.name" -}}}}
{{{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Create a default fully qualified app name.
*/}}}}
{{{{- define "{agent_name}.fullname" -}}}}
{{{{- if .Values.fullnameOverride }}}}
{{{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- $name := default .Chart.Name .Values.nameOverride }}}}
{{{{- if contains $name .Release.Name }}}}
{{{{- .Release.Name | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}
{{{{- end }}}}
{{{{- end }}}}

{{{{/*
Create chart name and version as used by the chart label.
*/}}}}
{{{{- define "{agent_name}.chart" -}}}}
{{{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Common labels
*/}}}}
{{{{- define "{agent_name}.labels" -}}}}
helm.sh/chart: {{{{ include "{agent_name}.chart" . }}}}
{{{{ include "{agent_name}.selectorLabels" . }}}}
{{{{- if .Chart.AppVersion }}}}
app.kubernetes.io/version: {{{{ .Chart.AppVersion | quote }}}}
{{{{- end }}}}
app.kubernetes.io/managed-by: {{{{ .Release.Service }}}}
{{{{- end }}}}

{{{{/*
Selector labels
*/}}}}
{{{{- define "{agent_name}.selectorLabels" -}}}}
app.kubernetes.io/name: {{{{ include "{agent_name}.name" . }}}}
app.kubernetes.io/instance: {{{{ .Release.Name }}}}
{{{{- end }}}}
"""

    _write_deployment_file(templates_dir / "_helpers.tpl", helpers_content)

    # deployment.yaml template
    deployment_content = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{ include "{agent_name}.fullname" . }}}}
  labels:
    {{{{- include "{agent_name}.labels" . | nindent 4 }}}}
spec:
  {{{{- if not .Values.autoscaling.enabled }}}}
  replicas: {{{{ .Values.replicaCount }}}}
  {{{{- end }}}}
  selector:
    matchLabels:
      {{{{- include "{agent_name}.selectorLabels" . | nindent 6 }}}}
  template:
    metadata:
      labels:
        {{{{- include "{agent_name}.selectorLabels" . | nindent 8 }}}}
    spec:
      {{{{- with .Values.imagePullSecrets }}}}
      imagePullSecrets:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      containers:
      - name: {{{{ .Chart.Name }}}}
        image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag | default .Chart.AppVersion }}}}"
        imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
        ports:
        - name: http
          containerPort: {{{{ .Values.service.port }}}}
          protocol: TCP
        env:
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: {{{{ include "{agent_name}.fullname" . }}}}-secrets
              key: api-key
        - name: DEBUG
          value: "{{{{ .Values.config.debug }}}}"
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 10
          periodSeconds: 10
        resources:
          {{{{- toYaml .Values.resources | nindent 12 }}}}
        volumeMounts:
        - name: config
          mountPath: /app/agentup.yml
          subPath: agentup.yml
      volumes:
      - name: config
        configMap:
          name: {{{{ include "{agent_name}.fullname" . }}}}-config
      {{{{- with .Values.nodeSelector }}}}
      nodeSelector:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      {{{{- with .Values.affinity }}}}
      affinity:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      {{{{- with .Values.tolerations }}}}
      tolerations:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
"""

    _write_deployment_file(templates_dir / "deployment.yaml", deployment_content)

    # Other template files would be created similarly...
    # For brevity, I'll create just the essential ones

    # service.yaml template
    service_content = f"""apiVersion: v1
kind: Service
metadata:
  name: {{{{ include "{agent_name}.fullname" . }}}}
  labels:
    {{{{- include "{agent_name}.labels" . | nindent 4 }}}}
spec:
  type: {{{{ .Values.service.type }}}}
  ports:
  - port: {{{{ .Values.service.port }}}}
    targetPort: http
    protocol: TCP
    name: http
  selector:
    {{{{- include "{agent_name}.selectorLabels" . | nindent 4 }}}}
"""

    _write_deployment_file(templates_dir / "service.yaml", service_content)

    # configmap.yaml template
    configmap_content = f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {{{{ include "{agent_name}.fullname" . }}}}-config
  labels:
    {{{{- include "{agent_name}.labels" . | nindent 4 }}}}
data:
  agentup.yml: |
{{{{- .Values.agentConfig | nindent 4 }}}}
"""

    _write_deployment_file(templates_dir / "configmap.yaml", configmap_content)

    # secret.yaml template
    secret_content = f"""apiVersion: v1
kind: Secret
metadata:
  name: {{{{ include "{agent_name}.fullname" . }}}}-secrets
  labels:
    {{{{- include "{agent_name}.labels" . | nindent 4 }}}}
type: Opaque
stringData:
  api-key: {{{{ .Values.config.apiKey | quote }}}}
"""

    _write_deployment_file(templates_dir / "secret.yaml", secret_content)
