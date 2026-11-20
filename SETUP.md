# SETUP — conditiile reale, inainte de `claude`

Citeste asta inainte de `START.md`. `START.md` presupune ca tot ce e aici
functioneaza deja. Daca sari peste, te blochezi la jumatate.

Harta e impartita in sase parti. **Verifica fiecare pas inainte sa treci mai
departe** — comanda de verificare e sub fiecare. Daca o verificare nu da ce
scrie aici, rezolvi aia intai; nu mergi mai departe cu un pas stricat.

Totul e pentru **Windows**, in **PowerShell**. Deschide PowerShell ca utilizator
normal, nu ca administrator, decat unde scrie explicit.

---

## Partea 0 — poti face asta? (verifica inainte sa instalezi orice)

Doua conditii care te pot opri din start.

### 0.1 Abonament Claude platit

Claude Code **nu merge pe cont gratuit.** Ai nevoie de Claude Pro sau Max, sau
de facturare activa pe Anthropic API (console.anthropic.com, cu card).

- Pe abonament (Pro/Max) ai limite de utilizare, dar cost fix lunar.
- Pe API platesti la consum. La un proiect de dimensiunea asta, pe luni de
  zile, **costul e real si se aduna.** Nu e o cheltuiala de ignorat.

Daca nu ai niciunul, aici te opresti pana rezolvi partea asta. Nu e un pas
tehnic, e o decizie.

### 0.2 Cont GitHub

Gratuit e suficient. Il faci pe github.com daca nu ai.

---

## Partea 1 — programe de sistem (instaleaza-le intai, verifica fiecare)

Acestea nu sunt biblioteci Python. Sunt programe pe care Windows trebuie sa le
aiba inainte de orice. **Tesseract e cel care te muscă** — citeste 1.4 cu atentie.

### 1.1 Python 3.12

Aceeasi versiune ca in CI, ca sa nu ai surprize. Il iei de pe python.org.
**La instalare, bifeaza „Add Python to PATH".**

Verifica:
```powershell
python --version
```
Trebuie sa scrie `Python 3.12.x`. Daca scrie 3.11 sau 3.13, nu e fatal, dar
ramai pe 3.12 ca sa fii identic cu CI-ul.

### 1.2 Node.js 18 sau mai nou

Doar daca instalezi Claude Code prin npm (partea 2, varianta B). Daca folosesti
installer-ul nativ, sari peste. Il iei de pe nodejs.org, versiunea LTS.

Verifica:
```powershell
node --version
```

### 1.3 Git

Il iei de pe git-scm.com. La instalare lasa valorile implicite.

Verifica:
```powershell
git --version
```

### 1.4 Tesseract OCR — cu limba romana. ACESTA E PASUL GREU.

**Tesseract nu se instaleaza cu pip.** `pytesseract` (vine mai tarziu) e doar un
inveliș subtire care cheama programul Tesseract instalat in sistem. Fara
programul de sistem, OCR-ul nu merge deloc.

Pasi:
1. Descarca installer-ul de Windows de la build-ul UB Mannheim
   (github.com/UB-Mannheim/tesseract/wiki — e build-ul recomandat pentru Windows).
2. La instalare, la „Additional language data", **bifeaza Romanian (`ron`)**.
   Daca ratezi asta, OCR-ul merge dar nu stie romana.
3. **Adauga Tesseract la PATH.** Installer-ul o face de obicei; daca nu,
   adaugi manual folderul (de regula `C:\Program Files\Tesseract-OCR`) in
   variabila PATH si redeschizi PowerShell.

Verifica — ambele comenzi:
```powershell
tesseract --version
tesseract --list-langs
```
Prima trebuie sa afiseze o versiune. A doua trebuie sa conțina `ron` in lista.
Daca `ron` lipseste, reinstaleaza cu limba bifata.

> **Adevar neplacut, spus din timp:** `ron` din Tesseract recunoaste romana, dar
> diacriticele (ș/ț cu virgula fata de ş/ţ cu sedila) sunt o bataie de cap in
> sine. Pragul din specificatie — sub 2 greseli la mie — nu iese „din cutie".
> E munca de reglat si de testat pe documente reale, probabil cea mai grea
> parte a intregului proiect. Nu te astepta sa mearga perfect de la prima
> recunoastere.

### 1.5 GitHub CLI (`gh`) — optional

Daca il ai, Claude Code poate crea repo-ul printr-o comanda. Il iei de pe
cli.github.com. Daca **nu** il ai, nu e o problema: creezi repo-ul pe github.com
in browser, manual, si tot restul merge la fel.

Verifica (daca l-ai instalat):
```powershell
gh --version
gh auth login
```

---

## Partea 2 — instaleaza Claude Code

### Varianta A — installer nativ (recomandat, nu cere Node)
```powershell
irm https://claude.ai/install.ps1 | iex
```

### Varianta B — npm (daca ai deja Node.js 18+)
```powershell
npm install -g @anthropic-ai/claude-code
```

Verifica:
```powershell
claude --version
```
Daca scrie „command not found" dupa varianta B, e o problema de PATH la npm —
redeschide PowerShell; daca persista, foloseste varianta A.

---

## Partea 3 — mediul Python al proiectului

Dezarhiveaza `doculens` unde vrei sa stea proiectul, apoi intra in folder.

```powershell
cd C:\Proiecte\doculens
```

Creeaza un mediu virtual (izoleaza bibliotecile proiectului de restul sistemului):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
Daca PowerShell refuza sa ruleze scriptul de activare, ruleaza o data:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
si incearca din nou activarea.

Dupa activare, prompt-ul incepe cu `(.venv)`. Instaleaza dependentele de
dezvoltare:
```powershell
pip install -r requirements-dev.txt
```

Verifica:
```powershell
pytest --version
ruff --version
```

### 3.1 Testul de fum pentru bibliotecile grele (fa-l acum, nu peste o luna)

Bibliotecile de productie se instaleaza pe faze, dupa tabelul din `CLAUDE.md`.
Dar unele sunt greu de instalat pe Windows, si vrei sa afli ACUM, nu cand esti
la faza 4. Incearca:
```powershell
pip install -r requirements-smoke.txt
```
Daca toate intra fara eroare, esti acoperit pentru fazele 0-6. Daca una pica
(cel mai probabil candidat e ceva legat de compilare), notezi care si o rezolvi
separat — nu lasa pe mai tarziu.

> **PaddleOCR** (pentru detectia de tabele, faza 6) nu e in testul de fum: pe
> Windows aduce `paddlepaddle`, care e mare si capricios. Il lasam pentru cand
> ajungi efectiv la tabele, si il tratam separat atunci.

---

## Partea 4 — verifica fundatia (inainte de orice cod)

```powershell
python -I tools\verifica_schema.py
python -I tools\genereaza_matrice_trasabilitate.py
```
Prima trebuie sa dea `TRECUT 28/28`. A doua reface matricea si spune cate
cerinte si cate teste sunt. Daca amandoua trec, specificatia e solida si poti
construi pe ea.

---

## Partea 5 — de aici preia `START.md`

Pornesti Claude Code in folder:
```powershell
claude
```
La prima pornire te autentifici in browser (cu contul de la partea 0.1).

Mai departe lucrezi prin prompturi, nu prin comenzi. Toate sunt in `START.md`,
gata de copiat: pui proiectul pe GitHub (repo **privat**), apoi faza 0.

---

## Adevarul despre cat dureaza

Ca sa nu ai asteptari gresite:

- **Pornirea Claude Code** (partile 0-5 de mai sus): cateva ore, din care cel
  mai mult ia Tesseract si eventualele probleme de PATH.
- **Un produs OCR folosibil pe dosarele tale** (fazele 0-6): saptamani de
  munca, nu zile. Nu iese din prompturi aruncate — iese din sesiuni disciplinate,
  o faza pe rand, cu teste.
- **Produsul complet** (toate cele 16 faze, 1.487 de cerinte): luni.

Partea buna: fazele 0-6 iti dau deja ce-ti trebuie pentru munca ta reala —
scanare, OCR romanesc, export in Word si PDF cautabil. Restul poate astepta.

Daca vreun pas de aici nu merge, deschizi Claude Code in folder si ii spui exact
ce comanda ai dat si ce eroare ai primit. Are specificatia si CLAUDE.md la
indemana si te poate scoate din impas.
