# Project Manager

Django-based project/task manager.

## Context / Proof of Concept

This is a **full-stack proof of concept** that has been set up with the help of **AI/LLMs** and includes the required **Kubernetes (Kustomize) configs** to run the full application.

The goal is to effectively manage and operate business activities and services for:

- **ja-zum-leben.at**
- **gerda-ahorner.at**
- **vision.sascha-kohler.at**
- **and additional services/projects**

I also use this project personally to work effectively with **LLMs** and to deepen my understanding of the **Django** framework.

## Staging on Kubernetes (Kustomize)

This repo ships Kubernetes manifests via **kustomize**.

### Prerequisites

- IngressClass: `nginx`
- cert-manager ClusterIssuer: `letsencrypt-prod`
- In-cluster Postgres (StatefulSet + PVC) is shipped in `k8s/overlays/staging`

Staging hostname:

- `pj-staging.ja-zum-leben.at`

### Required secrets

Secrets are managed via **Bitnami SealedSecrets**.

The repo contains:

- `k8s/base/sealedsecret-app.yaml` (`app-secrets`)
- `k8s/overlays/staging/postgres/sealedsecret.yaml` (`postgres-secrets`)

These files must be generated/updated with `kubeseal` for your cluster. Do not commit plaintext Secrets.

#### Install SealedSecrets (once)

If you don't already have it:

```bash
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/latest/download/controller.yaml
```

#### Generate SealedSecrets for staging

Namespace:

```bash
kubectl create namespace project-manager-staging
```

Create the plaintext Secret locally (NOT committed) and seal it:

```bash
kubectl -n project-manager-staging create secret generic app-secrets \
  --from-literal=SECRET_KEY='replace-me' \
  --from-literal=DATABASE_URL='postgres://project_manager:replace-me@postgres:5432/project_manager' \
  --dry-run=client -o yaml \
  | kubeseal --format yaml --namespace project-manager-staging \
  > k8s/base/sealedsecret-app.yaml

Note: If your database password contains URL special characters (e.g. `/`, `@`, `:`), it must be URL-encoded in `DATABASE_URL`. To avoid this, generate a password without special characters (e.g. `openssl rand -hex 32`).

kubectl -n project-manager-staging create secret generic postgres-secrets \
  --from-literal=POSTGRES_DB='project_manager' \
  --from-literal=POSTGRES_USER='project_manager' \
  --from-literal=POSTGRES_PASSWORD='replace-me' \
  --dry-run=client -o yaml \
  | kubeseal --format yaml --namespace project-manager-staging \
  > k8s/overlays/staging/postgres/sealedsecret.yaml

kubectl -n project-manager-staging create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username='<github-username>' \
  --docker-password='<github-pat-with-read:packages>' \
  --dry-run=client -o yaml \
  | kubeseal --format yaml --namespace project-manager-staging \
  > k8s/overlays/staging/ghcr/sealedsecret-ghcr-pull.yaml
```

### Deploy

```bash
kubectl apply -k k8s/overlays/staging
```

### Superuser (staging)

Deploys do not reset the database. The database is only reset if you delete the Postgres PVC.

Create the admin credentials secret locally (NOT committed) and seal it:

```bash
kubectl -n project-manager-staging create secret generic django-admin \
  --from-literal=DJANGO_SUPERUSER_USERNAME='admin' \
  --from-literal=DJANGO_SUPERUSER_EMAIL='admin@example.com' \
  --from-literal=DJANGO_SUPERUSER_PASSWORD='replace-me' \
  --dry-run=client -o yaml \
  | kubeseal --format yaml --namespace project-manager-staging \
  > k8s/overlays/staging/admin/sealedsecret-admin.yaml
```

Then run the one-off Job (idempotent: creates or updates the user):

```bash
kubectl apply -f k8s/overlays/staging/admin/create-superuser-job.yaml
kubectl -n project-manager-staging logs -l job-name=create-superuser --tail=200
```

If you need to re-run it, delete and re-apply the Job:

```bash
kubectl -n project-manager-staging delete job create-superuser
kubectl apply -f k8s/overlays/staging/admin/create-superuser-job.yaml
```

### Translations

Translations are compiled during the Docker image build using `python /app/backend/manage.py compilemessages`.

### GitHub Actions deployment

The workflow `.github/workflows/staging-deploy.yml` builds and pushes an image to GHCR and deploys it to the cluster.

You need to configure the repository secret:

- `KUBECONFIG_B64`: base64-encoded kubeconfig with access to the staging namespace.

## Local development

```bash
# This project uses `uv` for dependency management and running Python commands.

cd backend

# Install/sync dependencies
uv sync

# Database setup
uv run python manage.py migrate

# Run the dev server
uv run python manage.py runserver

# Run tests
uv run pytest

# Compile translations
uv run python manage.py compilemessages
