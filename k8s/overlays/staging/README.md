# Staging Deployment

This directory contains the Kubernetes manifests for the staging environment.

## Security: Restricted CI/CD Access

The GitHub Actions deployment uses a restricted ServiceAccount with minimal permissions limited to the `project-manager-staging` namespace only.

### Setup Instructions

1. **Deploy the ServiceAccount and RBAC**:
   ```bash
   kubectl apply -k .
   ```

2. **Generate the restricted kubeconfig**:
   ```bash
   # Edit the script with your cluster details
   nano generate-ci-kubeconfig.sh

   # Update CLUSTER_NAME and CLUSTER_SERVER variables

   # Run the script
   ./generate-ci-kubeconfig.sh
   ```

3. **Encode and update GitHub secret**:
   ```bash
   cat ci-kubeconfig.yaml | base64 -w 0
   ```
   Update the `KUBECONFIG_B64` secret in GitHub Actions with this encoded content.

### Permissions

The `github-actions-deployer` ServiceAccount has the following permissions in the `project-manager-staging` namespace:

- **Pods**: get, list, watch, create, update, patch, delete
- **Services**: get, list, watch, create, update, patch, delete
- **Deployments**: get, list, watch, create, update, patch, delete
- **ReplicaSets**: get, list, watch, create, update, patch, delete
- **Ingresses**: get, list, watch, create, update, patch, delete
- **Jobs/CronJobs**: get, list, watch, create, update, patch, delete
- **ConfigMaps/Secrets**: get, list, watch, create, update, patch, delete
- **PersistentVolumeClaims**: get, list, watch, create, update, patch, delete
- **SealedSecrets**: get, list, watch, create, update, patch, delete

This ensures the CI/CD pipeline can only manage resources within the staging namespace and cannot affect other parts of the cluster.