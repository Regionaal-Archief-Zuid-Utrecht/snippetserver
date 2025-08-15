# snippetserver #

Een eerste aanzet voor een snippetserver, nu voor alto.xml.

## Installatie ##

Gebruik een virtualenv:

```bash
python3 -m venv venv
source venv/bin/activate
venv/bin/python -m pip install -U pip
venv/bin/python -m pip install -r requirements.txt
```

## Starten ## 

```bash
venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

## Configuratie ##

Sta alleen requests toe naar bepaalde domeinen (security):

- Omgevingsvariabele: `ALLOWED_HOSTS` (comma-separated)

Voorbeelden:

```bash
# Alleen opslag.razu.nl en subdomeinen
export ALLOWED_HOSTS=opslag.razu.nl

# Meerdere domeinen toestaan
export ALLOWED_HOSTS=opslag.razu.nl,example.org

# Start daarna
venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

## Testen ##

```bash
# GET (HTMX-vriendelijk, HTML response)
curl --silent -i --get 'http://127.0.0.1:8000/snippet' \
  --data-urlencode 'url=https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/031/nl-wbdrazu-k50907905-689-31947.alto.xml' \
  --data-urlencode 'q=belastingen' \
  --data-urlencode 'context=70'

# POST (JSON response {"html": "..."})
curl --silent -i -X POST http://127.0.0.1:8000/snippet \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/031/nl-wbdrazu-k50907905-689-31947.alto.xml","q":"belastingen"}'
```

## Responses ##


200

```json
{ "html": "9 Aug „25 Ocht. 5, ge knipt den staat der Rijksmiddelen bevattende de <em>belastingen</em> door het Rijk ontvangen in de afge loopen 7 maanden van 1925 èn gespe" }
```

204 — geen hit gevonden

403 — ALTO niet public-read / 404 upstream, of domein niet toegestaan (Domain not allowed)

502 — upstream/parse-fout


## HTMX ##

Voorbeeld gebruik met GET die direct HTML terugstuurt:

```html
<div id="snippet"
     hx-get="/snippet"
     hx-vals='{"url": "https://…/file.alto.xml", "q": "term*", "context": 70}'
     hx-trigger="load"
     hx-target="#snippet"
     hx-swap="innerHTML">
  Snippet wordt geladen…
</div>
```

Of via query parameters:

```html
<div id="snippet"
     hx-get="/snippet?url=https%3A%2F%2F…%2Ffile.alto.xml&q=term*&context=70"
     hx-trigger="load"
     hx-target="#snippet"
     hx-swap="innerHTML"></div>
```

## Nginx (rate-limit + CORS) ##

```nginx
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

```   

### Deploy tips (kort) ###

Productie:
`venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2`
