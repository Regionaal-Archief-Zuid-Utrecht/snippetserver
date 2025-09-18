from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, HttpUrl
import requests, re, html, os
from lxml import etree
from typing import Optional, List
from urllib.parse import urlparse

app = FastAPI()

class SnipReq(BaseModel):
    url: HttpUrl   # directe .alto.xml-URL uit ES
    q: str        # query
    context: int = 70  # tekens links/rechts (MVP)
    

def _localname(tag: str) -> str:
    # strip XML-namespace
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag

def _load_allowed_hosts() -> List[str]:
    # Comma-separated env var; default to opslag.razu.nl
    raw = os.getenv("ALLOWED_HOSTS", "opslag.razu.nl")
    hosts = [h.strip().lower() for h in raw.split(",") if h.strip()]
    return hosts

ALLOWED_HOSTS = _load_allowed_hosts()

def _host_allowed(host: Optional[str]) -> bool:
    if not host:
        return False
    host = host.lower()
    for allowed in ALLOWED_HOSTS:
        if host == allowed or host.endswith("." + allowed):
            return True
    return False

def _match_pattern(query: str, text: str, context: int) -> Optional[str]: 
    ''' takes in input the user query and the newspaper text retrieved from the alto.xml with the number of context chars to include before and after the query returns an html string '''
    # need to add code to match both lower and uppercase

    query = query.strip("*") # removing wildcards added by typescript 
    html_snippet = None

    if query[0] == "\"" and query[-1] == "\"":
        '''logic to look for quoted strings such as "geldzaken en belastingen" '''
        # print(query)
        query = query.strip("\"")
        words = query.split()
        pattern = r'\b' + r'\s+'.join(re.escape(word) for word in words) + r'\b' # builds pattern by joining any number of words with spaces
        re_pattern = re.compile(pattern, re.IGNORECASE)
        match = re_pattern.search(text)
        if match:
            # print(match.group(0))
            # code to include the context text before and after the match
            start = max(0, match.start() - context) # gets text before match ensuring it doesn't go out of bounds
            end = min(len(text), match.end() + context) # gets text after match ensuring it doesn't go out of bounds
            pre, hit, post = text[start:match.start()], text[match.start():match.end()], text[match.end():end] # splits the text into three parts: before, match, and after to add the <em> in the html
            html_snippet = f"{html.escape(pre)}<em>{html.escape(hit)}</em>{html.escape(post)}" # create the html snippet adding the <em> tag around the match
            # print(html_snippet)
            return html_snippet


    else:
        words = query.split()
        if len(words) > 1:
            '''logic to look for multiple words such as belastingen Utrecht '''
            if all(re.search(rf'\b{re.escape(word)}\b', text, re.IGNORECASE) for word in words): 
                '''check if all terms are matched in the text'''
                html_snippet = [] # initializing a list for highlight snippets of every word in the query
                for word in words:
                    pattern = rf'\b{re.escape(word)}\b' # builds pattern for each word
                    re_pattern = re.compile(pattern, re.IGNORECASE) # compiles pattern
                    match = re_pattern.search(text) # searches for match
                    if match:
                        start = max(0, match.start() - context) # gets text before match ensuring it doesn't go out of bounds
                        end = min(len(text), match.end() + context) # gets text after match ensuring it doesn't go out of bounds
                        pre, hit, post = text[start:match.start()], text[match.start():match.end()], text[match.end():end] # splits the text into three parts: before, match, and after to add the <em> in the html
                        html_snippet.append(f"{html.escape(pre)}<em>{html.escape(hit)}</em>{html.escape(post)}") # appends the html snippet to the list
                return "<br>".join(html_snippet) # joins the list into a string

            else: 
                '''check if any of the words are matched in the text''' 
                html_snippet = [] # initializing a list for highlight snippets of every word in the query
                for word in words:
                    pattern = rf'\b{re.escape(word)}\b' # builds pattern for each word
                    re_pattern = re.compile(pattern, re.IGNORECASE) # compiles pattern
                    match = re_pattern.search(text) # searches for match
                    if match:
                        start = max(0, match.start() - context) # gets text before match ensuring it doesn't go out of bounds
                        end = min(len(text), match.end() + context) # gets text after match ensuring it doesn't go out of bounds
                        pre, hit, post = text[start:match.start()], text[match.start():match.end()], text[match.end():end] # splits the text into three parts: before, match, and after to add the <em> in the html
                        html_snippet.append(f"{html.escape(pre)}<em>{html.escape(hit)}</em>{html.escape(post)}") # appends the html snippet to the list
                return "<br>".join(html_snippet) # joins the list into a string


        elif len(words) == 1:
            '''logic to look for one word such as belastingen '''
            pattern = rf'\b{re.escape(words[0])}\b'
            '''looks for exact match'''
            re_pattern = re.compile(pattern, re.IGNORECASE)
            match = re_pattern.search(text)
            if match:
                start = max(0, match.start() - context)
                end = min(len(text), match.end() + context)
                pre, hit, post = text[start:match.start()], text[match.start():match.end()], text[match.end():end]
                html_snippet = f"{html.escape(pre)}<em>{html.escape(hit)}</em>{html.escape(post)}"
                return html_snippet
            else:
                '''looks for term with any number of characters before and after the match'''
                pattern = rf'\w*{re.escape(words[0])}\w*' # matches any word containing the queried word
                re_pattern = re.compile(pattern, re.IGNORECASE)
                match = re_pattern.search(text)
                if match: # returns only the first matched word
                    start = max(0, match.start() - context)
                    end = min(len(text), match.end() + context)
                    pre, hit, post = text[start:match.start()], text[match.start():match.end()], text[match.end():end]
                    html_snippet = f"{html.escape(pre)}<em>{html.escape(hit)}</em>{html.escape(post)}"
                    return html_snippet
                else:
                    return None

def _find_snippet(url: HttpUrl, q: str, context: int) -> Optional[str]:
    print(f"\nquery text = {q}")

    # Security: restrict to configured domains
    host = urlparse(str(url)).hostname
    if not _host_allowed(host):
        raise HTTPException(403, "Domain not allowed")

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

                # calls the function to look for the query in the text
                html_snippet = _match_pattern(q, text, context)
                if html_snippet:
                    print(f"\nhtml snippet: {html_snippet}\n")
                    return html_snippet

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

# tested with  
# 1 "geldzaken en budgetbeheersing" (should match exactly 'geldzaken en budgetbeheersing')
# 2 belastingen bedrijfsleven ( should match both words in different parts of the text)
# 3 waking (should match 'bewaking')
# 4 volgens (should exact match 'volgens')
# 5 belastingen bedrijfsleven ciao (should only match 'bedrijfsleven')

# 1
''' curl --silent -i --get 'http://127.0.0.1:8000/snippet' \
  --data-urlencode 'url=https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/001/169/nl-wbdrazu-k50907905-689-1169654.alto.xml' \
  --data-urlencode 'q="geldzaken en budgetbeheersing"' \
  --data-urlencode 'context=70'
  '''
# 2
''' curl --silent -i --get 'http://127.0.0.1:8000/snippet' \
  --data-urlencode 'url=https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/001/169/nl-wbdrazu-k50907905-689-1169654.alto.xml' \
  --data-urlencode 'q=probeert bedrijfsleven' \
  --data-urlencode 'context=70'
  '''
  # 3
''' curl --silent -i --get 'http://127.0.0.1:8000/snippet' \
  --data-urlencode 'url=https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/001/169/nl-wbdrazu-k50907905-689-1169654.alto.xml' \
  --data-urlencode 'q=waking' \
  --data-urlencode 'context=70'
  '''
  # 4
''' curl --silent -i --get 'http://127.0.0.1:8000/snippet' \
  --data-urlencode 'url=https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/001/169/nl-wbdrazu-k50907905-689-1169654.alto.xml' \
  --data-urlencode 'q=volgens' \
  --data-urlencode 'context=70'
  '''
  # 5
''' curl --silent -i --get 'http://127.0.0.1:8000/snippet' \
  --data-urlencode 'url=https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/001/169/nl-wbdrazu-k50907905-689-1169654.alto.xml' \
  --data-urlencode 'q=volgens bedrijfsleven ciao' \
  --data-urlencode 'context=70'
  '''

'''
  curl --silent -i -X POST http://127.0.0.1:8000/snippet \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/001/169/nl-wbdrazu-k50907905-689-1169654.alto.xml","q":"\"geldzaken en budgetbeheersing\""}'
  '''
