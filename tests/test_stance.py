"""Stance (docs/plans/claim-context-2026-10-14.md, milestone 5): a claim's attribution chain, the reported links of
who holds it, kept apart from the pipeline's own confidence."""
import stubs  # noqa: F401 (a clean environment)
import unittest

from semantic_pdf_diff.schema import Claim, Extraction, Link, claim_id

TIMEOUT = dict(entity="Link failure detection", attribute="acknowledgement timeout", value="251", unit="ms",
               kind="table", quote="Proposal 1: The acknowledgement timeout is 251 ms.", confidence=0.9)

class Schema(unittest.TestCase):
    def test_a_claim_without_a_holder_keeps_its_id_and_two_holders_make_two_claims(self):
        import hashlib
        import json
        plain = Claim(**TIMEOUT)
        before = ["c", "link failure detection", "acknowledgement timeout", "251", "ms", "", False, "unknown"]
        self.assertEqual(claim_id("c", plain), "ev-" + hashlib.sha256(json.dumps(before).encode()).hexdigest()[:16])
        avelin = Claim(**TIMEOUT, stance=[Link(holder="Avelin", attitude="proposes")])
        borealis = Claim(**TIMEOUT, stance=[Link(holder="Borealis", attitude="proposes")])
        self.assertEqual(len({claim_id("c", x) for x in (plain, avelin, borealis)}), 3)
        # the attitude and a hedge describe the link; the holder names the claim
        hedged = Claim(**TIMEOUT, stance=[Link(holder="avelin", attitude="may propose", strength="may")])
        self.assertEqual(claim_id("c", hedged), claim_id("c", avelin))

    def test_a_malformed_stance_loses_the_stance_not_the_claim(self):
        answer = Extraction.model_validate({"claims": [{**TIMEOUT, "stance": "Avelin"},
                                                       {**TIMEOUT, "value": "483", "stance": [{"holder": "Borealis"},
                                                                                             {"attitude": "x"}, 7]}],
                                            "complete": True})
        self.assertEqual([[link.holder for link in c.stance] for c in answer.claims], [[], ["Borealis"]])
        self.assertTrue(answer.complete)

    def test_evidence_without_a_stance_is_written_as_before(self):
        from semantic_pdf_diff.schema import Evidence, PdfLocator
        made = lambda **k: Evidence(**TIMEOUT, **k, id="ev-1", content="c",  # noqa: E731
                                    locator=PdfLocator(page=1, bbox=(0, 0, 1, 1), region="table", task="t"))
        self.assertNotIn("stance", made().model_dump())
        self.assertEqual(made(stance=[Link(holder="Avelin")]).model_dump()["stance"],
                         [{"holder": "Avelin", "attitude": "", "strength": ""}])

if __name__ == "__main__":
    unittest.main()
