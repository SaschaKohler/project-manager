# Project Manager

Django-based project/task manager.

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

### GitHub Actions deployment

The workflow `.github/workflows/staging-deploy.yml` builds and pushes an image to GHCR and deploys it to the cluster.

You need to configure the repository secret:

- `KUBECONFIG_B64`: base64-encoded kubeconfig with access to the staging namespace.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver
```
