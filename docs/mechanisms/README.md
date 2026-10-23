# Mechanisms: from biology to a clinical outcome

The candidate report ranks drugs by how well studied they are. It cannot say *why* a treatment should work, or what would show that it does not. This layer carries that, one hypothesis at a time.

Records live in [`curation/mechanisms.json`](../../curation/mechanisms.json) and are checked by `vitiligo mechanism verify`.

```bash
vitiligo mechanism list                      # every hypothesis, and what its support reaches
vitiligo mechanism show trm-il15-relapse     # the chain, the evidence, the rivals, the test
vitiligo mechanism verify                    # the gate (needs the local corpus)
vitiligo mechanism verify --structure-only   # the gate without the corpus
vitiligo mechanism seal <id>                 # freeze the claim, context and test
```

## The chain

Each record states all five levels. A record that stops at the mechanism is an observation; one that stops at the intervention is a plan without a measurement.

| Level | What it states |
|---|---|
| **Biological state** | What is happening in the tissue |
| **Mechanistic hypothesis** | A pathway is necessary for that process, in a defined context |
| **Intervention hypothesis** | Altering that pathway changes the process |
| **Experimental outcome** | What we would measure, and in what |
| **Clinical outcome** | Which of the four outcomes in [`success.md`](../success.md) it moves |

## Two rules the gate enforces

**1. A claim may not outrank its evidence.** Every source carries where it sits on the causal ladder, weakest first:

| Rung | Means |
|---|---|
| `association` | Observed together: expression, abundance, correlation |
| `human_genetics` | An inherited variant associates with the disease |
| `perturbation_in_vitro` | The pathway was altered in cells |
| `perturbation_in_animal` | Altered in an animal model, with an effect |
| `perturbation_in_human` | Altered in people, with a measured effect |

"Supporting evidence reaches" is the strongest rung any **supporting** source reaches. It is computed, never curated, so a hypothesis resting on expression data cannot read as a demonstrated mechanism. The corpus has the last word: `vitiligo mechanism verify` classifies each cited document and rejects a claim of perturbation in people on a mouse study.

Each source also takes a stance:

- **supports** — evidence for the claim.
- **contradicts** — evidence against it.
- **bounds** — relevant and must be read, but it tests a different question or context. It limits what the claim may assume without supporting or contradicting it. A human trial of the right drug asking the wrong question belongs here, and it does not raise what the support reaches.

**2. A claim must be able to fail.** Every record names the strongest competing explanation and how to tell it from the claim, then states what we expect to see if the claim is right, what we expect if it is wrong, and which hypothesis survives which result. The gate rejects a record whose two expectations are the same, or that names no rival.

## The gate

`vitiligo mechanism verify` reports a problem when:

- a level of the chain, a context field, or a part of the test is empty;
- `if_correct` and `if_incorrect` are the same, so the claim cannot fail;
- no competing explanation is named, or one has no way to tell it apart;
- there is no supporting evidence, or a stance or causal level is unknown;
- a citation is malformed or **does not resolve in the local corpus**;
- a causal level is impossible for what the corpus says the source is;
- the outcome is not one of the four in [`success.md`](../success.md);
- a sealed record's claim, context or test has changed since it was sealed.

It exits non-zero when anything fails, so it can gate a commit.

## Sealing

A seal is a SHA-256 over the **falsifiable core**: the claim, the context and the test. Evidence and notes stay editable, because sources accumulate and a record should be allowed to grow; what must not move is what the record predicts and how it will be judged. This follows the [pre-registrations](../model-v0.4-preregistration.md), where amendments are appended rather than rewritten.

Sealing is refused while the gate fails, and re-sealing an already sealed record is refused.

A hypothesis is sealed when its test names an instrument that can no longer be tuned. Neither record below is sealed yet, for that reason: both tests rest on a score that is still to be defined.

## The records

| ID | Outcome | Claim | Support reaches | Status |
|---|---|---|---|---|
| `trm-il15-relapse` | 3. Last | IL-15-dependent resident memory T cells are necessary for depigmentation to restart after treatment stops | Perturbation in animals | draft |
| `follicular-reservoir-limits-repigmentation` | 2. Restore pigment | Where the follicular melanocyte reservoir is absent or unresponsive, suppressing the attack is not enough to repigment | Association | draft |

Both sit at the honest state of the field: the first rests on a mouse perturbation ([Richmond 2018](https://pubmed.ncbi.nlm.nih.gov/30021889/)) and human data that only bound it; the second rests on association alone. Neither has been tested, and the gate makes that visible rather than letting a confident sentence hide it.

`trm-il15-relapse` is roadmap item 3.6. Its test is the first use of this layer: derive a resident-memory score, seal it, then test it on skin sampled after treatment stops.

## What this is not

It is not a mechanism-wide knowledge graph. A graph of genes, cells and pathways would be infrastructure built before anything has been tested, and [`success.md`](../success.md) asks for the minimum an answer needs. These records are files: readable, reviewable, and verifiable without a database. Structure gets added when several hypotheses need connecting, not before.

The [knowledge graph](../architecture.md) stays what it is: deterministic links seeded from priors and trials, which is why those edges no longer score in the candidate report ([roadmap](../roadmap.md#checks-on-what-exists)).
