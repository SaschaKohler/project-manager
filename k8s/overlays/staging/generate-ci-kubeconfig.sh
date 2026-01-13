#!/bin/bash

# Script to generate a kubeconfig for GitHub Actions CI/CD
# This creates a kubeconfig that only has access to the project-manager-staging namespace

set -euo pipefail

NAMESPACE="project-manager-staging"
SERVICE_ACCOUNT="github-actions-deployer"
CLUSTER_NAME="default"                     # Replace with your actual cluster name
CLUSTER_SERVER="https://87.106.81.52:6443" # Replace with your cluster endpoint

echo "Generating kubeconfig for GitHub Actions CI/CD..."

# Get the service account token
TOKEN_DURATION="${TOKEN_DURATION:-}"
TOKEN=""

SECRET_NAME="$(kubectl -n "$NAMESPACE" get secret -o jsonpath="{range .items[?(@.type=='kubernetes.io/service-account-token')]}{.metadata.name}{'\t'}{.metadata.annotations.kubernetes\\.io/service-account\\.name}{'\n'}{end}" | awk -v sa="$SERVICE_ACCOUNT" '$2==sa {print $1; exit}')"
if [ -n "${SECRET_NAME:-}" ]; then
  TOKEN="$(kubectl -n "$NAMESPACE" get secret "$SECRET_NAME" -o jsonpath='{.data.token}' | base64 -d)"
fi

if [ -z "$TOKEN" ] && kubectl -n "$NAMESPACE" create token "$SERVICE_ACCOUNT" --help >/dev/null 2>&1; then
  if [ -n "$TOKEN_DURATION" ]; then
    TOKEN="$(kubectl -n "$NAMESPACE" create token "$SERVICE_ACCOUNT" --duration="$TOKEN_DURATION" 2>/dev/null || true)"
  else
    TOKEN="$(kubectl -n "$NAMESPACE" create token "$SERVICE_ACCOUNT" 2>/dev/null || true)"
  fi
fi

if [ -z "$TOKEN" ]; then
  SECRET_NAME="$(kubectl get serviceaccount "$SERVICE_ACCOUNT" -n "$NAMESPACE" -o jsonpath='{.secrets[0].name}' 2>/dev/null || true)"
  if [ -n "${SECRET_NAME:-}" ]; then
    TOKEN="$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.token}' 2>/dev/null | base64 -d)"
  fi
fi

if [ -z "$TOKEN" ]; then
  echo "ERROR: Could not obtain a service account token for '$SERVICE_ACCOUNT' in namespace '$NAMESPACE'." >&2
  echo "If you're on Kubernetes v1.24+, ServiceAccount token Secrets are not auto-created. You can:" >&2
  echo "- use 'kubectl create token' (recommended, but token may expire), or" >&2
  echo "- create a kubernetes.io/service-account-token Secret bound to the service account." >&2
  exit 1
fi

# Get the cluster CA certificate
CA_CERT=$(kubectl config view --minify --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')

if [ -z "$CA_CERT" ]; then
  echo "ERROR: Could not read cluster certificate-authority-data from current kubeconfig." >&2
  exit 1
fi

# Create the kubeconfig
cat >ci-kubeconfig.yaml <<EOF
apiVersion: v1
kind: Config
clusters:
- cluster:
    certificate-authority-data: $CA_CERT
    server: $CLUSTER_SERVER
  name: $CLUSTER_NAME
contexts:
- context:
    cluster: $CLUSTER_NAME
    namespace: $NAMESPACE
    user: $SERVICE_ACCOUNT
  name: ci-context
current-context: ci-context
users:
- name: $SERVICE_ACCOUNT
  user:
    token: $TOKEN
EOF

echo "Kubeconfig generated: ci-kubeconfig.yaml"
echo "To encode for GitHub secret:"
echo "cat ci-kubeconfig.yaml | base64 | tr -d '\\n'"
echo "(Linux alternative: cat ci-kubeconfig.yaml | base64 -w 0)"
echo ""
echo "Update the KUBECONFIG_B64 secret in GitHub with the encoded content."

