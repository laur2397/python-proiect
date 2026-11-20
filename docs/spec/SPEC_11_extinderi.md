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
| E-503 | Copiile de citire | paginile de dupa cuprins | — | paginile tuturor documentelor, in ordinea listei, ca la A-024. **Pe fiecare pagina, o eticheta: „Copie de citire — semnatura nu este valida pe aceasta pagina; originalul semnat este atasat”.** Campurile de semnatura si adnotarile lor se elimina din copie, ca sa nu para semnaturi valide | dosar care se citeste si se tipareste continuu | — | N |
| E-504 | Semne de carte | automat | — | un semn de carte de nivel 1 pentru fiecare document, catre prima lui pagina din copia de citire | navigare pe documente | — | N |
| E-505 | Vizualizarea ca portofoliu | setare a operatiei | bifa | **implicit: dosar cu copii de citire (E-503).** Optional: numai portofoliu (cuprins + atasamente, fara copii de citire), pentru fisiere mai mici | — | — | N |
| E-506 | Sigiliul dosarului | dialogul operatiei, optional | certificatul utilizatorului (ca la semnaturile din G.3) | **semnatura se aplica numai dupa ce dosarul e complet.** Dupa semnare se verifica din nou E-501 pe fiecare atasament | dosarul semnat; dovedeste ca setul de documente nu a fost schimbat dupa alcatuire | certificat expirat sau nevalid → mesaj si dosarul ramane nesemnat | N |
| E-507 | Verificarea semnaturilor se face offline implicit | automat | — | verificarea foloseste numai ce e in fisiere si magazinul de certificate al sistemului. **Fara retea, conform regulii de produs „offline total”.** Starea care cere revocare online se raporteaza `nu se poate verifica offline`, nu `invalida` | — | — | N |
| E-508 | Date de validare pe termen lung (LTV) | optiune separata, dezactivata implicit | bifa „Adauga datele de verificare pentru pastrare pe termen lung” | **singura exceptie permisa de la regula offline, si numai cand utilizatorul o activeaza explicit pentru operatia curenta.** Se descarca lantul de certificate si starea de revocare (OCSP/CRL) si se salveaza in dosar, alaturi de originale, fara sa modifice originalele | dosarul ramane verificabil dupa expirarea certificatelor | fara retea → mesaj; dosarul se creeaza fara datele LTV | N |
| E-509 | Avertisment la unirea clasica | Lansator (A-024), `Organize Pages` (E-014, E-015, E-020), Explorer (W-011) | — | **cand cel putin un fisier din lista contine o semnatura, inainte de unirea clasica apare un avertisment** cu lista semnaturilor care se vor pierde si trei optiuni: `Uneste pastrand semnaturile` (E-500), `Continua oricum`, `Anuleaza` | — | — | N |
| E-510 | Export ca ASiC-E | dialogul operatiei, format de iesire alternativ | — | container ASiC-E conform ETSI EN 319 162 (arhiva cu originalele neschimbate si manifest), pentru cazurile in care se cere formatul european | fisier `.asice` | — | N |
| E-511 | Extragerea originalelor | PDF Editor, panoul `Attachments` (F-051, F-052) | dosarul creat cu E-500 | `Save` pe un atasament scrie originalul exact; amprenta se verifica la scriere | fisierul original, cu semnatura valida | amprenta diferita → mesaj | N |
| E-512 | Recunoasterea unui dosar existent | la deschiderea unui PDF in PDF Editor | — | daca fisierul e un dosar E-500, apare o bara de informare cu starea semnaturilor din atasamente si cu butonul de verificare | — | — | N |

### Ce trebuie verificat inainte de implementare

- Acceptarea unui astfel de dosar de catre portalurile folosite (MySMIS si altele) si verificarea semnaturilor din atasamente. **Se testeaza cu un dosar real inainte de faza 8.**
- Comportamentul cu certificate calificate reale (STS, certSIGN, DigiSign, Trans Sped), nu doar cu certificate de test.

### Faza

Faza 8, impreuna cu `E-*`. Testele E-501, E-503, E-506 si E-509 sunt de prioritate 1: o greseala aici transforma un dosar valid intr-unul invalid fara ca utilizatorul sa observe.
