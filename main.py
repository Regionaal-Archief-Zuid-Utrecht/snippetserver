from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, HttpUrl
import requests, re, html
from lxml import etree
from typing import Optional

app = FastAPI()

class SnipReq(BaseModel):
    url: HttpUrl   # directe .alto.xml-URL uit ES
    q: str         # query
    context: int = 70  # tekens links/rechts (MVP)

def _compile_pattern(q: str) -> re.Pattern:
    # simpele OR over termen, '*' is wildcard binnen een token (niet over whitespace)
    terms = [t for t in re.split(r"\s+", q.strip()) if t]
    if not terms:
        raise HTTPException(400, "Lege query")

    def token_to_regex(tok: str) -> str:
        # Normaliseer meerdere '*' achter elkaar
        tok = re.sub(r"\*+", "*", tok)

        # Escape alle niet-wildcard tekens
        parts = [re.escape(p) for p in tok.split("*")]

        # Bouw patroon waarbij '*' -> [^\s]* (blijft binnen dezelfde 'woordgroep')
        if "*" not in tok:
            # Exacte term als heel woord
            core = parts[0]
            return rf"\b{core}\b"

        # Met wildcard(s): voeg boundaries toe indien zinvol
        # Voorbeeld: 'term*' => \bterm[^\s]*
        #           '*term' => [^\s]*term\b
        #           'te*rm' => \bte[^\s]*rm\b (binnen woord)
        regex = "[^\\s]*".join(parts)

        starts_with_star = tok.startswith("*")
        ends_with_star = tok.endswith("*")

        if not starts_with_star:
            regex = rf"\b{regex}"
        if not ends_with_star:
            regex = rf"{regex}\b"
        return regex

    patterns = [token_to_regex(t) for t in terms]
    return re.compile("|".join(patterns), re.IGNORECASE)

def _localname(tag: str) -> str:
    # strip XML-namespace
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag

def _find_snippet(url: HttpUrl, q: str, context: int) -> Optional[str]:
    pat = _compile_pattern(q)

    try:
        r = requests.get(
            url, timeout=12, stream=True,
            headers={"Accept-Encoding": "gzip, deflate, br"}
        )
    except requests.RequestException:
        raise HTTPException(502, "Fetch failed")
    if r.status_code in (403, 404):
        raise HTTPException(403, "Not public")
    if r.status_code != 200:
        raise HTTPException(502, "Upstream error")

    # Laat requests de gzip decompresseren terwijl we streamen
    r.raw.decode_content = True

    # Accumuleer tekst per Page; stop bij eerste match
    buf = []
    try:
        for event, elem in etree.iterparse(
            r.raw, events=("start", "end"),
            recover=True, huge_tree=True
        ):
            tag = _localname(elem.tag)

            if event == "start" and tag == "Page":
                buf = []

            elif event == "end" and tag == "String":
                content = elem.get("CONTENT")
                if content:
                    buf.append(content)
                elem.clear()

            elif event == "end" and tag == "Page":
                text = " ".join(buf)
                # eenvoudige de-hyphenation (MVP)
                text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)

                m = pat.search(text)
                if m:
                    s = max(0, m.start() - context)
                    e = min(len(text), m.end() + context)
                    pre, hit, post = text[s:m.start()], text[m.start():m.end()], text[m.end():e]
                    html_snip = f"{html.escape(pre)}<em>{html.escape(hit)}</em>{html.escape(post)}"
                    return html_snip

                buf = []
                elem.clear()

    except etree.XMLSyntaxError:
        raise HTTPException(502, "Parse error")

    return None

@app.post("/snippet")
def snippet(req: SnipReq):
    html_snip = _find_snippet(req.url, req.q, req.context)
    if html_snip is None:
        return Response(status_code=204)
    return {"html": html_snip}

@app.get("/snippet")
def snippet_get(url: HttpUrl, q: str, context: int = 70):
    html_snip = _find_snippet(url, q, context)
    if html_snip is None:
        return Response(status_code=204)
    return Response(content=html_snip, media_type="text/html")
