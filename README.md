# DAO Proposal Reviewer

An **Intelligent Contract on [GenLayer](https://www.genlayer.com)** that lets AI validators review DAO governance proposals against the DAO's own rules *before* they go to a vote.

Anyone can submit a proposal. The contract asks the validator set to evaluate it for completeness, rule compliance, red flags, and measurable deliverables, then records a verdict, a score, and the concrete issues found. Validators must agree through GenLayer's equivalence-principle consensus, so no single reviewer decides the outcome.

- **Contract (Studionet):** [`0x76BEA7a4a97B6933F58963F534e46b37e8e1192d`](https://explorer-studio.genlayer.com/address/0x76BEA7a4a97B6933F58963F534e46b37e8e1192d)
- **Live frontend:** `https://isnoop4.github.io/Dao-proposal-reviewer/`

## How it works

1. A proposer calls `submit_proposal(title, description, reference_url)`. The proposal starts as `PENDING`.
2. Anyone calls `review_proposal(id)`. Each validator runs an LLM review (and optionally reads the reference URL), returning JSON.
3. Validators reach consensus with `prompt_comparative`: the `verdict` must match exactly and the `score` may differ by at most 10 points.
4. The proposal status becomes `PASS`, `REVISE`, or `REJECT`, and the full review is stored on-chain.

| Verdict | Meaning |
|---------|---------|
| `PASS` | Ready to move to a vote |
| `REVISE` | Has fixable shortcomings |
| `REJECT` | Violates DAO rules or is too risky |

Each review contains `verdict`, `score` (0-100), `issues` (up to 5), and a one-sentence `summary`.

## Contract interface

Constructor: `DAOProposalReviewer(dao_name: str, rules: str)`

| Method | Type | Description |
|--------|------|-------------|
| `submit_proposal(title, description, reference_url="")` | write | Create a proposal, returns its id |
| `review_proposal(proposal_id)` | write | Run the AI review and store the result |
| `revise_proposal(proposal_id, new_description)` | write | Proposer updates a `PENDING`/`REVISE` proposal |
| `get_proposal(proposal_id)` | view | Proposal JSON |
| `get_review(proposal_id)` | view | Review JSON (empty string if not reviewed) |
| `get_rules()` | view | The DAO rules text |
| `get_proposal_count()` | view | Number of proposals |

## Deploy the contract

1. Open [GenLayer Studio](https://studio.genlayer.com) and paste `dao_proposal_reviewer.py`.
2. Deploy with these constructor arguments:

   **dao_name**
   ```
   GenBuilders DAO
   ```

   **rules**
   ```
   Every proposal must state a clear purpose, a budget in USD, a timeline, and a named person responsible. Budgets above 50,000 USD require approval from two independent auditors. A proposer may not be a fund recipient without declaring a conflict of interest. Proposals must not promise fixed returns or make unverifiable claims. Deliverables must be measurable, with clear milestones.
   ```

## Try it

- **Should `PASS`:** "Community Hackathon Q1", 8,000 USD budget, 3-month timeline, a named lead, 3 milestones.
- **Should `REJECT`:** "Investment Fund", 200,000 USD, no timeline, promises 30% profit per month.

## Frontend

`index.html` is a single static file with no build step. It uses [`genlayer-js`](https://github.com/genlayerlabs/genlayer-js) from a CDN to talk to the contract on Studionet.

- On first visit it generates a **burner wallet** stored in the browser's `localStorage` (Studionet is a testnet, no real funds). Clearing site data creates a new wallet.
- It shows the DAO rules, lets you submit proposals, trigger AI reviews, and see verdicts, scores, and issues.
- The contract address is set by the `CONTRACT` constant near the top of the script. Change it if you redeploy.

### Run locally

ES modules need a server, so don't open the file directly:

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

### Publish on GitHub Pages

1. Push `index.html` and `README.md` to a GitHub repository.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**, select `main` and `/ (root)`, then save.
4. After a minute the site is live at `https://<your-username>.github.io/<repo-name>/`.

## Notes

- A review takes from several seconds up to a minute or two because validators must reach consensus. Some validators may show "cancelled after quorum" in the explorer; that is normal once quorum is reached.
- Reviews are AI judgments meant to screen proposals, not replace human governance.

## Files

```
dao_proposal_reviewer.py   Intelligent Contract
index.html                 Static frontend
README.md                  This file
```
