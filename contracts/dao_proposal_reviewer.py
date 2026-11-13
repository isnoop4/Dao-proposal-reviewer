# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json


class DAOProposalReviewer(gl.Contract):
    """
    DAO Proposal Reviewer
    Validator AI mengecek proposal governance terhadap aturan DAO
    (kelengkapan, konflik aturan, red flag) sebelum masuk voting.
    """

    dao_name: str
    rules: str
    proposal_count: u256
    proposals: TreeMap[u256, str]  # id -> JSON proposal
    reviews: TreeMap[u256, str]    # id -> JSON hasil review

    def __init__(self, dao_name: str, rules: str):
        self.dao_name = dao_name
        self.rules = rules
        self.proposal_count = u256(0)

    # ---------- WRITE ----------

    @gl.public.write
    def submit_proposal(self, title: str, description: str, reference_url: str = "") -> int:
        if len(title.strip()) == 0 or len(description.strip()) == 0:
            raise Exception("Judul dan deskripsi wajib diisi")

        pid = self.proposal_count
        data = {
            "id": int(pid),
            "proposer": str(gl.message.sender_address),
            "title": title,
            "description": description,
            "reference_url": reference_url,
            "status": "PENDING",
            "revision": 0,
        }
        self.proposals[pid] = json.dumps(data)
        self.proposal_count = u256(int(pid) + 1)
        return int(pid)

    @gl.public.write
    def revise_proposal(self, proposal_id: int, new_description: str) -> None:
        pid = u256(proposal_id)
        data = self._load(pid)
        if str(gl.message.sender_address) != data["proposer"]:
            raise Exception("Hanya proposer yang boleh merevisi")
        if data["status"] not in ("REVISE", "PENDING"):
            raise Exception("Proposal ini tidak bisa direvisi")

        data["description"] = new_description
        data["status"] = "PENDING"
        data["revision"] += 1
        self.proposals[pid] = json.dumps(data)

    @gl.public.write
    def review_proposal(self, proposal_id: int) -> str:
        pid = u256(proposal_id)
        data = self._load(pid)
        if data["status"] != "PENDING":
            raise Exception("Proposal sudah direview, revisi dulu jika perlu")

        rules = self.rules
        dao_name = self.dao_name
        title = data["title"]
        description = data["description"]
        url = data["reference_url"]

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

        data["status"] = result["verdict"]
        self.proposals[pid] = json.dumps(data)
        self.reviews[pid] = result_str
        return result_str

    # ---------- VIEW ----------

    @gl.public.view
    def get_proposal(self, proposal_id: int) -> str:
        return json.dumps(self._load(u256(proposal_id)))

    @gl.public.view
    def get_review(self, proposal_id: int) -> str:
        pid = u256(proposal_id)
        if pid not in self.reviews:
            return ""
        return self.reviews[pid]

    @gl.public.view
    def get_rules(self) -> str:
        return self.rules

    @gl.public.view
    def get_proposal_count(self) -> int:
        return int(self.proposal_count)

    # ---------- INTERNAL ----------

    def _load(self, pid: u256) -> dict:
        if pid not in self.proposals:
            raise Exception("Proposal tidak ditemukan")
        return json.loads(self.proposals[pid])
