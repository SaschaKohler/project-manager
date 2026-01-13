#!/bin/bash

# Script to generate a kubeconfig for GitHub Actions CI/CD
# This creates a kubeconfig that only has access to the project-manager-staging namespace

set -e

NAMESPACE="project-manager-staging"
SERVICE_ACCOUNT="github-actions-deployer"
CLUSTER_NAME="your-cluster-name"  # Replace with your actual cluster name
CLUSTER_SERVER="https://your-cluster-endpoint"  # Replace with your cluster endpoint

echo "Generating kubeconfig for GitHub Actions CI/CD..."

# Get the service account token
SECRET_NAME=$(kubectl get serviceaccount $SERVICE_ACCOUNT -n $NAMESPACE -o jsonpath='{.secrets[0].name}')
TOKEN=$(kubectl get secret $SECRET_NAME -n $NAMESPACE -o jsonpath='{.data.token}' | base64 -d)

# Get the cluster CA certificate
CA_CERT=$(kubectl config view --minify --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')

# Create the kubeconfig
cat > ci-kubeconfig.yaml << EOF
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
echo "cat ci-kubeconfig.yaml | base64 -w 0"
echo ""
echo "Update the KUBECONFIG_B64 secret in GitHub with the encoded content."