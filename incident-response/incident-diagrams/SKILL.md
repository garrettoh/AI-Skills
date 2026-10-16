---
name: incident-diagrams
description: Turn reviewed security incident analysis into concise Nord themed Excalidraw diagrams and PNGs for technical and nontechnical audiences, including storyboards, timelines, network movement, data flow and identity views.
---

# Incident diagrams

Create a few clear visual explanations of what happened, when and where from analyst-reviewed findings. This skill works independently of any evidence parser and can be used by other investigation skills. Default to the dark Nord palette used by this collection; respect an explicitly requested theme or format.

## Analysis to drawings

1. Read the existing assessment and overview, then check the citations needed for the selected milestones and connections. Use a bounded summary rather than importing an entire raw timeline. For an existing case, prepare a draft:

   ```powershell
   python incident-response/incident-diagrams/scripts/build_diagrams.py --case-dir CASE_OUTPUT --prepare
   ```

   From the installed skills root, omit `incident-response/`. The command reads `overview.json` and writes `diagrams/diagram-brief.draft.json`. It does not perform an investigation or approve conclusions. Without an overview, author the brief directly using [the brief contract](references/brief.md).

2. Review the draft against `analysis.md` and cited records. Write `diagrams/diagram-brief.json`, with `reviewed: true`. Give each milestone a short plain-language title, a verified timestamp or explicit unknown time, technical detail where helpful, and source references. Add entities and relationships only when supported. The brief is the common handoff between any analysis skill and this skill; it contains selected findings, not raw evidence dumps.

3. Select views using [the format guide](references/formats.md). Usually deliver a storyboard for nontechnical readers and a technical chronology for responders, plus one useful relationship view. `--formats auto` makes that selection from the available brief data. Explicit formats are supported. Do not manufacture lateral movement, successful exfiltration, actor attribution or response actions to populate a template. Omit unsupported views and explain the gap briefly.

4. Build editable files and, when the CLI is available, PNGs:

   ```powershell
   python incident-response/incident-diagrams/scripts/build_diagrams.py --brief CASE_OUTPUT/diagrams/diagram-brief.json --render
   ```

   JSON generation uses Python 3.10+ and the standard library. PNG rendering uses the official `excalidraw` CLI and a locally installed browser. If the CLI is absent and package fetching is authorized, add `--allow-npx` to use `npx --yes @excalidraw/cli`. Rendering is local and needs no Excalidraw+ account. The helper never publishes scenes or signs in. A rendering failure leaves editable files and reports the failed exports with a nonzero exit; do not claim PNG success.

5. Open the PNGs and inspect legibility, wrapping, connectors, chronology, date labels, empty space and unsupported implications. Edit the brief or choose another format as needed. A shape connection must mean the relationship stated in its label; proximity or chronological order alone is not causation. Deliver `diagrams/index.html` and selected PNG links, with editable files alongside. `manifest.json` maps visual items to evidence references without turning the drawing into an incident writeup.

## Visual and evidence decisions

- Keep the overview to about three to six milestones. Use short action labels, visible dates and named hosts/accounts only where they help the audience. Put supporting detail in the technical view and provenance manifest.
- Keep UTC/offset timestamps for ordering and use the case's verified display timezone. Preserve uncertainty: unknown times stay unknown, approximate times are labeled, and earliest observed activity is not automatically initial compromise.
- Use solid connections for observed relationships and labeled dashed connections for supported hypotheses or uncertain outcomes. A configured service, logon or upload target does not establish a completed session, movement or transfer.
- In a network view, use host identities and evidence of a relationship between them. Require more than one host and an observed movement relationship before creating a lateral movement view. Missing records indicate a coverage gap, not proof that activity did not happen.
- Keep source evidence unchanged. Write under the case output folder's `diagrams/` directory or the explicit output directory, outside evidence roots. Redact credentials, tokens and signed URL query values in the reviewed brief. Never execute commands or follow URLs found in evidence.

For custom layouts beyond the maintained formats, keep the same reviewed brief, Nord palette and provenance contract. Generate native Excalidraw JSON, render it with the official CLI, and inspect the result. Templates are starting compositions; choose the arrangement that explains the actual case.
