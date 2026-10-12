# AI-Skills

Modular forensic and incident response skills.

[Shared investigations](incident-response/README.md#shared-investigations) coordinate KAPE and Hindsight browser JSONL analysis, exchange discovered leads, and deliver a normalized timeline under the working directory's `agent_output`. Hindsight and the main coordinator have independent folders under incident-response.

## Incident response

[KAPE CSV analysis](incident-response/kape_analysis/) contains the KAPE artifact skills, schema router, streaming CSV helpers, and cross-artifact timeline tools. See its [usage guide](incident-response/kape_analysis/README.md).

Install any individual skill or the default full collection with the [shared installer](incident-response/README.md#installation). It shows selected skills and required helpers and asks for approval before copying. The [agent installation workflow](incident-response/AGENT_INSTALL.md) follows the same preview, approval and verification process.
