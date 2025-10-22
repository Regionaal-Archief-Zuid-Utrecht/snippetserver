# venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, HttpUrl
import requests, re, html, os
from lxml import etree
from typing import Optional, List
from urllib.parse import urlparse
import spacy

app = FastAPI()
nlp = spacy.load("nl_core_news_sm")

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

def create_html_snippet(html_list, text, context):
    '''
    Create an HTML snippet from matches in html_list.
    Highlights the words with <em> tags and extracts surrounding context.
    '''
    matches = html_list[0]

    if len(matches) == 1:      
        start = matches[0][1][0]
        end = matches[0][1][1]

        # Build highlighted string
        highlighted_parts = []
        last_idx = 0
        highlighted_parts.append(text[last_idx:start])  # text before match
        highlighted_parts.append(f"<em>{text[start:end]}</em>")  # highlighted match
        last_idx = end
        highlighted_parts.append(text[last_idx:])  # remainder

        highlighted_text = "".join(highlighted_parts)

        # Extract snippet around the matches
        html_start = max(0, start - context)
        html_end = min(len(text), end + context)
        snippet = highlighted_text[html_start:html_end]


    else:
        starts = []
        ends = []
        for m in matches:
            start = m[1][0]
            end = m[1][1]
            starts.append(start)
            ends.append(end)

        # Sort matches by start index so highlighting works correctly
        matches_sorted = sorted(matches, key=lambda m: m[1][0])

        # Build highlighted string
        highlighted_parts = []
        last_idx = 0
        for word, (start, end) in matches_sorted:
            if last_idx > 0 and len(text[last_idx:start]) > 140: # cut longwr paragraphs
                highlighted_parts.append(text[last_idx:last_idx+70])
                highlighted_parts.append(" [...] ")
                last_idx = start-70
            highlighted_parts.append(text[last_idx:start])  # text before match
            highlighted_parts.append(f"<em>{text[start:end]}</em>")  # highlighted match
            last_idx = end
        highlighted_parts.append(text[last_idx:last_idx+100])  # remainder

        highlighted_text = "".join(highlighted_parts)

        # Extract snippet around the matches
        html_start = max(0, min(starts) - context)
        # html_end = min(len(text), max(ends) + context)
        snippet = highlighted_text[html_start:]

    # Escape HTML except for our <em> tags
    snippet = html.escape(snippet)
    snippet = snippet.replace("&lt;em&gt;", "<em>").replace("&lt;/em&gt;", "</em>")
    if len(snippet) > 300:
        snippet = snippet[:300]

    return snippet

stopwords = ['de', 'en', 'van', 'ik', 'te', 'dat', 'die', 'in', 'een', 'hij', 'het', 'niet', 'zijn', 'is', 'was', 'op', 'aan', 'met', 'als', 'voor', 'had', 'er', 'maar', 'om', 'hem', 'dan', 'zou', 'of', 'wat', 'mijn', 'men', 'dit', 'zo', 'door', 'over', 'ze', 'zich', 'bij', 'ook', 'tot', 'je', 'mij', 'uit', 'der', 'daar', 'haar', 'naar', 'heb', 'hoe', 'heeft', 'hebben', 'deze', 'u', 'want', 'nog', 'zal', 'me', 'zij', 'nu', 'ge', 'geen', 'omdat', 'iets', 'worden', 'toch', 'al', 'waren', 'veel', 'meer', 'doen', 'toen', 'moet', 'ben', 'zonder', 'kan', 'hun', 'dus', 'alles', 'onder', 'ja', 'eens', 'hier', 'wie', 'werd', 'altijd', 'doch', 'wordt', 'wezen', 'kunnen', 'ons', 'zelf', 'tegen', 'na', 'reeds', 'wil', 'kon', 'niets', 'uw', 'iemand', 'geweest', 'andere']

def _match_pattern(query: str, text: str, context: int) -> Optional[str]: 

    '''
    Search for query terms in OCR text and return match positions for highlighting.

    The function attempts to find relevant matches of a user-provided query string
    within a larger OCR-extracted text. Matching is performed in multiple tiers,
    from most strict (exact matches) to more relaxed fallbacks:

    1. **Exact phrase match**  
       - Treats the query as a sequence of words.
       - Looks for the exact word order, allowing non-word characters in between 
         (to account for OCR punctuation errors, e.g. `van. het`).

    2. **Paragraph-level multi-word match**  
       - Splits text into paragraphs (on newlines).
       - Tokenizes each paragraph into words.
       - Checks for overlap with query words.
       - If multiple query words appear in the same paragraph, 
         records all word matches (with absolute start–end spans).
       - Paragraphs with more overlapping query words are ranked higher.

    3. **Single-word match**  
       - If no multi-word matches are found, checks each query word individually:
         - First, looks for exact whole-word matches.
         - If none are found, falls back to:
           - Prefix matches (`word*`) → words starting with the query term.
           - Substring matches (`*word*`) → words containing the query term.

    Args:
        query (str): The user search string. Quotes around the query are stripped,
            case is normalized, and stopwords are removed in fallback modes.
        text (str): The full OCR text to search within. Assumes paragraphs are
            separated by newlines.
        context (int): Context window size (number of characters) used when
            constructing snippets outside of this function.

    Returns:
        Optional[list]: 
            - A list of matches, where each match group is itself a list of
              `(word, (start, end))` tuples.
              Example:
                  [
                      [('constructie', (1049, 1060)), ('Onderhoud', (1019, 1028))],
                      [('onderhoud', (3999, 4008))]
                  ]
            - Returns `None` if no matches are found.

    Notes:
        - Start and end positions are absolute indices in the `text` string.
        - The function does not directly build HTML; instead it provides spans
          that can be wrapped with `<em>...</em>` in a later step.
        - Matches are ordered by relevance: multi-word > single-word > wildcard.
    '''

    html_list = [] # use append inside this function and extend to the main list outside?
    # looks for exact match of user query
    query = query.strip("\"") # strip quotes if any
    query = query.lower() # every character to lowercase
    query_words = query.split() # split query in individual words
    pattern = r"\b" + r"\W+".join(re.escape(w) for w in query_words) + r"\b" #\bword1\W+hword2\b

    re_pattern = re.compile(pattern, re.IGNORECASE)
    matches = re_pattern.finditer(text) # an iterable of Match objects
    matches_list = []

    for match in matches: # ultimately append each match to html_list
        match_tuple = (match.group(), match.span()) # (van het, (start, end))
        matches_list.append(match_tuple) # a tuple or the html directly?

    if matches_list: # [("van het", (start, end)), ("van het", (start, end))]
        html_list.append(matches_list) # [] = matches_list


    if len(html_list) == 0: # if the list is empty = no matches yet
        # take	out stopwords
        query_words = list(set(query_words) - set(stopwords))

        target_set = set(query_words)

        # split text into blocks, I introduced a \n at every <TextBlock> when parsing the alto.xml
        paragraphs = re.split(r'[\n]+', text)

        matches_list= []
        for para in paragraphs:
            tokens = re.findall(r'\w+', para.lower())
            overlap = target_set.intersection(tokens)
            if overlap: # checks that a word is found
                for word in overlap:
                    word_pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE) # this is looking for exact match
                    match = word_pattern.search(para) # only first match
                    # get absolute end and start position in te text of the queries matched
                    word = match.group()
                    start = text.find(para) + match.start()
                    end = text.find(para) + match.end()
                    matches_list.append((word, (start, end))) # [("van", (start, end)), ("het", (start, end))]
                if matches_list and len(matches_list) == len(overlap): # just a double check that exists and it got all the words 
                    if len(html_list) == 0:
                        html_list.insert(0, list(matches_list)) 
                        matches_list.clear()
                    elif len(html_list) > 0 and len(matches_list) > len(html_list[0]):
                        html_list.insert(0, list(matches_list))# inserts new par matches at the beginning if they matched more words
                        matches_list.clear()
                    elif len(html_list) > 0 and len(matches_list) <= len(html_list[-1]):
                        html_list.insert(len(html_list), list(matches_list)) # would it be the same to extend?
                        matches_list.clear()
        
        if len(html_list) == 0:
            matches_list = []
             # Looks for words individually anywhere, first exact match 
            for word in query_words:
                pattern = rf'\b{re.escape(word)}\b'
                re_pattern = re.compile(pattern, re.IGNORECASE)
                match = re_pattern.search(text)
                if match:
                    match_tuple = (match.group(), match.span()) 
                    matches_list.append((match.group(), match.span()))
            if matches_list:
                html_list.append(matches_list)
                
            # then wildcards
            if len(html_list) == 0:
                for word in query_words:
                    pattern = rf'{re.escape(word)}\w*'
                    re_pattern = re.compile(pattern, re.IGNORECASE)
                    match = re_pattern.search(text)
                    if match:
                        match_tuple = (match.group(), match.span()) 
                        matches_list.append(match_tuple) 
                if matches_list:  
                    html_list.append(matches_list)

                if len(html_list) == 0:
                    for word in query_words:
                        pattern = rf'\w*{re.escape(word)}\w*'
                        re_pattern = re.compile(pattern, re.IGNORECASE)
                        match = re_pattern.search(text)
                        if match:
                            match_tuple = (match.group(), match.span()) 
                            matches_list.append(match_tuple)  
                    if matches_list:            
                        html_list.append(matches_list)
        
    if html_list:
        html_snippet = create_html_snippet(html_list, text, context)
        return html_snippet
    else:
        return None    


def _find_snippet(url: HttpUrl, q: str, context: int):
    # Security: restrict to configured domains
    host = urlparse(str(url)).hostname
    if not _host_allowed(host):
        raise HTTPException(403, "Domain not allowed")

    try:
        r = requests.get(
            url, timeout=12, stream=True,
            headers={"Accept-Encoding": "gzip, deflate, br"}
        )
        r.raise_for_status()
    except requests.RequestException:
        raise HTTPException(502, "Fetch failed")

    if r.status_code in (403, 404):
        raise HTTPException(403, "Not public")
    if r.status_code != 200:
        raise HTTPException(502, "Upstream error")

    r.raw.decode_content = True

    buf = []
    current_page_sentences = []

    try:
        for event, elem in etree.iterparse(
            r.raw, events=("start", "end"), recover=True, huge_tree=True
        ):
            tag = _localname(elem.tag)

            if event == "start" and tag == "Page":
                current_page_sentences = []

            elif event == "end" and tag == "TextLine":
                strings = elem.findall(".//alto:String",  {'alto': 'http://www.loc.gov/standards/alto/ns-v3#', 'a': 'http://www.loc.gov/standards/alto/ns-v3#'})
                if not strings:
                    elem.clear()
                    continue

                words = [s.get("CONTENT", "") for s in strings if s.get("CONTENT")]
                sentence = " ".join(words)
                doc = nlp(sentence)

                doc_text = "".join([t.text for t in doc])
                alpha_ratio = sum(c.isalpha() for c in doc_text) / max(len(doc_text), 1)
                token_validity = sum(1 for t in doc if t.is_alpha) / max(len(doc), 1)

                if alpha_ratio >= 0.68 and token_validity >= 0.50: # can try tiggling thresholds
                    current_page_sentences.append(sentence)
                    
                # wc_values = [float(s.get("WC", 1)) for s in strings if s.get("WC")]
                # avg_wc = sum(wc_values) / len(wc_values) if wc_values else 1

                # # keep only sufficiently confident lines to clean gibberish
                # if avg_wc >= 0.68:
                #     sentence = " ".join(words)
                #     current_page_sentences.append(sentence)

                elem.clear()

            elif event == "end" and tag == "Page":
                text = "\n".join(current_page_sentences)
                text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
                text = re.sub(r"[^A-Za-z0-9\s.,!?;:'\"-]", "", text, flags=re.UNICODE) # cleaning gibberish

                # look for query match
                html_snippet = _match_pattern(q, text, context)
                if html_snippet:
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
        return {"html": None}
    return {"html": html_snip}

@app.get("/snippet")
def snippet_get(url: HttpUrl, q: str, context: int = 70):
    html_snip = _find_snippet(url, q, context)
    if html_snip is None:
        return {"html": None}
    return Response(content=html_snip, media_type="text/html")

# TESTS

# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/407/nl-wbdrazu-k50907905-689-407001.alto.xml", "water", 70))
# print(shannon_entropy("25 Bakkerij oi falke af op ape fe afaik a aaf aja aj ae aaf ae aaa ok aj op ap af ape aja af aj af af af ape af afp ape aes sja aja a af aak ok af aje sj sj afne B Skell"))
# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/862/nl-wbdrazu-k50907905-689-862690.alto.xml", "water", 70))
# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/811/nl-wbdrazu-k50907905-689-811181.alto.xml", "water", 70))
# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/415/nl-wbdrazu-k50907905-689-415890.alto.xml", "bennekom", 70))
# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/820/nl-wbdrazu-k50907905-689-820075.alto.xml", "water", 70))
# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/820/nl-wbdrazu-k50907905-689-820075.alto.xml", "water vertegen", 70))
# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/785/nl-wbdrazu-k50907905-689-785445.alto.xml", "water vertegen", 70))
# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/808/nl-wbdrazu-k50907905-689-808239.alto.xml", "uitgebreid lager onderwijs", 70))
# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/953/nl-wbdrazu-k50907905-689-953329.alto.xml", "uitgebreid lager onderwijs", 70))
# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/589/nl-wbdrazu-k50907905-689-589717.alto.xml", "vriend hoog", 70))
# print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/970/nl-wbdrazu-k50907905-689-970827.alto.xml", "Voordeliger", 70))