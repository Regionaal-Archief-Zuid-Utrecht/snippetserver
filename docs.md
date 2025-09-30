### _match_pattern

**Search for query terms in OCR text and return match positions for highlighting.**

#### Tests:

1. UNIQUE WORD matches EXACTLY, multiple times in the text.
```
print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/407/nl-wbdrazu-k50907905-689-407001.alto.xml", "water", 70))
```

 first part of code line 161-169
```
html_list = [[('water', (5932, 5937)), ('water', (6096, 6101))]]

html_list[0] = [('water', (5932, 5937)), ('water', (6096, 6101))]
```

2. UNIQUE word matches ONCE
```
print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/415/nl-wbdrazu-k50907905-689-415890.alto.xml", "bennekom", 70))
```

first part of code line 161-169
```
html_list = [[('Bennekom', (2138, 2146))]]

html_list[0] = [('Bennekom', (2138, 2146))]
```

3. UNIQUE word matches as SUBSTRING

```
print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/820/nl-wbdrazu-k50907905-689-820075.alto.xml", "water", 70))
```
goes in forth section line 231 -240
N.B. we use search so we find only the first one, not all of the matches of the same word

```
html_list = [[('watersportvereniging', (784, 804))]]

html_list[0] = [('watersportvereniging', (784, 804))]
```

If two words are matched:

```
print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/820/nl-wbdrazu-k50907905-689-820075.alto.xml", "water vertegen", 70))
```

code in fourth section and finds first match of each word

```
html_list = [[('watersportvereniging', (784, 804)), ('vertegenwoordigers', (1561, 1579))]]

html_list[0] = [('watersportvereniging', (784, 804)), ('vertegenwoordigers', (1561, 1579))]
```

4. MULTIPLE words match EXACTLY, NEXT TO EACH OTHER

```
print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/808/nl-wbdrazu-k50907905-689-808239.alto.xml", "uitgebreid lager onderwijs", 70))
```

first part of code line 161-169
```
html_list = [[('Uitgebreid Lager Onderwijs', (660, 686))]]

html_list[0] = [('Uitgebreid Lager Onderwijs', (660, 686))]
```

5. MULTIPLE words match EXACTLY, NEAR TO EACH OTHER (in the same alto.xml < textBlock> )

```
print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/953/nl-wbdrazu-k50907905-689-953329.alto.xml", "uitgebreid lager onderwijs", 70))
```

goes in second code part from line 181
```
html_list = [[('uitgebreid', (15619, 15629)), ('lager', (15657, 15662)), ('onderwijs', (15663, 15672))], [('lager', (13910, 13915)), ('onderwijs', (13916, 13925))], [('uitgebreid', (7306, 7316))], [('ONDERWIJS', (13583, 13592))], [('onderwijs', (13661, 13670))], [('onderwijs', (14998, 15007))], [('onderwijs', (17366, 17375))]]

html_list[0] = [('onderwijs', (15663, 15672)), ('uitgebreid', (15619, 15629)), ('lager', (15657, 15662))]
```

6. MULTIPLE words match EXACTLY, FAR FROM EACH OTHER (in the whole page of the alto.xml file)

7. MULTIPLE words match as SUBSTRING NEAR EACH OTHER 

```
print(_find_snippet("https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/589/nl-wbdrazu-k50907905-689-589717.alto.xml", "vriend hoog", 70))
```

```
html_list = [[('vriendin', (1883, 1891)), ('hooguit', (3114, 3121))]]

html_list[0] = [('hooguit', (3114, 3121)), ('vriendin', (1883, 1891))]
```

### errors to check

{"url":"https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/784/nl-wbdrazu-k50907905-689-784392.alto.xml","q":"koude water"}

{"url":"https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/605/nl-wbdrazu-k50907905-689-605552.alto.xml","q":"koude water"}

{"url":"https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/576/nl-wbdrazu-k50907905-689-576830.alto.xml","q":"koude water"}

{"url":"https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/823/nl-wbdrazu-k50907905-689-823979.alto.xml","q":"koude water"}

{"url":"https://k50907905.opslag.razu.nl/nl-wbdrazu/k50907905/689/000/068/nl-wbdrazu-k50907905-689-68630.alto.xml","q":"koude water"}