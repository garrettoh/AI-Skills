# Choosing incident views

| Format | Audience and question | Input needed |
| --- | --- | --- |
| `storyboard` | Nontechnical: what happened, in a few beats? | Three to six reviewed milestones with dates; chronological sequence, no causal arrows |
| `timeline` | Mixed: when did the important events happen? | Selected events with verified or explicitly unknown times |
| `technical` | Responders: how do host, account and process activity line up? | Selected events with a short `lane` and technical description |
| `network` | Responders: which hosts were connected, when, using what access? | Two or more host entities and an observed `movement` relationship with citations; a timestamp or explicit unknown time |
| `data-flow` | Mixed: where did files or information come from and go? | Entity relationships categorized as `data`; distinguish download, collection, attempted transfer and confirmed receipt |
| `identity` | Responders: which identity had or used what access? | Relationships categorized as `identity`; distinguish assignment, authentication, privilege and demonstrated access |

`auto` chooses storyboard and technical chronology when events exist, then the first supported relationship view in network, data-flow, identity order. Explicit requests can select any supported combination. Unsupported relationship formats are listed as skipped in the manifest instead of producing an empty or invented diagram.

For malware, phishing, business email compromise, cloud account abuse, ransomware or insider investigations, use the same brief with case-specific event labels and entity types. For example, a cloud case might use mailbox, session, application and storage entities; a ransomware case might use workstation, server, account and share entities. Do not require Windows or endpoint artifacts.

Nord styling uses polar-night backgrounds (`#2E3440`, `#3B4252`), snow text (`#ECEFF4`, `#D8DEE9`) and restrained frost accents. Frost marks observed activity, green supported conclusions, amber uncertainty and muted gray unknowns. Status text and line style also communicate meaning so the color is not the sole signal.

Avoid repeating the same diagram in several cosmetic styles. Deliver complementary views of the same findings. A short storyboard, a dated technical chronology and one supported relationship graph usually provide a useful set.
