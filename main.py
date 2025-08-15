from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, HttpUrl
import requests, re, html
from lxml import etree

app = FastAPI()

class SnipReq(BaseModel):
    url: HttpUrl   # directe .alto.xml-URL uit ES
    q: str         # query
    context: int = 70  # tekens links/rechts (MVP)

def _compile_pattern(q: str) -> re.Pattern:
    # simpele OR over termen, '*' is wildcard
    terms = [t for t in re.split(r"\s+", q.strip()) if t]
    if not terms:
        raise HTTPException(400, "Lege query")
    parts = []
    for t in terms:
        esc = re.escape(t).replace(r"\*", r".*")
        parts.append(esc)
    return re.compile("|".join(parts), re.IGNORECASE)

def _localname(tag: str) -> str:
    # strip XML-namespace
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag

@app.post("/snippet")
def snippet(req: SnipReq):
    pat = _compile_pattern(req.q)

    try:
        r = requests.get(
            req.url, timeout=12, stream=True,
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
                    s = max(0, m.start() - req.context)
                    e = min(len(text), m.end() + req.context)
                    pre, hit, post = text[s:m.start()], text[m.start():m.end()], text[m.end():e]
                    html_snip = f"{html.escape(pre)}<em>{html.escape(hit)}</em>{html.escape(post)}"
                    return {"html": html_snip}

                buf = []
                elem.clear()

    except etree.XMLSyntaxError:
        raise HTTPException(502, "Parse error")

    return Response(status_code=204)
