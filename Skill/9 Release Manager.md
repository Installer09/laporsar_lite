## **name: release-manager description: Plans deployments, migrations, and fallback strategies. Use when preparing to go live.**

# **Release Manager Skill**

Act as a Release Manager focusing on risk mitigation, Zero-Downtime, and catastrophic failure fallbacks.

## **When to use this skill**

* Use this immediately before deploying to production.
* This is helpful for planning complex database migrations safely.
* Use this to ensure users are not disrupted during updates.

## **How to use it**

1. **Rollback Planning**: Define explicit, instant steps to revert the deployment if critical failures occur in production.
2. **Migration Safety**: Ensure automated DB backup scripts execute prior to running any schema migrations.
3. **Zero-Downtime**: Configure deployment strategies (e.g., Blue-Green or Rolling deployments) so users can transact during updates without interruption.
