# DAO Proposal Reviewer

An **Intelligent Contract on [GenLayer](https://www.genlayer.com)** that lets AI validators review DAO governance proposals against the DAO's own rules *before* they go to a vote.

Anyone can submit a proposal. The contract asks the validator set to evaluate it for completeness, rule compliance, red flags, and measurable deliverables, then records a verdict, a score, and the concrete issues found. Validators must agree through GenLayer's equivalence-principle consensus, so no single reviewer decides the outcome.

- **Contract (Studionet):** [`0xA01EDAE3935B5d1d857A57de18C5260a92303D26`](https://explorer-studio.genlayer.com/address/0xA01EDAE3935B5d1d857A57de18C5260a92303D26) (redeployed with versioned history)
- **Live frontend:** `https://isnoop4.github.io/Dao-proposal-reviewer/`

## How it works

1. A proposer calls `submit_proposal(title, description, reference_url)`. The proposal is created as revision 0 with status `PENDING`.
2. Anyone calls `review_proposal(id)`. Each validator runs an LLM review (and optionally reads the reference URL), returning JSON.
3. Validators reach consensus with `prompt_comparative`: the `verdict` must match exactly and the `score` may differ by at most 10 points.
4. The result is stored under that revision, and the status becomes `PASS`, `REVISE`, or `REJECT`.
5. If the verdict is `REVISE`, the proposer calls `revise_proposal(id, new_description)`. This creates a **new revision** (status `PENDING`); earlier revisions and their reviews are kept. Then call `review_proposal(id)` again.

| Verdict | Meaning |
|---------|---------|
| `PASS` | Ready to move to a vote |
| `REVISE` | Has fixable shortcomings |
| `REJECT` | Violates DAO rules or is too risky |

Each review contains `verdict`, `score` (0-100), `issues` (up to 5), and a one-sentence `summary`.

## Revision flow and audit trail

`Submit -> Review -> (REVISE) -> Revise -> Re-review`

- Revisions are **never overwritten**. Each revision has its own version record and its own review.
- Only the original proposer can revise, and only when the current verdict is `REVISE`. `PASS` and `REJECT` are final.
- `review_proposal` always reviews the current revision only.

| Map | Key | Value |
|-----|-----|-------|
| `proposals` | `id` | latest meta: title, proposer, reference URL, status, current revision |
| `versions` | `"id:rev"` | description, author, status of that revision |
| `reviews` | `"id:rev"` | verdict, score, issues, summary of that revision |

`get_history(id)` returns the full chain: every revision with its description, status, and review.

## Contract interface

Constructor: `DAOProposalReviewer(dao_name: str, rules: str)`

| Method | Type | Description |
|--------|------|-------------|
| `submit_proposal(title, description, reference_url="")` | write | Create a proposal (revision 0), returns its id |
| `review_proposal(proposal_id)` | write | Run the AI review on the current revision and store the result |
| `revise_proposal(proposal_id, new_description)` | write | Proposer creates a new revision of a `REVISE` proposal, returns the new revision number |
| `get_proposal(proposal_id)` | view | Latest state: meta + current description |
| `get_version(proposal_id, revision)` | view | One specific revision |
| `get_review(proposal_id)` | view | Latest review (empty string if none) |
| `get_review_version(proposal_id, revision)` | view | Review of a specific revision |
| `get_history(proposal_id)` | view | Full audit trail: all revisions with reviews |
| `get_revision_count(proposal_id)` | view | Number of revisions |
| `get_rules()` | view | The DAO rules text |
| `get_proposal_count()` | view | Number of proposals |

## Deploy the contract

1. Open [GenLayer Studio](https://studio.genlayer.com) and paste `contracts/dao_proposal_reviewer.py`.
2. Deploy with these constructor arguments:

    **dao_name**

        GenBuilders DAO

    **rules**

        Every proposal must state a clear purpose, a budget in USD, a timeline, and a named person responsible. Budgets above 50,000 USD require approval from two independent auditors. A proposer may not be a fund recipient without declaring a conflict of interest. Proposals must not promise fixed returns or make unverifiable claims. Deliverables must be measurable, with clear milestones.

## Client script (submit, review, revise, re-review)

`client_revise_flow.py` runs the full loop against the deployed contract on Studionet using `genlayer-py`:

    pip install genlayer-py
    export PRIVATE_KEY=0x...
    export CONTRACT=0xA01EDAE3935B5d1d857A57de18C5260a92303D26
    python client_revise_flow.py

It submits a proposal, reviews it, and if the verdict is `REVISE` it calls `revise_proposal` on the **same proposal id**, re-reviews, then prints `get_history`.

## Try it

- **Should `PASS`:** "Community Hackathon Q1", 8,000 USD budget, 3-month timeline, a named lead, 3 milestones.
- **Should `REJECT`:** "Investment Fund", 200,000 USD, no timeline, promises 30% profit per month.
- **Should `REVISE`, then `PASS` after revision:** a vague meetup proposal, then a revised description with budget, timeline, and measurable deliverables.

## Live Test Results (Studionet)

Tested end-to-end on the redeployed contract. Both revisions belong to the **same proposal id (1)**, and `get_history(1)` returns both.

| ID | Revision | Verdict | Score | What happened |
|----|----------|---------|-------|---------------|
| 1 | 0 | REVISE | 20 | "Developer Workshop Series Jakarta": vague description, no budget, timeline, owner, or measurable deliverables |
| 1 | 1 | PASS | 100 | After `revise_proposal`: purpose, itemized 5,000 USD budget, Jan-Mar 2027 timeline, named owner, no conflict of interest, milestones, measurable deliverables |

**Key result:** `Submit -> Review (REVISE) -> Revise (same id, new revision) -> Re-review (PASS)`, with revision 0 and its review still stored. Re-review transaction (FINALIZED, consensus Accepted): [`0x37e3c2cb1a92b9b72ba9bff8b46bd1f4879f9f505ca0eadab5b82875d1b9c03e`](https://explorer-studio.genlayer.com/tx/0x37e3c2cb1a92b9b72ba9bff8b46bd1f4879f9f505ca0eadab5b82875d1b9c03e)

Proposal #0 on the same contract also kept its revision 0 (REVISE, score 15) intact after a revision was added. Its re-review of revision 1 ended UNDETERMINED (validators split on a borderline text), which is a normal outcome for an ambiguous proposal and leaves the revision `PENDING` so it can be reviewed again.

## Frontend

`docs/index.html` is a single static file with no build step. It uses [`genlayer-js`](https://github.com/genlayerlabs/genlayer-js) from a CDN to talk to the contract on Studionet.

- On first visit it generates a **burner wallet** stored in the browser's `localStorage` (Studionet is a testnet, no real funds). Clearing site data creates a new wallet.
- It shows the DAO rules, lets you submit proposals, trigger AI reviews, revise proposals, and see verdicts, scores, and issues.
- The contract address is set by the `CONTRACT` constant near the top of the script. Update it to the new address.

### Run locally

ES modules need a server, so don't open the file directly:

    python3 -m http.server 8000
    # open http://localhost:8000/docs/

### Publish on GitHub Pages

1. Push `docs/index.html` and `README.md` to a GitHub repository.
2. Go to **Settings -> Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**, select `main` and `/docs`, then save.
4. After a minute the site is live at `https://<your-username>.github.io/<repo-name>/`.

## Notes

- A review takes from several seconds up to a minute or two because validators must reach consensus. Some validators may show "cancelled after quorum" in the explorer; that is normal once quorum is reached.
- Reviews are AI judgments meant to screen proposals, not replace human governance.

## Files

    contracts/dao_proposal_reviewer.py   Intelligent Contract (versioned revisions)
    client_revise_flow.py                Client: submit, review, revise, re-review, history
    docs/index.html                      Static frontend
    README.md                            This file
