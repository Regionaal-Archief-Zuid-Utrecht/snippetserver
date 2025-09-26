from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, HttpUrl
import requests, re, html, os
from lxml import etree
from typing import Optional, List
from urllib.parse import urlparse
from nltk.corpus import stopwords

stopwords = stopwords.words("dutch")

def create_html_snippet(html_list, text, context):
    '''
    Create an HTML snippet from matches in html_list.
    Highlights the words with <em> tags and extracts surrounding context.
    '''
    matches = html_list[0]

    # Collect all start/end positions
    starts = [m[1][0] for m in matches]
    ends = [m[1][1] for m in matches]

    # Sort matches by start index so highlighting works correctly
    matches_sorted = sorted(matches, key=lambda m: m[1][0])

    # Build highlighted string
    highlighted_parts = []
    last_idx = 0
    for word, (start, end) in matches_sorted:
        highlighted_parts.append(text[last_idx:start])  # text before match
        highlighted_parts.append(f"<em>{text[start:end]}</em>")  # highlighted match
        last_idx = end
    highlighted_parts.append(text[last_idx:])  # remainder

    highlighted_text = "".join(highlighted_parts)

    # Extract snippet around the matches
    html_start = max(0, min(starts) - context)
    html_end = min(len(text), max(ends) + context)
    snippet = highlighted_text[html_start:html_end]

    # Escape HTML except for our <em> tags
    snippet = html.escape(snippet)
    snippet = snippet.replace("&lt;em&gt;", "<em>").replace("&lt;/em&gt;", "</em>")

    return snippet
    
def _match_pattern(query: str, text: str, context: int) -> Optional[str]: 
    html_list = [] # use append inside this function and extend to the main list outside?
    # looks for exact match of user query
    query = query.strip("\"") # strip quotes if any
    query = query.lower() # every character to lowercase
    query_words = query.split() # split query in individual words
    pattern = r"\b" + r"\W+".join(re.escape(w) for w in query_words) + r"\b" #\bword1\W+hword2\b
    print(pattern)  

    re_pattern = re.compile(pattern, re.IGNORECASE)
    matches = re_pattern.finditer(text) # an iterable of Match objects
    matches_list = []

    for match in matches: # ultimately append each match to html_list
        print("Matched text:", match.group())   # The actual matched substring
        print("Start-end position:", match.span()) # Start nindex and end idx in the text
        match_tuple = (match.group(), match.span()) # (van het, (start, end))
        matches_list.append(match_tuple) # a tuple or the html directly?

    if matches_list: # [("van het", (start, end)), ("van het", (start, end))]
        html_list.extend(matches_list) # [] = matches_list
    
    if len(html_list) == 0: # if the list is empty = no matches yet
        # take	out stopwords
        print(query_words)
        query_words = list(set(query_words) - set(stopwords))
        print(query_words)
        
        # split text into paragraph, tokenize the words in the paragraphs, iterate over paragraphs
        # for every paragraph, find intersection with query, if found, get absolute start and end of every word match
        # put all paragraph level matches in a list and sort the list by the letgth of matches in a paragraph
        # this ensures that if all three words match in a par they will be at the index 0 of the list
        # outside of function, take the first element of html list and create the snippet

        target_set = set(query_words)

        # split text into blocks, I introduced a \n at every <TextBlock> when parsing the alto.xml
        paragraphs = re.split(r'[\n]+', text)

        matches_list= []
        for para in paragraphs:
            tokens = re.findall(r'\w+', para.lower())
            overlap = target_set.intersection(tokens)
            if overlap: # checks that a word is found
                print(overlap)
                print(len(overlap))
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
                print(pattern)
                re_pattern = re.compile(pattern, re.IGNORECASE)
                match = re_pattern.search(text)
                if match:
                    match_tuple = (match.group(), match.span()) 
                    matches_list.append((match.group(), match.span()))
            html_list.extend(matches_list)
            # then wildcards
            if len(html_list) == 0:
                for word in query_words:
                    pattern = rf'{re.escape(word)}\w*'
                    print(pattern)
                    re_pattern = re.compile(pattern, re.IGNORECASE)
                    matches = re_pattern.search(text)
                    if match:
                        match_tuple = (match.group(), match.span()) 
                        matches_list.append((match.group(), match.span()))   
                html_list.extend(matches_list)
                if len(html_list) == 0:
                    for word in query_words:
                        pattern = rf'\w*{re.escape(word)}\w*'
                        print(pattern)
                        re_pattern = re.compile(pattern, re.IGNORECASE)
                        match = re_pattern.search(text)
                        if match:
                            match_tuple = (match.group(), match.span()) 
                            matches_list.append((match.group(), match.span()))              
                    html_list.extend(matches_list)
        
    if html_list:
        return html_list
    else:
        return None    



text = "\n ers \n ners e \n 022 \n   \n   \n   \n ezien op de Huishoudbeurs \n \\orige week vond in de RAI in Amsterdam de jaarlijkse Huiswudbeurs plaats. Het aantal deelnemers en verhuurde meters ‚npervlakte was nog weer groter dan vorig jaar. De redactie van Wonen tussen de Rivieren” bracht voor u een bezoek aan deze kurs. Een uitermate vermoeiende speurtocht naar nieuwe din- ‚n. Want echt veel nieuws was er dit jaar niet te zien._ Slimme jngen waren er wel, een aantal zochten wij vooor u uit. \n kunststofkozijnen \n nakta presenteerde op de beurs haar ogramma kunststofkozijnen, \n schuifdeuren, blinden en kozijnen met rolluiken. Een Duitse vinding waarmee al een aantal jaren ervaring is opgedaan in Duitsland, Engeland en Denemarken. Kunststofkozijnen komen we in Nederland nog niet zoveel tegen. Rond de 6% van onze woningen heeft deze kozijnen. Exakta verwacht dat \n daar gauw verandering in zal komen._ \n Het produkt is maar liefst 12 à 15% goedkoper dan hardhoutenkozijnen. \n Goedkoper in aanschaf dus maar ook in gebruik. Onderhoud is niet nodig en de constructie is zodanig dat het raam letterlijk potdicht zit. Dat betekent een aanzienlijke besparing op uw energierekening. \n Een praktisch voordeel vn dit kozijn is dat het naar binnen scharniert en dat betekent moeilijk toegankelijk voor de inbreker en gemakkelijk schoon te houden. Voor nadere informatie kunt u bellen met Exakte in Winterswijk, tel. 05430-19725. \n Energiezuinige verwarming \n Wij waren de Zibro-Kamin al eens tegen gekomen, echt nieuw is het dus niet maar zeker de moeite waard. Zibro-Kamin is een verplaatsbaar petroleumkacheltje. Een petroleumkacheltje zonder afvoer. Echter voorzien van het zogenaamde TURBO-systeem waardoor er bij gebruik geen rook of geur ontstaat, giftige gassen zoals koolmonoxide tot een absoluut nulpunt worden gereduceerden er een \n hoog rendement uit de brandstof wordt gehaald. Daar komt nog bij dat u het kacheltje kunt verplaatsen naar de ruimte die u verwarmd wilt hebben. \n Ideaal, zeker in deze tijd van het jaar. De Zibro-Kamin wordt geleverd in verschillende uitvoeringen. Prijzen vanaf f 695,-. \n Nieuw voor in uw keuken \n Franke Roestvrijstaal Nederland bv is een Helmonds bedrijf dat zich toelegt op de produktie van onder andere aanrechtbladen. Op de Huishoudbeurs was de nieuwste vinding van dit bedrijf te zien: Franke Compact-Fradura. Een smal aanrechtblad (60 cm) dat kan worden ingebouwd in elk keukenblad. Smal maar wel met twee spoelbakken. Zoals u op de foto kunt zien voorzien van een diepe en een halfdiepe bak. In het midden zit de vondst: een klein afdruipbakje met afvoer. Daar kan men ontzettend veel mee doen. Een fles wijn koud zetten, de spruitjes wassen of een klein afwasje doen. Het blad is leverbaar in nieerdere uitvoeringen van roestvrijstaal tot wit gemêleerd. \n Quarzolux: de nieuwe vloerbedekker \n U heeft trek in een plavuizenvloer maar u kunt niet de juiste keuze maken. U loopt rond met een tapijtmotief in uw hoofd. In zo’n geval is de Quadrolux de oplossing voor u. Een sedimentsgesteente met hoogwaardige kunststoffen als bindmiddel. Het biedt het voordeel dat het oogt als tapijt maar onderhoudsarmer is dan vloerbedekking en plavuizen. Het motief is een beetje gemêleerd en dat betekent \n dat je er eigenlijk niets opziet. Een j keer per week stofzuigen is voldoende. : een erg mooi produkt als je ervan , houdt. Maar met het nadeel van een / \n plavuisvloer: niet voetwarm. \n Een betaalbaar \n en eenvoudig \n te monteren smeedijzeren tuinhek \n Het Amsterdamse bedrijf Henco brengt een betaalbaar smeedijzeren sierhek op de markt. Een soort doe het zelf hek. U krijgt de onderdelen thuis aangeleverd en kunt dan binnen één dag plaatsing en verven verzorgen. Bij een hoogte van 60 cm. komt het hek in de meest eenvoudige uitvoering op f 45,- per strekkende meter. In de maand april krijgt u daarop nog een zogenaamde ‚‚beurskorting” van 5%. \n   \n   \n   \n Velke-gids ‚Vloerenl n wanden’ \n verschenen \n ‘ Noppenrubber of geribd rubber is redelijk intensief in onderhoud. Na het schoonmaken liefst droogwrij- \n | wnanders zetten kalkresten zich af \n ‚ tndom de noppen en tussen de \n | nbbels. \n * Vuil geworden witte voegen in een, tgelvloer kunnen worden gereitied door in het schrobwater een \n | flinke scheut zoutzuur te doen. \n * Dit soort tips maar vooral de (on) \n L mogelijkheden van vloeren wandbedekkers maken de nieuwe WELKE-gids over vloeren en wanden demoeite waard. Informatie die onmisbaar is bij de keuze, de aanschaf en het onderhoud van vloeren en wanden. \n De gids kost f 4,95 en is verkrijgbaar bij demeeste tijdschriftenwinkels. \n h h \n ‘RABO introduceert Wmnspaarplan \n h V. :!în Nâture zijn wij Nederlanders een velènarzaam_\\olkje. We hebben graag E aappelî]c voor de dorst, iets achter moetn : vMaar om te kunnen sparen & n wel de ruimte zijn, men moet | SS over kúnnen houden. .‘…nll(e)ts Overhouden in een tijd van te- ‚ke%i_kpeln_de inkomens is niet gemak- ‘ anjrﬁ îer wel wat _fmancì'e'le ruimte E d…*t er op de juiste manier ge- & ard worden. Met de hoogst moge- ‘Stlhiêenopbrcngs‘t aan rente. En misÌgelĳkh'()ä\\u“ situatie afgestemde moE cden voor het tussentijds opn van het geld. ìí\\íïî)oban}gen hebben een nieuwe 'gewoonrmìgfmtro_duceerd die buitene g)uch1_kt is voor mensen die |D WL)È… huis zouden willen kopen. lrekkel__ìn5paarplan biedt een aan- 'm0geli'lll\\»he rente en ruime opnameE aarjìd )eden. Vergeh;kbgaar met de e aa ä)$pgá\\_r_x'ormen. Nieuw is dat E kar Ër vrij over het gehele beÌvefuuizìrrìì eschikken bij huwelijk én enge d_g; Met andere woorden ook E ììtu%ldanlîjagìenw_onen kunnen Vordt \\‘erhuigâ% eschikken mits er Îd?1rkïil'ntlâ N geval een huis gekocht 0“_anng Ï spaarder over de totale E eeâ… rente een premie van 25% Faane maximum van f 1250,-. | met e€n€eRr;b(ï?]evn deze koopwoning emie | : ypotheek dan wordt de im y er oogt tot 50% met een denkt inmde\\tan f2500,. Wie dus w0ning E l…0<3k()crinst eens een koop-: kĳkenofdpen oet er goed aan te : €ze spaarvorm voor hem/ \n   \n   \n   \n   \n Rondkomen volgens plan \n Overheid en bedrijfsleven hebben samen een instituut opgericht dat zich bezighoudt met de bewaking van het gezinsbudget. Dat instituut, het NIBUD, probeert door middel van voorlichting, informatie en adviezen, consumenten te helpen op het gebied van geldzaken en budgetbeheersing. Want het ísingewikkeld met al die banktoestanden, betaalcheques enzovoort. U kunt bij het NIBUD terecht voor informatie over het maken van het kasboek, het maken van een gezinsbudget, het zakgeld wat het kind nodig heeft en hoe u VAN reserveren voor onverwachte uitgaven zoals de vervanging van een kapotte wasmachine. Vindt u het met geld omgaan een \n moeilijke zaak dan moet u de brochure „rondkomen volgens plan” eens aanvragen. Aan de hand van duidelijke instructies en overzichtelijke voorbeelden kunt u er stap voor stap uw eigen financiën mee in kaart brengen. \n Daarnaast bevat deze brochure een uitgebreide adressenlijst van hulpverleningsinstanties. De brochure kost f 7,60. Het instituut is telefonisch bereikbaar van 08.30-12.30 uur op nr. 070-888840. \n Een voorbeeld van een begrotingsoverzicht, treft u hierbij aan. Het geeft een overzicht van wat er per maand aan geld binnenkomt en eruit gaat. Vult u het maar eens in. \n Het in de handhouden van uw gezinsbudget \n natonod nsituid voor Dudgeiooriching \n 4 \n nioud \n De post inventaris Uitg: \n   \n in het gezinsbudget \n   \n jave NIBUD, postbus 19291 2500 CG Den Haag \n   \n INKOMSTEN \n ® Salaris . . . Uitkering .. Pensioen . . .. Alimentatie . . .. Huursubsidie . .. Kinderbijslag . . . Vakantiegeld . . . . Extraverdienste(n) . . Eenmaligeuitkering . . \n Reisen onkostenvergoe Kamerverhuur ….. \n Afdracht kostgeld Riĳjkspremie (woning) \n 13emaand, gratificatie . . . ding . Tegemoetkoming ziektekosten Telefoon-onkostenvergoeding \n Teruggave belasting en premie volksverzekering . . . . . .. \n   \n Totaal \n   \n UITGAVEN \n Huishoudgeld ® Voeding . . \n Rookwaren . . . . . .. (incl. dierenarts) . . …. kleding P \n kapper . . . .. \n kinderoppas Geschenken, kollektes . \n Zakgeld . . . . . \n Wasen schoonmaakartik \n ® Snoep,gebak, dranken . .…. \n Voeding en overige kosten huisdieren \n elen, reiniging \n Persoonlijke verzorging, toiletartikelen, \n Huishoudelijke hulp, glazenwasser, \n Diversen (postzegels, bloemen, losse tijdschriften, enz.) . . . . \n   \n Totaal huishoudgeld \n   \n   \n Vaste Lasten \n ® Huur/aflossing + rente; servicekosten/erfpacht \n ® Energiekosten . .. \n ® Water . . . \n ® Heffingen: \n onroerend goed belasting, reinigingsrechten, milieubelasting, rioolrecht, \n waterschapsheffing \n ® Telefoon (abonnement + gesprekskoéte-n)' \n ® Verzekeringen . . . .. ® Schoolen cursusgelden . \n ® Omroepbijdrage + kabel-t.v. ® Vaste vervoerskosten: \n bus-, treinof tramabonnement, wegenbelasting, autoof bromfietsverzekering, \n garagehuur . . . . . ® Alimentatie .…. ® Afbetalingen . . . ® Aflossing krediet . . \n ® Contributies, lidmaatschappen .. ® Abonnementen, kranten en tijdschriften \n   \n Totaal Vaste Lasten \n   \n Reserveringsuitgaven/Grote uitgaven ©® Aanschaf en onderhoud kleding en \n schoenen . . . .. \n ® Aanschaf en onderhoud inventaris (meubilair, apparatuur, stoffering) \n Onderhoud huis en tuin \n Ziektekosten niet vergoed (brillen \n tandaris:etc] _ \n Vrijetijdsuitgaven (hobby, sport, muziek, \n boeken): … _ Uitgaan . . . .. \n Vakantie en eventueel weekenden \n Extra sparen ©® Onvoorzien \n   \n Totaal reserveringsuitgaven \n   \n Eindtotaal uitgaven \n   \n   \n   \n   \n   \n   \n   \n … \n Hoe belangrijk \n E , \n is de rente? \n Zoals u uit het op deze pagina afgedrukte hypotheekrente-overzicht kunt concludereren is het rustig op het rentefront. Toch houden de Nederlandse deskundigen hun oog nauwlettend gericht op de Verenigde Staten. En daar komt slecht nieuws vanar Interessant i. \n daan. Het disconto is daar onlangs met een half procent verhoogd. Tot nu toe \n zijn de Nederlandse banken niet gevolgd. Doorgaans zijn wij Nederlanders niet zo geïnteresseerd in financieel nieuws. Met de rente ligt dat anders. Vooral de eigen woning-bezitter heeft daar direkt mee te maken. Vooral in het begin van deze tachtiger jaren, toen de rente in zeer korte tijd sterk steeg (zie grafiek), was er zelfs sprake van direkte paniek. Vraag die blijft „‚is die rente echt zo belangrijk?”’ \n Geschiedenis \n Perioden van extreme rentestijgingen komen vaker voor. Zoals u kunt zien in de grafiek was daarvan ook sprake in het midden van de zeventiger jaren. Wanneer we nu naast deze rente grafiek de prijsontwikkeling van woningen zetten dan ziet u dat ondanks die hoge rente de prijzen op de woningmarkt zijn blijven stijgen. Hoge rente was toen geen reden om geen eigen \n woning te kopen blijkbaar. De verklaring voor dit verschijnsel is eenvoudig. In die tijd verkeerden we allemaal in een halleluja-stemming voor wat betreft de economische vooruitzichten. Het kon als het ware niet op. De positieve toekomstverwachtingen zijn nu aanmerkelijk gewijzigd. Wie is niet bang voor werkloosheid. En in zo’n situatie wordt de rente/een extra negatieve factor bij de aankoop van een eigen huis. \n De hamvraag \n De hamvraag is nu wat moet de aspirant-koper van vandaag doen? Rente heeft invloed op de kosten van het wonen. Een hoger rentepercentage betekent meer betalen voor hetzelfde. Als we spreken over „betalen” dan zijn: dat de kosten van het wonen. Naast rente worden die kosten sterk bepaald door de hoogte van de aankoopsom. \n Iedereen weet dat de prijzen op de woningmarkt de afgelopen jaren fors zijn gedaald. Ingewikkelde berekeningen tonen aan dat wanneer iemand in 1975 met de hoge rente en het hoge prijspeil kon kopen dat dat nu ook kan. Zijn inkomen is sindsdien zelfs nog gestegen. Waar het allemaal omdraait is de maandlast. En daarnaast moet de aspirant-koper weten wat hij doet, wat de consequenties van de aankoop over x jaar zullen zijn. Denk niet te snel dat een koopwoning onbereikbaar is, maar maak uzelf ook niet gek met dingen die u straks niet kunt betalen. Een huis kopen begint met rekenen. Maar om de rente hoeft u het niet te laten. Dat is duidelijk. Hele slimme mensen zeggen zelfs: „Lage woningprijzen ook al is de rente hoog, dat is een ideale situatie. De overheid draagt toch bij in de rente maar niet in de hoge prijzen”’. \n   \n Wonen in een van de oudste boerderijen \n van Rossum \n Rossum is een fraai dorp op 6 kilometer ten oosten van Zaltbommel. Onze woondroom is dit keer. een monumentale woonboerderij gelegen in de bebouwde kom van dit dorp. Winkels, postkantoortje, dokter en bushalte op enkele honderden meters afstand. De woonboerderij, een monumentenpand, biedt naast modern comfort bijzonder veel privacy. Om u een indruk te geven. \n De rechterzijde van het huis waar de eetkamer en keuken gelegen zijn ligt aan ’> straatzijde. Maar is van deze weg gescheiden door zes meter tuin, een sloot een een groenstrook van 5 meter. Vanuit de woonkamer kijkt men in de tuin (25x25 m). Achter de tuin ligt een boomgaard. Vanuit de kamers op de bovenverdieping kijkt men uit over de boomgaarden naar de Waaldijk en het Slingerbos. Totaal grondoppervlakte £2000 m2. \n De boederij is gebouwd rond 1660 en is daarmee een van de oudste boerderijen van het dorp. Het huis ligt op een wat hoger gelegen stuk grond. He \n woongedeelte is in de afgelopen 15 jaar ingrijpend verbouwd en gemoderniseerd. Maar liefst vier slaapkamers op de geheel vernieuwde bovenverdieping. De huiskamer heeft een oppervlakte van 48 m2? en is voorzien \n ‚van een parketvloer, spouwmuren, \n een open haard en een nieuw plafond, de elektrische leidingen zijn geheel vernieuwd. \n Het achterhuis draagt nog de sporen van het verleden. De deel heeft de kenmerken van een koeienen paardenstal behouden. Hier liggen nog grote mogelijkheden voor uitbreiding, bijvoorbeeld van de woonkamer. Het pand staat op de monumentenlijst. Dat betekent dat de kosten van onderhoud aftrekbaar zijn. Groot onderhoud, bijvoorbeeld van het rietendak, wordt door de overheid gesubsidieerd. \n Voor nadere informatie over dit unieke object kunt u terecht bij verkopend makelaar Nieuwdorp, tel. 04180-2474 in Zaltbommel. \n   \n   \n   \n Kwijtschelding belasting \n Uw woonvragen kunt u voorleggen aan de redactie. Vermeld uw naam en adres en telefoonnummer en adresseer uw vraag aan de redactie van \n PT E er \n P \n P d \n hetling \n „Wonen tussen de Rivieren”, postbús 102, 4130 EC Vianen. \n Wij zijn een gepensioneerd echtpaar woonachtig in een eigen huis. Er zitnog een kleine hypotheek op. Wij krijgen AOW en hebben daarnaast een bescheiden pensioen. De eenmalige uitkering voor de minima hebben wij reeds twee keer toegewezen gekregen. Denkt u dat wij in aanmerking komen voor kwijtschelding van de onroerend goed belasting? \n De familie H. K. te Z. \n Wij hebben uw vraag voorgelegd aan de organisatie Konsumenten Kontakt in Den Haag. Daar is men van mening dat u gezien het verschil tussen de getaxeerde waarde van het huis en de beduidend lage hypotheeksom wel degelijk ogb-belasting moet betalen. En daar doet het feit van een eenmalige uitkering niets aan af. \n Heeft u een soortgelijk probleem en komt u er niet uit bel dan even met genoemde ocnsumentenorganisatie, tel. 070-458000. De hierbij afgedrukte folder geeft alle nadere informatie. E \n t \n s a \n o E \n e \n E \n"

text1 = "\n DOORNSE COURANT „oe KAAPT \n 7 KINDERCORDURDT BROEKEN. ge \n “DAMES ROKKEN : „SPIJKERROKJES E EN TUINBROEKEN, \n ; peuterkleding. \n | \n _HERENBROEKEN 5 45.00 ida 45,00. \n en kn A 0. 00 ë \n Kom: eens kien, ookpaet de nieuws collectie En \n Chr. ‘Sctiöldigeméenschap. voor - Gymaasium, Atheneum en Havo * \n Pane 6c,\'3941 ZX boem Ee ‚Rector: drs. J. ‚ Gispen … Set \n „OPEN DAG: \n voor r toekomstige ferien en hun ouders op 4d \n | zaterdag 17: februari a. s. \n de aula van de school om u te. informeren over r het in „Revius Lyceum. / : \n ‘Daamaast heeft ude gelegenheid rond te kijken i in, \n „puders, \n „in Ja do: 8 La Strada a \n - za lo The Flying. Pickets \n Wij ontvangen ugraag om 9.30 uúr.of 10.45 uur in * \n han school en te spreken met docenten, leningen en_ \n “VERWARMINGSSPECIALIST . \n WILLEM KOUDIJS \n ‚ voor aanleg’ van uw cv-installatie \n DE “Sanitair en loodgieterswerk - u Loödieters., Gasen Wateritersbedij \n Tel. 0343452635, na:18.00 uur 54796 - \n ‘Service na a 6, vur 54796, 511 te en’ ‘57003 « en © © Kon \n + \n Joost Prinsen. in La Strada.” „foto: Kors van Bennekom. * \n ‘Période: 8 t/m 18 febr. \n : Fotó: \n et \n „Toneelbewerking, van de gelijknamige EE film van Federico Fellini Zen | Joost Prinsen, Heddy Lester ea. \n Ee 20. 15-.uur „Theater. \n | vrg Swing. Support m.m.v. _Deborah Browh Sl EE En \'e D 5 \n n het showballet John Felter Presentatie: Pim Jacobs “SSZ …: 20.15 ur. Stadshial. Ô \n vA capella popconcert , : 20.15 uur Theater, tT Koffietorieel: at > Frank Degruyter vertelt. \n “> Roald Dahl. 7 aen 12 uur Theater, \n ‚do 15 Paul de Leeuw \n vr 16 Beste maatjes. …::. …* 20. 15 uur Theater. \n ’ Kaartverkoës v. a. één week” voor. het evenement “ma t/m vr. 12.30-17.30 uurs, kassavolgnummers v.d.» 8, 30 var; telefonisch reserveren. van „L4-17.30 „ur, “|L \n En zo. u \n Jeevscccvcovecvee \n “bakje \n lors \n „„Secolaaljes, 4 smaken \n 1 „59 d \n en \n pak Er „CHOCO LEIBNIZ; “makktpuur 1 89 ‘bus 7 p ENKHUIZER - JODEKOEKEN 1. ‚98 | 400 gram \n 1.98 \n dubbelpek \n H-0 vertadur. __ 2. 29 \n [|AUGDRKEN EEN 249 \n “| rol. \n EPO Tarwe | \n fles \n | ln RHONE” | | 4. 49 \n oF RIJSTWAFELS \n 0. 89: \n ShieLkook DESSERTRUST \n KROS \n er \n il lainens Rantane \n 219 \n oo \n CALVE sushus NE Je | 69 \n See KAPUCIJNERS \n MELITTA FLTRAAKIES \n 1.98 \n Haise GLORIE | HALVARINE \n ĳ got \n Ad ‚os \n . ER \n DÉ. \n _nu dubbele vaardonen : \n 287 \n 0. e9 | eel 7 \n | TOILETBLOK \n 119 \n angbroskerweg’ 1Doorn Tel. 1291 4 \n _tel-033-726094. fB, \n E Sgchildeisbedrijt E. Ovérweel \n Ì Bentincklaan 18, Leersum. Tel: 03434.52276 \n OOK Uw WINTERSCHILDER \n Voor: kolen,” \n | “OLIEHANDEL \n _” Telefoon-0343012750. \n Gn „hulsbrandolle, …, petroleum en - “flessen gas \n het Jüiste adres: \n BOSMAN mm \n Kampweg 50, „Doorn. - \n Lambda-sonde.. \n NANCIERIN Ko \n e | “De ander: mogelijkheid is ‘een n.lening: over — ri. 48 maánderi met een: laag reritetarief van 7,9% is: effectief Ondertussen’ ‘profiteert u in ‘beide: | gevallen van wat de 205 allemaal te bieden” \n - heeft: comfort, ‘ruimte “° “én, betrouwbaárheid De zeer zuinige en. pie “ige 205 is: niet âlleen uitgerust. met een soepel. zi a schakelende 5bäk “kn maar ook met?n  benzine3 injectiemotor en} ’n Sriteg-katalysator met een \n Zo. voldoen. vrijwel alle 205 medelen Jaan. ‘de: strengste ‘Europese milieu-normen,…* \n E 33 uitvoeringèn. Van diesel tot benzinemotor. ze ‘Van. 3-deurs tot 5-deurs. Van GTI tot Cabrio: … | \n _ En wat dacht uvan al die fraaie extra’s bij de, d \n | “Accent of de Junior. EEE | BODEN ze „Kortom, „met dit: financietingsanbod \n zijn úw mogelijkheden. onbeperkt. _ \n „Alle reden om niet lang te wachten. én \n en vandaag: nog even. bij. Ons: langs te: komen „U bent van harte welkom.” : \n ‚ PEUGEOT 205 | dt Sterk nummer. we \n NDER DE GEBRUIKELIJKE VOORWAARDEN VAN HUURKOOPOVEREENKOMST. WAAREIJ. DE PEUGEOT-ORGANISATIE DE en Ee \n SNDE 16 AUTOMATIC, PAIZEN, INCLUSIEF BTW, OEVER AFLE \n EVERINGSKOSTEN -465,- WIJZIGINGEN, VOORBEHOUDEN. sj \n ‘Geopend: Maandaë en | dinsdag € os. 00. tot 18. oo. „Donderdag 08.30 tot. 18. oo’ Vrijdag 08.30 tet 21.00 Zaterdag. 08. 30 tot 16. 00 \n | emme | ElERSALADE : „8.98 || __ VIZIR vragen Baloe. 1 wee #C_…_|| WORST 9. 2.69. 400 gram Ok on Ì PG jen KEE ‘caliworsr HER BELEGEN Kaas ; je Ak 1 09 âsterren nm 5. 75. CO eN as |-[-GEBRADEN KALFSGERAKT | 679 IE 1. 19 „5 | TisGER oF - \n BESAMBDL \n 129) \n _ Woensdag 08. 30 tot 43. óo. \n AUTORUNS IN EEN FAT 10 5 GEWOON. N GOE TP \n ee „onderbouwde theorielessen id ‘opbouwende praktijklessen en … Ne * examentraining Waarop men, kan, bouwen! 5 \n 03434-51688 \n deka weg voo belet. \n Rijschool met ’n’ visiel\' An De „Bars. H. vd. Boschstraat tb, 2958. CD Amerongeë, ‘elfoon ozaaa stens \n e de auto van ‘het j jaar 19891 zi ede \n JOHN HUISMAN \n maakt van elke beginner m/v. Ee Ge „de bestuurder van het Jaart \n want hij ‘geeft \n “AUTORIJSCHOOL … JE \n _JOHN HUISMAN - \n we \n Ps Doornebal;’Groep 5-in - te-verlénen voót het opri \n edeputeerde’ staten van \n ichten en in werki het houden van mestvärké \n berg (gemeente. Leersum \n hét gemeentehuis: van gak hijs aatweg \n huize vande bode; euendlen, liggen de \n 1 bezwaren schriftelijk-worden iní … Utrecht, Postbus-80300; 3508 TH Utrecht, degene die ‘bezwaren ‘hebben; i \n Werkdag van 9.00 tot 12, 00 uur en t \n Hoflaan 29 in Leersum: tijdens de opení \n je in het gemeentehuis van: ‘Amerongen; Hof van.9.00: tot 12.00 uur.en op maandag tevèns va \n Hof 3 in Amerongen, \n stukken ook na 21 feb: \n BE am gon E Wet algemene, bepalingen miliduhygiëne/Hinderwet. k Utrecht maker bekend dat zij voorhemens zijn raon En Overberg eên vergunning ingevolge de Hinderwet’ Den ng hebben van een inrichting voor ens, ‘Tegkippen’en rundvee aan de Groep 5 in Over- . “- ). Aan de \\ vergunning worden voorschriften’ ver/ \n 1990 nog, elke vanda ter « el tot het einde van de termijn. \' n de beschikking op de. aan-; ichting\'op de-stukken worden … \n bn \n TIE et b \n evers in de open are:bibliotheek,- \n lúcht: en hinder van de dieftst Wateren : \n en die eäntonen daartoe’ rèdelijkerw, \n vens niet bekend te ma \n die‘een: ‘bezwaarschrift malsnt kan: daarbij \n miet 21 februari 1990 kunnen gemotiveerde: gebracht bij gedeputeerde, staten van”: door de regen de adviseurs,"

# print(_match_pattern("Onderhoud constructie letterlijk", text, 70)) # words in same par but not next to each other
# print(_match_pattern("Zibro-Kamin", text, 70))
# print(_match_pattern("Zibro-Kamin is een verplaatsbaar", text, 70))
# print(_match_pattern("\"Kors van Bennekom\"", text1, context=70))
# print(_match_pattern("\"Kor van Benneko\"", text1, context=70)) # doesn't work as expected and matches only using both wildcards at both sides

html_list = [[('constructie', (1049, 1060)), ('Onderhoud', (1019, 1028)), ('letterlijk', (1085, 1095))], [('onderhoud', (3999, 4008))], [('onderhoud', (4478, 4487))], [('onderhoud', (9031, 9040))], [('onderhoud', (9088, 9097))], [('Onderhoud', (9147, 9156))], [('onderhoud', (13812, 13821))]]

print(create_html_snippet(html_list, text, 70))