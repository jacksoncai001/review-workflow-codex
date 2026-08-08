# Domain profiles

The core workflow is domain-independent for engineering and natural science. A domain YAML profile adds vocabulary and scientific boundaries; it cannot change phase order, privacy policy, evidence ceilings, citation integrity, or human gates.

## Allowed fields

- `profile_id`, `display_name`, `domains`;
- `synonyms`: canonical concept to alternative terms;
- `inclusion_clues` and `exclusion_clues`;
- `evidence_priorities`;
- `measurement_chains`: domain-specific input → phenomenon → sensor → representation → inference → decision sequences;
- `newcomer_concepts` that must be explained;
- `prohibited_equivalences` that must not be assumed.

Start from `engineering-generic.yaml` or `natural-science-generic.yaml`. Add a narrower profile only when recurring terminology or evidence rules materially affect retrieval, classification, or claim review. Keep project-specific conclusions and private manuscript language in the project workspace, never in a reusable plugin profile.

## Review-type emphasis

- Narrative: coherent development of a bounded topic, with explicit selection limits and no claim of exhaustive screening.
- Critical: competing interpretations, assumptions, contradictions, and consequences for future work.
- Technical: methods, measurement chains, validation designs, performance boundaries, comparability, and deployment implications.

Reject a request to relabel these outputs as systematic review or meta-analysis without a separately suitable methodology.
