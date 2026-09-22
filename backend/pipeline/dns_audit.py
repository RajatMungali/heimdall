import dns.resolver
import asyncio

COMMON_DKIM_SELECTORS = [
    "google", "selector1", "k1", "default", "mail",
    "smtp", "picasso", "mandrill", "sendgrid", "microsoft"
]


async def async_check_selector(selector: str, domain: str):
    def lookup():
        try:
            dns.resolver.resolve(f"{selector}._domainkey.{domain}", "TXT")
            return selector
        except Exception:
            return None
    return await asyncio.to_thread(lookup)


async def audit_domain_email_infrastructure(domain: str) -> dict:
    """
    Performs a deterministic public DNS diagnostic on the target domain.

    Returns the Strict Data Contract DNS Audit Objective Object:
    spf, dkim, dmarc as strings, plus issues as string[].
    """
    results: dict[str, str | list[str]] = {
        "spf": "Missing",
        "dkim": "Missing",
        "dmarc": "Missing",
        "issues": []
    }

    try:
        txt_records = dns.resolver.resolve(domain, "TXT")
        for record in txt_records:
            txt_str = "".join(s.decode() for s in record.strings)
            if txt_str.startswith("v=spf1"):
                results["spf"] = "Valid"
                break
    except Exception:
        pass

    if results["spf"] == "Missing":
        results["issues"].append(
            f"{domain} has no SPF record - outbound emails risk immediate rejection."
        )

    try:
        dmarc_records = dns.resolver.resolve(f"_dmarc.{domain}", "TXT")
        for record in dmarc_records:
            txt_str = "".join(s.decode() for s in record.strings)
            if txt_str.startswith("v=DMARC1"):
                results["dmarc"] = "Valid"
                if "p=none" in txt_str.lower():
                    results["dmarc"] = "Weak (Monitoring Only)"
                    results["issues"].append(
                        f"{domain} enforces DMARC p=none - monitoring only, "
                        "lacks active domain protection."
                    )
                break
    except Exception:
        pass

    if results["dmarc"] == "Missing":
        results["issues"].append(
            f"{domain} lacks a DMARC record - zero delivery visibility "
            "or sender spoofing safety blocks."
        )

    discovered_selectors = await asyncio.gather(*[
        async_check_selector(s, domain) for s in COMMON_DKIM_SELECTORS
    ])
    
    if any(discovered_selectors):
        results["dkim"] = "Valid"

    if results["dkim"] == "Missing":
        results["issues"].append(
            f"{domain} missing common cryptographic DKIM record configurations."
        )

    return results
