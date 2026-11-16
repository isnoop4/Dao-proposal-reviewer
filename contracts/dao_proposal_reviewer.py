# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json


class DAOProposalReviewer(gl.Contract):
    """
    DAO Proposal Reviewer
    AI validators check a governance proposal against the DAO rules
    (completeness, rule compliance, red flags) before it goes to a vote.

    Versioned audit trail:
    - Every revision is stored as its own version record (never overwritten).
    - Every review is stored per (proposal, revision).
    - get_history() returns the full chain: version 0 -> review -> revision 1 -> review ...
    """

    dao_name: str
    rules: str
    proposal_count: u256
    proposals: TreeMap[u256, str]  # id -> JSON meta (latest state: status, current revision)
    versions: TreeMap[str, str]    # "id:rev" -> JSON {revision, description, author, status}
    reviews: TreeMap[str, str]     # "id:rev" -> JSON review result

    def __init__(self, dao_name: str, rules: str):
        self.dao_name = dao_name
        self.rules = rules
        self.proposal_count = u256(0)

    # ---------- WRITE ----------

    @gl.public.write
    def submit_proposal(self, title: str, description: str, reference_url: str = "") -> int:
        if len(title.strip()) == 0 or len(description.strip()) == 0:
            raise Exception("Title and description are required")

        pid = self.proposal_count
        sender = str(gl.message.sender_address)
        meta = {
            "id": int(pid),
            "proposer": sender,
            "title": title,
            "reference_url": reference_url,
            "status": "PENDING",
            "revision": 0,
        }
        version = {
            "revision": 0,
            "description": description,
            "author": sender,
            "status": "PENDING",
        }
        self.proposals[pid] = json.dumps(meta)
        self.versions[self._key(int(pid), 0)] = json.dumps(version)
        self.proposal_count = u256(int(pid) + 1)
        return int(pid)

    @gl.public.write
    def revise_proposal(self, proposal_id: int, new_description: str) -> int:
        """Creates a NEW version. Previous versions and their reviews are preserved."""
        if len(new_description.strip()) == 0:
            raise Exception("New description is required")

        pid = u256(proposal_id)
        meta = self._load(pid)
        if str(gl.message.sender_address) != meta["proposer"]:
            raise Exception("Only the proposer can revise")
        if meta["status"] != "REVISE":
            raise Exception("Only proposals with verdict REVISE can be revised")

        new_rev = int(meta["revision"]) + 1
        version = {
            "revision": new_rev,
            "description": new_description,
            "author": meta["proposer"],
            "status": "PENDING",
        }
        self.versions[self._key(proposal_id, new_rev)] = json.dumps(version)

        meta["revision"] = new_rev
        meta["status"] = "PENDING"
        self.proposals[pid] = json.dumps(meta)
        return new_rev

    @gl.public.write
    def review_proposal(self, proposal_id: int) -> str:
        """Reviews the CURRENT revision. Result is stored under that revision only."""
        pid = u256(proposal_id)
        meta = self._load(pid)
        if meta["status"] != "PENDING":
            raise Exception("Current revision already reviewed, revise first if needed")

        rev = int(meta["revision"])
        key = self._key(proposal_id, rev)
        version = json.loads(self.versions[key])

        rules = self.rules
        dao_name = self.dao_name
        title = meta["title"]
        description = version["description"]
        url = meta["reference_url"]

        def run_review() -> str:
            external = ""
            if url:
                try:
                    external = gl.nondet.web.render(url, mode="text")[:3000]
                except Exception:
                    external = "(reference URL could not be opened)"

            prompt = f"""
You are a governance proposal reviewer for the DAO "{dao_name}".

DAO RULES:
{rules}

PROPOSAL:
Title: {title}
Description: {description}

REFERENCE URL CONTENT (if any):
{external if external else "(none)"}

Evaluate this proposal on 4 aspects:
1. Completeness (clear purpose, budget, timeline, responsible person?)
2. Compliance with the DAO rules above
3. Red flags (unrealistic budget, conflict of interest, unverifiable claims, signs of a scam)
4. Clarity and measurability of deliverables

Decide a verdict:
- "PASS": ready to move to voting
- "REVISE": has fixable shortcomings
- "REJECT": violates the rules or is too risky

Write all text in English.
Reply with ONLY valid JSON in exactly this format:
{{"verdict": "PASS|REVISE|REJECT", "score": 0-100, "issues": ["..."], "summary": "one sentence"}}
"""
            raw = gl.nondet.exec_prompt(prompt)
            if isinstance(raw, dict):
                parsed = raw
            else:
                text = str(raw).strip()
                text = text.replace("```json", "").replace("```", "").strip()
                start, end = text.find("{"), text.rfind("}")
                parsed = json.loads(text[start : end + 1])

            verdict = str(parsed.get("verdict", "REVISE")).upper()
            if verdict not in ("PASS", "REVISE", "REJECT"):
                verdict = "REVISE"
            try:
                score = max(0, min(100, int(parsed.get("score", 0))))
            except Exception:
                score = 0
            issues = [str(i) for i in parsed.get("issues", [])][:5]
            summary = str(parsed.get("summary", ""))[:300]

            return json.dumps(
                {"verdict": verdict, "score": score, "issues": issues, "summary": summary},
                sort_keys=True,
            )

        result_str = gl.eq_principle.prompt_comparative(
            run_review,
            "The 'verdict' field must match exactly, and the 'score' may differ by at most 10 points. "
            "The 'issues' and 'summary' may be worded differently as long as the meaning is consistent.",
        )
        result = json.loads(result_str)

        # Store review under this revision (history preserved)
        self.reviews[key] = result_str
        version["status"] = result["verdict"]
        self.versions[key] = json.dumps(version)
        meta["status"] = result["verdict"]
        self.proposals[pid] = json.dumps(meta)
        return result_str

    # ---------- VIEW ----------

    @gl.public.view
    def get_proposal(self, proposal_id: int) -> str:
        """Latest state: meta + current revision's description."""
        meta = self._load(u256(proposal_id))
        version = json.loads(self.versions[self._key(proposal_id, int(meta["revision"]))])
        meta["description"] = version["description"]
        return json.dumps(meta)

    @gl.public.view
    def get_version(self, proposal_id: int, revision: int) -> str:
        key = self._key(proposal_id, revision)
        if key not in self.versions:
            return ""
        return self.versions[key]

    @gl.public.view
    def get_review(self, proposal_id: int) -> str:
        """Review of the latest reviewed revision ('' if none yet)."""
        meta = self._load(u256(proposal_id))
        rev = int(meta["revision"])
        while rev >= 0:
            key = self._key(proposal_id, rev)
            if key in self.reviews:
                return self.reviews[key]
            rev -= 1
        return ""

    @gl.public.view
    def get_review_version(self, proposal_id: int, revision: int) -> str:
        key = self._key(proposal_id, revision)
        if key not in self.reviews:
            return ""
        return self.reviews[key]

    @gl.public.view
    def get_history(self, proposal_id: int) -> str:
        """Full audit trail: every version with its review (if any)."""
        meta = self._load(u256(proposal_id))
        history = []
        for rev in range(int(meta["revision"]) + 1):
            key = self._key(proposal_id, rev)
            entry = json.loads(self.versions[key])
            entry["review"] = json.loads(self.reviews[key]) if key in self.reviews else None
            history.append(entry)
        return json.dumps({"id": meta["id"], "title": meta["title"], "history": history})

    @gl.public.view
    def get_revision_count(self, proposal_id: int) -> int:
        meta = self._load(u256(proposal_id))
        return int(meta["revision"]) + 1

    @gl.public.view
    def get_rules(self) -> str:
        return self.rules

    @gl.public.view
    def get_proposal_count(self) -> int:
        return int(self.proposal_count)

    # ---------- INTERNAL ----------

    def _key(self, proposal_id: int, revision: int) -> str:
        return f"{int(proposal_id)}:{int(revision)}"

    def _load(self, pid: u256) -> dict:
        if pid not in self.proposals:
            raise Exception("Proposal not found")
        return json.loads(self.proposals[pid])
