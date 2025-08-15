# snippets #

Een eerste aanzet voor een snippetserver, nu voor alto.xml.

## Starten ## 

"""
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
"""

## Testen ##

"""
curl --silent -i -X POST http://127.0.0.1:8000/snippet   -H 'Content-Type: application/json'   -d '{"url":"https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/031/nl-wbdrazu-k50907905-689-31947.alto.xml","q":"belastingen"}'
"""

## Responses ##


200

"""
{ "html": "… de <em>Amerong</em>sche Courant …" }
"""

204 — geen hit gevonden

403 — ALTO niet public-read / 404 upstream

502 — upstream/parse-fout


## Nginx (rate-limit + CORS) ##

"""
# http {}
limit_req_zone $binary_remote_addr zone=snip:10m rate=5r/s;

# server {}
location /snippet {
  limit_req zone=snip burst=20 nodelay;
  proxy_pass http://127.0.0.1:8000;
  add_header Access-Control-Allow-Origin *;
  add_header Access-Control-Allow-Headers Content-Type;
  if ($request_method = OPTIONS) { return 204; }
}

"""   

### Deploy tips (kort) ###

Productie:
`uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2`

Zet HTTP compressie aan voor ALTO aan de bron/CDN.
Frontend: laad snippets lazy (IntersectionObserver), individuele calls.