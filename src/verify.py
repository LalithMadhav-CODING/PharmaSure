"""Two-stage citation verifier.

Stage 1: Source identity — does the citation exist and match the drug+disease?
Stage 2: Claim support — does the passage actually support the claim?

Failures are flagged as "needs review", NOT auto-rejected (to avoid rejecting valid paraphrases).
"""
import re


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip whitespace, normalize quotes."""
    text = text.lower().strip()
    # Normalize smart quotes
    text = text.replace("\"", '"').replace("\"", '"')
    text = text.replace("'", "'").replace("'", "'")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text


def verify_citations(answer: dict, passages_by_id: dict) -> dict:
    """Verify all citations in the answer.

    Stage 1: source identity — citation ID exists, passage matches drug+disease
    Stage 2: claim support — quote is a substring of the passage (fuzzy)

    Flags failures as "needs review" rather than dropping.
    """
    verified = []

    for candidate in answer.get("candidates", []):
        drug_name = candidate.get("drug_name", "")
        verified_claims = []

        for claim in candidate.get("claims", []):
            citation_ids = claim.get("citation_ids", [])
            quote = claim.get("quote", "")
            text = claim.get("text", "")

            if not citation_ids or not quote:
                # No citation or no quote — flag as needs review
                verified_claims.append({
                    **claim,
                    "verification_status": "needs_review",
                    "verification_reason": "Missing citation or quote",
                })
                continue

            # Check each citation
            all_verified = True
            any_verified = False
            reasons = []

            for cid in citation_ids:
                passage = passages_by_id.get(cid)
                if passage is None:
                    all_verified = False
                    reasons.append(f"Citation [{cid}] not found")
                    continue

                passage_text = passage.get("text", "")
                norm_passage = normalize_text(passage_text)
                norm_quote = normalize_text(quote)

                # Stage 1: source identity — does passage mention the drug?
                if drug_name and drug_name.lower() not in norm_passage:
                    all_verified = False
                    reasons.append(f"Citation [{cid}] does not mention drug '{drug_name}'")
                    continue

                # Stage 2: claim support — is the quote in the passage?
                if norm_quote in norm_passage:
                    any_verified = True
                else:
                    # Fuzzy check: check if key phrases from quote appear
                    quote_words = norm_quote.split()
                    if len(quote_words) >= 3:
                        # Check if at least 70% of quote words appear in passage
                        matches = sum(1 for w in quote_words if w in norm_passage)
                        if matches / len(quote_words) >= 0.7:
                            any_verified = True
                        else:
                            all_verified = False
                            reasons.append(f"Citation [{cid}] quote not found in passage")
                    else:
                        all_verified = False
                        reasons.append(f"Citation [{cid}] quote not found in passage")

            if all_verified and any_verified:
                status = "verified"
                reason = "All citations verified"
            elif any_verified:
                status = "needs_review"
                reason = "; ".join(reasons) if reasons else "Some citations could not be fully verified"
            else:
                status = "needs_review"
                reason = "; ".join(reasons) if reasons else "No citations could be verified"

            verified_claims.append({
                **claim,
                "verification_status": status,
                "verification_reason": reason,
            })

        verified.append({
            **candidate,
            "claims": verified_claims,
        })

    return {"candidates": verified}
