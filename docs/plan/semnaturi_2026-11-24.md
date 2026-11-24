# Semnaturile care raman valide — cercetarea din 24.11.2026

Cerut de utilizator: „sa ramana valide chiar daca unesti pdf-uri”. Trei directii, in paralel:
1. cum judeca validatorii (Adobe, EU DSS, pyHanko) un PDF semnat la care se adauga ceva dupa semnare;
2. ce fac in practica alte programe si ce cer portalurile romanesti;
3. experimente locale cu semnaturi reale (certificate de test, pyHanko 0.38.2).

Nimic din ABBYY sau din alte produse nu s-a descarcat sau decompilat; „reverse engineering” inseamna aici analiza formatului PDF si a regulilor validatorilor.

## 1. Limita, verificata in surse

- O semnatura PAdES acopera **tot fisierul semnat, de la primul octet**, mai putin valoarea ei (ISO 32000-2; iText, „Digital Signatures for PDF documents”, p. 27: „It's not possible to sign specific pages”). https://itextpdf.com/sites/default/files/2018-12/digitalsignatures20130304.pdf
- Semnaturile se pot adauga numai una dupa alta, nu in paralel; documente semnate separat nu se pot uni dupa aceea in acelasi fisier cu semnaturile valide (acelasi document, p. 53).
- Consecinta: intr-un PDF cu paginile tuturor documentelor, **cel mult semnaturile unui singur document** (cel aflat la inceputul fisierului) raman intacte. Nicio unealta nu poate face altfel fara sa falsifice.

## 2. Ce accepta validatorii dupa o semnatura

| Schimbare (actualizare incrementala) | Adobe Acrobat/Reader | EU DSS (politica implicita) | pyHanko 0.38.2 |
|---|---|---|---|
| pagini noi | interzisa → invalida | `PdfPageDifference` = FAIL → TOTAL_FAILED | OTHER → invalida |
| pagini din sabloane (`/Templates`) | permisa la P=2/3 numai daca sablonul era deja in revizia semnata | schimba numarul de pagini → TOTAL_FAILED | OTHER |
| adnotari (FreeText, FileAttachment) | permise dupa o semnatura de aprobare; „schimbari ulterioare” (galben) | avertisment | OTHER (regula pentru adnotari nu exista inca) |
| atasamente (`EmbeddedFiles`) | urmarite ca „atasamente adaugate” | clasate ca form-fill; curate la aprobare | OTHER |
| **o semnatura noua** | **permisa (aprobare; certificat P=2/3)** | **curata** | **FORM_FILLING → valida** |
| date LTV (DSS/VRI), marca temporala de document | permise (ETSI EN 319 142-1 §5.4.2.3) | curate | LTA_UPDATES → valida |

Surse:
- Adobe Digital Signatures User Guide (pp. 40–57): https://www.adobe.com/devnet-docs/acrobatetk/tools/DigSigDC/Acrobat_DigSig_WorkflowGuide.pdf
- Adobe Signature Validation Key: https://www.adobe.com/au/devnet-docs/acrobatetk/tools/QuickKeys/Acrobat_SignatureValidationKey.pdf
- EU DSS, documentatia (protected PDF documents, PDF modification detection) si sursele (`PdfPageDifferenceCheck`, `DocMDPCheck`, `PdfObjectModificationsFilter`):
  - https://ec.europa.eu/digital-building-blocks/DSS/webapp-demo/doc/dss-documentation.html
  - https://github.com/esig/dss
- ETSI EN 319 142-1 V1.2.1: https://www.etsi.org/deliver/etsi_en/319100_319199/31914201/01.02.01_60/en_31914201v010201p.pdf
- Mladenov et al., „Breaking the Specification: PDF Certification” (IEEE S&P 2021): https://pdf-insecurity.org/download/pdf-certification/paper.pdf

**Documentele certificate (DocMDP):**
- La `P=1` nicio schimbare nu e permisa (nici o semnatura noua).
- La `P=2`/`P=3` o semnatura noua e permisa, dar **un camp de semnatura vizibil nou schimba lista de adnotari a paginii**. pyHanko o respinge: „only allowed after an approval signature, not a certification signature” (experimentul din sectiunea 4).
- O semnatura **invizibila** e acceptata.

## 3. Practica

- **MySMIS2021+:** fiecare anexa e un PDF separat, semnat electronic de reprezentantul legal, maximum 50 MB pe fisier. Un fisier combinat nu se cere. Lipsa semnaturii reprezentantului duce la respingere fara clarificari.
  - Corrigendum Ghid PR Vest, Decizia AM nr. 57/03.07.2024: https://www.vest.ro/api/documents/d/939c3ea32bba5e6ab69a9d8cb17f09d4
  - Manualul MySMIS2021 Proiecte, p. 30: https://fondurieuropene.centre.ubbcluj.ro/wp-content/uploads/2023/06/Manual.de_.utilizare.MySMIS2021-Proiecte-FO.pdf
  - Sursa secundara (furnizor): „MySMIS2021 verifica doar ultima semnatura”; semnatura reprezentantului trebuie sa fie ultima. https://alfasign.ro/proiect-finantare-fonduri-europene-firma/
- **SEAP/SICAP:** fiecare document semnat cu certificat calificat (HG 395/2016 art. 60(4)); formatul (PDF semnat sau `.p7s`) il da fisa de date.
- **Alte programe:**
  - Adobe recomanda portofoliul (`/Collection`): componentele semnate raman semnate.
  - Stirling-PDF, Aspose si Syncfusion elimina semnaturile la unire si recomanda semnarea din nou.
  - Niciun producator nu are o „unire care pastreaza semnaturile” in afara de portofoliu sau atasamente.
  - https://github.com/Stirling-Tools/Stirling-PDF/issues/435
- **EU DSS** nu valideaza fisierele atasate intr-un PDF; ele trebuie extrase si verificate separat.

## 4. Experimentele (scratchpad, semnaturi RSA-2048 reale, CA de test)

| Varianta, cu B pus in A semnat | semnatura lui A |
|---|---|
| unire clasica intr-un fisier nou | dispare |
| paginile lui B adaugate incremental | intacta, dar OTHER (modificata) |
| B in `EmbeddedFiles` | intacta, OTHER |
| B ca adnotare FileAttachment | intacta, OTHER |
| adnotari Link/FreeText | intacta, OTHER |
| sablon de pagina instantiat | intacta, OTHER |
| **container nou cu A si B neschimbate** | **valida (NONE)**; B extras: valid |
| **semnatura noua adaugata peste A** | **A valida, semnatura noua valida** |

Pe toate bazele (aprobare, certificat P=2, P=3) rezultatele au fost aceleasi, cu exceptia semnaturii noi: vizibila pe un document certificat → modificata; invizibila → valida.

## 5. Solutia aleasa (SPEC_11 E.6, E-514…E-519)

1. **Pachetul de depunere** (`app/core/pdf/submission.py`):
   - cate un PDF pe document, copiat octet cu octet si numerotat;
   - contrasemnat incremental de reprezentantul legal: vizibil pe documentele obisnuite, invizibil pe cele certificate;
   - verificat dupa semnare: daca o semnatura existenta si-ar schimba starea, ramane originalul;
   - documentele certificate cu `P=1` nu se semneaza;
   - verificarile depunerii: PDF, 50 MB, semnatura reprezentantului ultima;
   - optional, o arhiva ZIP.
   Toate semnaturile raman valide in Adobe, EU DSS si pyHanko.
2. **Dosarul E-500**, pastrat pentru citire si arhivare, cu varianta portofoliu ca `/Collection` (E-519).
3. **ASiC-E** (E-510), pentru destinatarii care accepta containere.

**Nu se construieste nicio tehnica de ascundere sau suprapunere** (atacurile „shadow”, EAA, SSA) prin care un validator sa arate ca semnat un continut pe care semnatarul nu l-a semnat.

## 6. De verificat cu documentele reale ale utilizatorului

- Pachetul pe 2–3 PDF-uri reale semnate calificat (certSIGN, DigiSign, Trans Sped, AlfaTrust): starea fiecarei semnaturi in Adobe Reader dupa contrasemnare.
- Daca e posibil, incarcarea de proba a unui document contrasemnat in MySMIS2021+.
