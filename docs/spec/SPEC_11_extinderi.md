# SPECIFICATIE 11 — EXTINDERI PROPRII

**De ce exista acest fisier.** Aici intra functiile cerute de utilizator care **nu exista in ABBYY FineReader PDF 16**. Toate sunt marcate `N`. Nu modifica nicio cerinta din SPEC_01–SPEC_10; le completeaza.

**Regula:** se adauga prin apendare. Fiecare bloc de ID-uri incepe de la 500, ca sa nu se suprapuna cu blocurile existente (001–099, 100–199, 300–420).

Marcaje de sursa ca in celelalte fisiere. Aici toate sunt **N**.

---

## E.5 Unirea documentelor semnate electronic, cu semnaturile pastrate valide

### Contextul

O semnatura electronica (PAdES, CAdES) acopera octetii exacti ai fisierului semnat. Orice unire care muta paginile intr-un fisier nou o invalideaza, in orice program. Verificarea practica din 21.11.2026, facuta cu pyHanko pe doua PDF-uri semnate, a aratat:

| Varianta | Rezultatul verificarii |
|---|---|
| unire clasica (pagini alipite) | semnaturile dispar |
| pagini adaugate prin actualizare incrementala la PDF-ul semnat | semnatura intacta criptografic, dar raportata ca **modificata dupa semnare** (`modification_level = OTHER`, `docmdp_ok = False`) — inacceptabil pentru dosare oficiale |
| originale incorporate neschimbate intr-un PDF-container | fiecare original identic octet cu octet; toate semnaturile **valide** |
| containerul semnat la randul lui | semnatura containerului valida; semnaturile dinauntru raman **valide** |

Concluzia: originalele nu se modifica niciodata; se transporta intregi, iar continutul lor se arata separat, ca copie de citire.

### Cerintele

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| E-500 | `Uneste pastrand semnaturile` | Lansator, panoul de combinare (langa A-024); PDF Editor, `Organize Pages`; meniul contextual din Explorer (langa W-011) | lista de fisiere ordonata (ca la A-023), nume si folder de iesire | minimum 2 fisiere; se accepta orice fisier, semnat sau nu | un singur PDF-dosar, construit dupa E-501…E-505 | fisier ilizibil sau cu parola refuzata → se raporteaza si se sare, ca la J-050 | N |
| E-501 | Originalele raman neatinse | automat | — | **fiecare fisier sursa se incorporeaza ca fisier atasat, octet cu octet.** Dupa salvare se extrage fiecare atasament si se compara amprenta SHA-256 cu sursa | atasamente identice cu sursele | amprenta diferita → operatia se anuleaza si nu se scrie fisierul | N |
| E-502 | Pagina de cuprins si raport de semnaturi | prima pagina a dosarului, generata automat | — | pentru fiecare document: numarul de ordine, numele fisierului, numarul de pagini, semnatarii (nume din certificat, emitent, data semnarii), starea fiecarei semnaturi (`valida`, `invalida`, `modificat dupa semnare`, `nu se poate verifica`, `fara semnatura`), amprenta SHA-256 | pagina de cuprins, cu link catre copia de citire si catre atasamentul fiecarui document | — | N |
| E-503 | Copiile de citire | paginile de dupa cuprins | — | paginile tuturor documentelor, in ordinea listei, ca la A-024. **Pe fiecare pagina, o eticheta: „Copie de citire — semnatura nu este valida pe aceasta pagina; originalul semnat este atasat”.** Campurile de semnatura se elimina din copie, ca sa nu para semnaturi valide; aspectul lor vizibil ramane ca simplu desen, cu link catre original (E-513) | dosar care se citeste si se tipareste continuu | — | N |
| E-504 | Semne de carte | automat | — | un semn de carte de nivel 1 pentru fiecare document, catre prima lui pagina din copia de citire | navigare pe documente | — | N |
| E-505 | Vizualizarea ca portofoliu | setare a operatiei | bifa | **implicit: dosar cu copii de citire (E-503).** Optional: numai portofoliu (cuprins + atasamente, fara copii de citire), pentru fisiere mai mici | — | — | N |
| E-506 | Sigiliul dosarului | dialogul operatiei, optional | certificatul utilizatorului (ca la semnaturile din G.3) | **semnatura se aplica numai dupa ce dosarul e complet.** Dupa semnare se verifica din nou E-501 pe fiecare atasament | dosarul semnat; dovedeste ca setul de documente nu a fost schimbat dupa alcatuire | certificat expirat sau nevalid → mesaj si dosarul ramane nesemnat | N |
| E-507 | Verificarea semnaturilor se face offline implicit | automat | — | verificarea foloseste numai ce e in fisiere si magazinul de certificate al sistemului. **Fara retea, conform regulii de produs „offline total”.** Starea care cere revocare online se raporteaza `nu se poate verifica offline`, nu `invalida` | — | — | N |
| E-508 | Date de validare pe termen lung (LTV) | optiune separata, dezactivata implicit | bifa „Adauga datele de verificare pentru pastrare pe termen lung” | **singura exceptie permisa de la regula offline, si numai cand utilizatorul o activeaza explicit pentru operatia curenta.** Se descarca lantul de certificate si starea de revocare (OCSP/CRL) si se salveaza in dosar, alaturi de originale, fara sa modifice originalele | dosarul ramane verificabil dupa expirarea certificatelor | fara retea → mesaj; dosarul se creeaza fara datele LTV | N |
| E-509 | Avertisment la unirea clasica | Lansator (A-024), `Organize Pages` (E-014, E-015, E-020), Explorer (W-011) | — | **cand cel putin un fisier din lista contine o semnatura, inainte de unirea clasica apare un avertisment** cu lista semnaturilor care se vor pierde si trei optiuni: `Uneste pastrand semnaturile` (E-500), `Continua oricum`, `Anuleaza` | — | — | N |
| E-510 | Export ca ASiC-E | dialogul operatiei, format de iesire alternativ | — | container ASiC-E conform ETSI EN 319 162 (arhiva cu originalele neschimbate si manifest), pentru cazurile in care se cere formatul european | fisier `.asice` | — | N |
| E-511 | Extragerea originalelor | PDF Editor, panoul `Attachments` (F-051, F-052) | dosarul creat cu E-500 | `Save` pe un atasament scrie originalul exact; amprenta se verifica la scriere | fisierul original, cu semnatura valida | amprenta diferita → mesaj | N |
| E-512 | Recunoasterea unui dosar existent | la deschiderea unui PDF in PDF Editor | — | daca fisierul e un dosar E-500, apare o bara de informare cu starea semnaturilor din atasamente si cu butonul de verificare | — | — | N |
| E-513 | Click pe semnatura din copia de citire deschide originalul | copiile de citire (E-503) | — | **pentru fiecare semnatura vizibila din original: aspectul ei (imaginea, numele) se deseneaza in continutul paginii copiei, fara camp de semnatura, iar peste el se pune un link cu chenar albastru subtire.** La trecerea mouse-ului apare textul „Semnatura valida e in originalul atasat — click pentru a-l deschide”; click deschide originalul atasat intr-o fereastra noua (actiune PDF `GoToE`), unde semnatura se verifica. Semnaturile invizibile sau ascunse nu primesc link | semnatura se vede pe copie, iar verificarea ei e la un click | — | N |

### Ce trebuie verificat inainte de implementare

- Acceptarea unui astfel de dosar de catre portalurile folosite (MySMIS si altele) si verificarea semnaturilor din atasamente. **Se testeaza cu un dosar real inainte de faza 8.**
- Comportamentul cu certificate calificate reale (STS, certSIGN, DigiSign, Trans Sped), nu doar cu certificate de test.
- **23.11.2026:** testat cu doua documente reale semnate calificat (CertDigital, 2024, certificate expirate intre timp): originalele raman identice si semnaturile intacte; starea afisata e `valida, dar certificatul a expirat`.
- E-513 (`GoToE`): de verificat ca Adobe Acrobat Reader deschide atasamentul la click; alte programe de vizualizare pot ignora actiunea.

### Faza

Faza 8, impreuna cu `E-*`. Testele E-501, E-503, E-506 si E-509 sunt de prioritate 1: o greseala aici transforma un dosar valid intr-unul invalid fara ca utilizatorul sa observe.

---

## E.6 Pachetul de depunere: fiecare document semnat ramane valid si primeste semnatura reprezentantului legal

Cerut de utilizator pe 24.11.2026 („sa ramana valide chiar daca unesti pdf-uri”), dupa o cercetare cu trei directii (raportul complet: `docs/plan/semnaturi_2026-11-24.md`).

### Contextul

**Limita, verificata in surse:** o semnatura acopera tot fisierul semnat, de la primul octet, mai putin valoarea ei (ISO 32000-2; iText, „Digital Signatures for PDF documents”, p. 27 si 53). Paginile a doua documente semnate separat nu pot sta in acelasi PDF cu ambele semnaturi valide: cel mult semnaturile unui singur document (cel aflat la inceputul fisierului) raman intacte.

**Ce accepta validatorii dupa o semnatura** (Adobe Acrobat, EU DSS, pyHanko; experimente cu semnaturi reale pe 24.11.2026):

| Schimbare adaugata dupa semnatura | Adobe | EU DSS | pyHanko |
|---|---|---|---|
| pagini noi (si din sabloane de pagina) | invalida | TOTAL_FAILED | invalida |
| atasamente sau adnotari | valida, cu avertisment | avertisment | invalida |
| **o semnatura noua (actualizare incrementala)** | **valida** | **valida** | **valida** |
| **un container nou, cu originalele neschimbate** | **valida** | **valida** | **valida** |

Pe un document **certificat** (DocMDP): la `P=1` nicio schimbare nu e permisa; la `P=2`/`P=3` o semnatura noua e permisa, dar un camp de semnatura **vizibil** nou schimba adnotarile paginii, ceea ce certificarea nu permite (verificat cu pyHanko); o semnatura **invizibila** e acceptata.

**Ce cer portalurile:** ghidurile MySMIS2021+ cer fiecare anexa ca PDF separat, semnat electronic de reprezentantul legal (ex. Corrigendum PR Vest, Decizia AM nr. 57/03.07.2024; Manualul MySMIS2021 Proiecte, p. 30), maximum 50 MB pe fisier. Un singur fisier combinat nu se cere. Validatorul EU DSS verifica numai semnaturile PDF-ului, nu si pe ale fisierelor atasate in el.

**Concluzia:** solutia valida peste tot e pachetul de depunere: originalele raman neatinse, iar reprezentantul legal adauga semnatura lui peste fiecare, ca actualizare incrementala. Dosarul E-500 ramane pentru citire si arhivare. **Nu se construieste nicio tehnica prin care un validator sa arate ca semnat un continut pe care semnatarul nu l-a semnat** (atacurile „shadow”, suprapuneri, redefiniri de fonturi): ar fi o inselaciune.

### Cerintele

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| E-514 | `Pachet de depunere` | Lansator, panoul de combinare (langa E-500); dialogul dosarului | lista ordonata de fisiere, folderul de iesire, optional certificatul reprezentantului legal si o arhiva ZIP | **fiecare fisier se copiaza octet cu octet** (amprenta SHA-256 verificata dupa scriere), cu numele `01_<nume>.pdf`, `02_<nume>.pdf`… in ordinea listei; fisierele existente nu se suprascriu | un folder cu cate un PDF pe document (si arhiva ZIP, la cerere) | fisier ilizibil → se raporteaza, celelalte continua | N |
| E-515 | Contrasemnarea reprezentantului legal | E-514, cu certificat | certificatul (ca la G-030) | semnatura de aprobare se adauga **ca actualizare incrementala**, pe octetii exacti ai originalului; vizibila pe ultima pagina, **invizibila pe documentele certificate** (DocMDP P=2, P=3) | fiecare document poarta semnaturile de dinainte, intacte, si semnatura reprezentantului, ultima | certificat expirat sau parola gresita → mesaj, nimic semnat | N |
| E-516 | Verificarea dupa contrasemnare | automat, dupa E-515 | — | **fiecare semnatura de dinainte se valideaza din nou** (offline, E-507); daca vreuna si-ar schimba starea, sau daca originalul nu mai e prefixul exact al fisierului semnat, contrasemnarea se anuleaza si in pachet ramane originalul neschimbat | nicio semnatura existenta nu se strica fara ca utilizatorul sa afle | — | N |
| E-517 | Documentele certificate fara modificari permise | automat | nivelul DocMDP din `/Perms /DocMDP` | un document certificat cu `P=1` **nu se contrasemneaza** (orice schimbare l-ar invalida); intra in pachet neschimbat, cu avertisment | — | — | N |
| E-518 | Verificarile depunerii | automat, inainte de E-515 | marimea maxima (implicit 50 MB, MySMIS2021+) | pentru fiecare document: este PDF; nu depaseste marimea; are cel putin o semnatura; semnaturile existente sunt valide; **semnatura reprezentantului e ultima** dupa contrasemnare | lista avertismentelor pe document, in raportul pachetului | — | N |
| E-519 | Portofoliul PDF | dosarul E-500 in varianta fara copii de citire (E-505) | — | dosarul primeste dictionarul `/Collection`: Adobe Acrobat il deschide ca portofoliu, cu fiecare original in lista si cu semnaturile lui valide | — | — | N |

### Faza

Faza 8, impreuna cu `E-*`. Testele E-515, E-516 si E-517 sunt de prioritate 1: verifica, cu semnaturi reale, ca nicio semnatura existenta nu devine invalida.
