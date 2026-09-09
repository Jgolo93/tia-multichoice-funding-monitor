import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SITES = {
    "tia": {
        "name": "TIA Open Calls",
        "url": "https://www.tia.org.za/category/open-calls/",
        "domain": "tia.org.za",
    },
    "multichoice": {
        "name": "MultiChoice Innovation Fund",
        # This is the MultiChoice Innovation Fund page shown in the screenshot.
        # If MultiChoice changes its URL, change it here.
        "url": "https://www.multichoice.com/enriching-lives/multichoice-innovation-fund/",
        "domain": "multichoice.com",
    },
}

STATE_FILE = Path("data/funding_seen.json")
KEYWORDS = [
    "innovation", "fund", "funding", "application", "call", "grant",
    "technology", "ict", "digital", "smm", "entrepreneur", "startup",
    "open", "close", "deadline", "journeybase", "software", "saas",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; Empath-Funding-Monitor/1.0; "
        "+https://github.com/)"
    )
}


def load_state():
    if not STATE_FILE.exists():
        return {"sites": {}}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def normalise(text):
    return " ".join(text.split())


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch(url):
    response = requests.get(url, headers=HEADERS, timeout=45)
    response.raise_for_status()
    return response.text, response.url


def extract_tia(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#")[0]
        title = normalise(a.get_text(" ", strip=True))
        if not title or len(title) < 8:
            continue
        if urlparse(href).netloc and "tia.org.za" not in urlparse(href).netloc:
            continue
        if href.rstrip("/").endswith("/category/open-calls"):
            continue
        if any(x in href.lower() for x in ["/wp-content/", ".pdf", ".jpg", ".png"]):
            continue
        if href in seen:
            continue
        seen.add(href)
        items.append({"title": title, "url": href})

    # Keep only plausible call/post links. This deliberately errs toward
    # catching a new call rather than silently missing one.
    return items


def extract_multichoice(html, final_url):
    soup = BeautifulSoup(html, "html.parser")

    # Remove navigation/footer noise before hashing the meaningful page text.
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    text = normalise(soup.get_text(" ", strip=True))
    relevant = " ".join(
        sentence for sentence in text.split(".")
        if any(k in sentence.lower() for k in KEYWORDS)
    )

    # Capture links that look like application/call/fund links.
    links = []
    for a in soup.find_all("a", href=True):
        label = normalise(a.get_text(" ", strip=True))
        href = urljoin(final_url, a["href"]).split("#")[0]
        combined = f"{label} {href}".lower()
        if any(k in combined for k in ["apply", "application", "fund", "innovation", "call"]):
            if href.startswith("http"):
                links.append({"title": label or href, "url": href})

    return {
        "text": relevant[:20000],
        "links": links[:50],
    }


def create_issue(site_name, changes):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise RuntimeError("GITHUB_TOKEN/GITHUB_REPOSITORY not available")

    lines = [
        f"## {site_name} update detected",
        "",
        "This monitor found a new call or a meaningful change on the official funding page.",
        "",
    ]

    for change in changes:
        lines.append(f"### {change.get('title', 'Funding page update')}")
        if change.get("url"):
            lines.append(f"Official page: {change['url']}")
        if change.get("details"):
            lines.append("")
            lines.append(change["details"])
        lines.append("")

    lines += [
        "### JourneyBase check",
        "Review whether the opportunity is relevant to Empath Technology Solutions / JourneyBase.",
        "Check ownership, B-BBEE/black-ownership requirements, sector, funding type, amount, eligible costs, deadline and previous-government-funding rules before applying.",
    ]

    payload = {
        "title": f"[{site_name}] Funding opportunity/update",
        "body": "\n".join(lines),
        "labels": ["funding", site_name.lower().replace(" ", "-")],
    }

    r = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    print(f"Created GitHub Issue for {site_name}: {r.json().get('html_url')}")


def check_tia(state):
    cfg = SITES["tia"]
    html, final_url = fetch(cfg["url"])
    calls = extract_tia(html, final_url)
    current = {c["url"]: c for c in calls}
    previous = state.get("tia", {}).get("calls", {})

    # First run creates a baseline; it does not spam an issue for old calls.
    if not previous:
        state["tia"] = {"calls": current, "page_hash": sha(normalise(html))}
        print(f"TIA baseline stored: {len(current)} links")
        return

    new = [c for url, c in current.items() if url not in previous]
    if new:
        create_issue(cfg["name"], [
            {"title": c["title"], "url": c["url"], "details": "A new TIA Open Call link was detected."}
            for c in new
        ])

    state["tia"] = {"calls": current, "page_hash": sha(normalise(html))}
    print(f"TIA: {len(new)} new call(s)")


def check_multichoice(state):
    cfg = SITES["multichoice"]
    html, final_url = fetch(cfg["url"])
    extracted = extract_multichoice(html, final_url)
    content_hash = sha(extracted["text"])
    previous = state.get("multichoice", {})

    if not previous:
        state["multichoice"] = {
            "content_hash": content_hash,
            "text": extracted["text"],
            "links": extracted["links"],
        }
        print("MultiChoice baseline stored.")
        return

    if content_hash != previous.get("content_hash"):
        old = previous.get("text", "")
        new = extracted["text"]
        details = (
            "The relevant funding-page text changed.\n\n"
            f"**Previous snapshot:**\n{old[:5000]}\n\n"
            f"**Current snapshot:**\n{new[:5000]}"
        )
        create_issue(cfg["name"], [{
            "title": "Innovation Fund page changed",
            "url": final_url,
            "details": details,
        }])

    state["multichoice"] = {
        "content_hash": content_hash,
        "text": extracted["text"],
        "links": extracted["links"],
    }
    print("MultiChoice: checked for funding-page changes.")


def main():
    state = load_state()
    try:
        check_tia(state)
    except Exception as exc:
        print(f"TIA check failed: {exc}")

    try:
        check_multichoice(state)
    except Exception as exc:
        print(f"MultiChoice check failed: {exc}")

    save_state(state)


if __name__ == "__main__":
    main()
