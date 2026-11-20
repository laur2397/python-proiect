# Cum pornesti

> **Inainte de orice, citeste `SETUP.md`.** Acolo sunt conditiile
> preliminare reale — abonament Claude, Python, Git, si mai ales
> Tesseract (care NU se instaleaza cu pip). Fisierul de fata presupune
> ca tot ce e in `SETUP.md` functioneaza deja.

## 1. Instaleaza Claude Code

**Windows**, in PowerShell:

```powershell
irm https://claude.ai/install.ps1 | iex
```

Alternativ, daca ai deja Node.js 18 sau mai nou:

```powershell
npm install -g @anthropic-ai/claude-code
```

Verifica:

```powershell
claude --version
```

> Pe macOS sau Linux: `curl -fsSL https://claude.ai/install.sh | bash`

## 2. Deschide proiectul

Dezarhiveaza folderul `doculens` unde vrei sa stea proiectul, apoi:

```powershell
cd C:\Proiecte\doculens
claude
```

La prima pornire ti se cere sa te autentifici in browser. Claude Code citeste automat `CLAUDE.md` din folder, deci stie regulile proiectului de la prima secunda.

## 3. Porneste git imediat

In sesiunea Claude Code, scrie:

```
Initializeaza git in acest folder, fa primul commit cu tot ce exista acum,
cu mesajul "specificatie completa, 1487 de cerinte", si confirma ca
.gitignore functioneaza.
```

De ce intai: cand ceva se strica peste trei saptamani, ID-ul cerintei din mesajul de commit te duce direct la cauza.

## 4. Verifica specificatia inainte de orice cod

```
Ruleaza python -I tools/verifica_schema.py si
python -I tools/genereaza_matrice_trasabilitate.py.
Spune-mi ce iese si daca ceva nu trece.
```

Primul verifica 28 de reguli de business impuse direct in schema bazei de date. Al doilea reface matricea cerinta-test si pica daca o cerinta a rămas fara test. Daca amandoua trec, ai fundatia buna.

## 5. Prima bucata de cod

Nu cere „construieste produsul". Cere o faza, cu ID-uri. Copiaza asta:

```
Citeste docs/spec/SPEC_04_schema_bd.sql si secțiunea 4 din CLAUDE.md.

Implementeaza faza 0: scheletul de proiect si stratul de baza de date.
Concret:
- app/core/model.py cu tipurile si enumerarile din docs/spec/SPEC_05_api_core.py,
  secțiunile 0, 1 si 3
- app/core/errors.py cu toate excepțiile din secțiunea 2, cu codurile lor
- app/core/db.py care creeaza si deschide app.db si project.db din SPEC_04,
  cu PRAGMA foreign_keys ON si WAL
- app/core/settings.py cu SettingsStore din secțiunea 4
- teste pentru fiecare, in tests/

Pune ID-ul cerintei in comentariul de deasupra fiecarei clase.
Nu atinge app/gui si nu scrie nimic in docs/spec.
La final ruleaza pytest si tools/verifica_schema.py si arata-mi rezultatul.
```

## 6. Ritmul de lucru de aici inainte

O sesiune, o faza. La inceputul fiecarei sesiuni:

```
Citeste CLAUDE.md. Suntem la faza <N>. Arata-mi ce cerinte din faza
asta sunt deja implementate si care lipsesc, dupa ID.
```

La final de sesiune:

```
Fa commit pe ce e terminat, cu ID-urile cerintelor in mesaj.
Spune-mi ce a rămas neterminat si de ce.
```

## 6b. CI e deja scris

In `.github/workflows/ci.yml` ai integrarea continua gata. Ruleaza la fiecare
push si pull request pe `main`, cu trei porti:

1. **schema bazei de date** — `verifica_schema.py`. Functioneaza deja.
2. **matricea cerinta-test** — pica daca o cerinta a ramas fara test, sau daca
   fisierul `SPEC_07` comis nu e la zi fata de specificatie.
3. **lint + teste** — `ruff` si `pytest`. Blande cat timp proiectul e gol,
   stricte dupa faza 0.

Nu trebuie sa faci nimic pentru ele: in clipa in care urci pe GitHub, se aprind
singure. Dupa faza 0, scoate `|| true` de la pasul de lint ca sa devina
obligatoriu — e marcat cu un comentariu in fisier.

## 7. Doua comenzi utile de stiut

- `/init` — daca vrei sa regenerezi `CLAUDE.md` plecand de la cod. **Nu o rula acum**: ar suprascrie fisierul pe care l-ai primit.
- `/clear` — goleste contextul sesiunii. Folosita intre faze, ca sa nu care Claude Code conversatia precedenta.

## 8. Ce sa nu faci in prima luna

- Nu porni cu interfata grafica. Fara nucleu, interfata nu are ce sa arate.
- Nu sari peste teste ca sa mergi mai repede. La 1.487 de cerinte, fara teste nu mai stii ce functioneaza.
- Nu cere mai mult de o faza pe sesiune. Contextul se umple si calitatea scade.
- Nu modifica fisierele din `docs/spec/`. Ele sunt intrarea.

---

## Ce ai in folder

```
doculens/
  CLAUDE.md                        regulile permanente. Claude Code le citeste automat
  SETUP.md                         conditiile preliminare: citeste-l primul
  START.md                         fisierul asta
  .gitignore
  requirements-smoke.txt           test de fum pentru bibliotecile grele
  .github/workflows/ci.yml         integrare continua: schema, matrice, teste
  requirements-dev.txt
  docs/
    MASTER_PROMPT.md               harta de ansamblu: stiva, arhitectura, etape
    prototip_ocr_editor.html       prototip clicabil al OCR Editor-ului
    spec/                          cele 10 fisiere de specificatie
  tools/
    verifica_schema.py             verifica schema bazei de date
    genereaza_matrice_trasabilitate.py
  app/core  app/gui  app/cli       structura, inca goala
  tests/                           teste si corpusul de fisiere de test
```
