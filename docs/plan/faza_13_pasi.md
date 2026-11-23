# Faza 13 — automatizare: sarcini automate si Hot Folder

Cerinte: `S-001`…`S-073` si `S-200`…`S-217` (Hot Folder), `T-001`…`T-021` si
`T-100`…`T-107` (Automated Tasks). 100 de cerinte.

Contractul: SPEC_05 §13 (`TaskStep`, `AutomatedTask`, `AutomatedTaskRunner`,
`HotFolderTask`, `HotFolderService`); tabelele din SPEC_04 (`automated_task`,
`automated_task_step`, `hot_folder_task`, `hot_folder_step`, `processing_log`).

## Pasii

| Pas | Ce | Cerinte |
|---|---|---|
| 13.1 | Nucleul sarcinilor automate (`app/core/automation/tasks.py`): sarcinile livrate, validarea pasilor, salvarea, duplicarea, stergerea, scurtaturile, exportul si importul, rularea pe un lot de fisiere | T-001…T-021 (partea de nucleu) |
| 13.2 | Nucleul Hot Folder (`app/core/automation/hotfolder.py`): sarcinile, validarea, planificarea, verificarea folderului, stabilitatea fisierelor, evidenta celor procesate, reincercarile si `Errors`, originalul, iesirea si numele, jurnalul, contorul de pagini, exportul `.hft` | S-005…S-073 (partea de nucleu) |
| 13.3 | Interfata sarcinilor automate: `Tools > Automated Tasks`, managerul, editorul `Task Settings`, cardul din Lansator, rularea cu progres | T-001…T-021, T-100…T-107 |
| 13.4 | Interfata Hot Folder: fereastra cu lista si toolbarul, dialogul `Task Settings` cu paleta de pasi, bara de stare cu contorul, iconul din bara de sistem, notificarile, `Tools > Hot Folder` (`Ctrl+Shift+F`) | S-001…S-004, S-015…S-020, S-060…S-071, S-200…S-217 |

## Decizii

1. [DECIZIE AUTONOMA] **Fara APScheduler si fara watchdog.** S-032 (`D`) spune
   ca nu exista declansare pe aparitia unui fisier si ca singurele intervale sunt
   la fiecare minut / zi / saptamana / luna. Ora urmatoarei porniri o calculeaza
   nucleul (`next_start`, functie pura); un ceas din interfata (`QTimer`, la
   fiecare 15 secunde) cheama `HotFolderService.tick(now)`. Nicio dependenta noua.
2. [DECIZIE AUTONOMA] **Contradictiile SPEC_05 – SPEC_03 se rezolva dupa SPEC_03
   (`D`):**
   - `install_service` ridica intotdeauna `CoreError`: Hot Folder nu ruleaza ca
     serviciu de sistem (S-005). Semnatura din SPEC_05 ramane.
   - `schedule_kind`: `once` (S-031), `interval` cu exact 1 minut (`Every minute`),
     `daily`, `weekly`, `monthly` (S-032). `on_new_file` (implicitul din SPEC_05)
     e refuzat la validare cu mesaj; interfata nu il ofera.
   - Numerele de cerinte din docstring-urile SPEC_05 (S-015 stabilitatea, S-033
     reincercarile) corespund lui S-073 si S-072 din SPEC_03; codul citeaza SPEC_03.
3. [DECIZIE AUTONOMA] **Locul sarcinilor (S-008, `K`) si evidenta celor procesate
   (S-009, `K`):** sarcinile se tin in `app.db` (tabelele din SPEC_04), nu in
   fisiere `.hft`; `.hft` e formatul de export si import (S-065), JSON cu
   versiune. Rolul fisierului `.ppi` il are `processing_log`: un fisier cu un rand
   `success` (dupa cale, dimensiune si data modificarii) nu se mai proceseaza; un
   fisier inlocuit cu altul (alta dimensiune sau data) se proceseaza din nou.
4. [DECIZIE AUTONOMA] **Limita de 5.000 de pagini pe luna (S-006, `K`) si bara de
   stare (S-202, S-203):** se implementeaza contorul, cu reinnoire la 30 de zile
   de la prima pagina procesata. Limita e setarea `hotfolder.monthly_page_limit`
   (implicit 5.000, ca in original; 0 = fara limita). In original e o limitare de
   licenta; DocuLens nu are licente (Y-012), deci utilizatorul o poate ridica.
5. [DECIZIE AUTONOMA] **Surse care cer retea sau Office:** `File from FTP`
   (S-034) cere parola din magazinul de credentiale al sistemului, care nu e facut
   (faza 10, INCOMPLET); `File from Outlook` (S-035) cere Outlook (CLAUDE.md §6.3);
   `Save to SharePoint` (S-206) e un serviciu online (§6.1). Toate trei apar in
   paleta (structura interfetei), dezactivate, cu explicatie. INCOMPLET.
   Folderele de retea (cale UNC) merg ca `File from folder` (S-033).
6. [DECIZIE AUTONOMA] **S-007 (2 nuclee):** `max_parallel` se pastreaza (implicit 2),
   dar fisierele se proceseaza unul cate unul: proiectele OCR temporare folosesc
   conexiunea `app.db` a firului. INCOMPLET: procesarea in paralel.
7. [DECIZIE AUTONOMA] **Pasii care pornesc alte programe:** `Send document`
   (T-012), `E-mail document` (T-013) si `E-mail images` (T-015) nu deschid nimic
   din nucleu; nucleul intoarce fisierele, iar interfata le da aplicatiei alese,
   respectiv deschide folderul rezultatelor si clientul de e-mail (atasarea
   automata a fisierului nu are un mecanism standard fara Outlook). Scanarea
   (T-007 `Scan`, sarcinile `Scan to …`) o face interfata inainte de rulare, cu
   dialogul de scanare din faza 6d; nucleul primeste fisierele scanate.
8. [DECIZIE AUTONOMA] **Numele sarcinilor livrate** se tin in baza ca chei de
   traducere (`task.builtin.convert_pdf` …), ca sa se afiseze in limba
   interfetei (CLAUDE.md §6.5). Sarcinile utilizatorului au nume libere.
9. [DECIZIE AUTONOMA] **Exportul sarcinilor automate (T-021):** fisier JSON
   `.dltask`, cu `format_version`; o versiune mai noua da `ProjectVersionError`.
10. [DECIZIE AUTONOMA] **`Draw areas manually` (T-106):** rularea primeste un
    callback `wait_for_areas(project)`; fara callback (rulare din Hot Folder sau
    din linia de comanda) pasul se refuza la rulare cu `TaskValidationError`.

11. [DECIZIE AUTONOMA] **Cardul `Automated Tasks` din Lansator (T-019, `V`)** sta in
    coloana din stanga, sub cele cinci sarcini si deasupra lui `Options`: A-003
    (`D`) cere exact cinci sarcini, iar A-301 exact doua sectiuni pe tabul `Open`.
12. [DECIZIE AUTONOMA] **`Draw areas manually` (T-106)** merge numai cu proiectul OCR
    curent: sarcina se opreste cu un mesaj, utilizatorul deseneaza zonele in OCR
    Editor si apasa OK. Cu un proiect nou sau existent pasul se refuza la rulare.
13. [DECIZIE AUTONOMA] **Setarile Hot Folder:** pornirea automata (S-071) si limita
    de pagini (S-006) sunt in `Options > General`, grupul `Hot Folder`;
    jurnalizarea si notificarile sunt comutatoarele din toolbarul ferestrei (S-200).
14. [DECIZIE AUTONOMA] **Sursa `OCR project` (S-036)** se tine ca `source_kind =
    folder` cu calea proiectului: SPEC_04 nu are o valoare proprie; nucleul
    recunoaste proiectul dupa `project.db`. `Save OCR project` are
    `output_format = ocr_project`, fiindca SPEC_04 cere un format la salvare.

## Starea pasilor

- 13.1 gata (commit 719a161), 13.2 gata (commit 6546407), 13.3 si 13.4 gata (acest
  commit). Teste: `test_automated_tasks.py`, `test_hotfolder.py`,
  `test_gui_tasks.py`, `test_gui_hotfolder.py`.

## INCOMPLET

- `File from FTP`, `File from Outlook`, `Save to SharePoint` (decizia 5).
- Procesarea in paralel (`max_parallel`, S-007; decizia 6).
- `Draw areas manually` cu un proiect nou sau existent (decizia 12).
- Notificarea prin e-mail la eroare (`notify_email`): cere un server de e-mail.
- S-001 (componenta in instalarea personalizata) si pornirea Hot Folder din meniul
  Start cu aplicatia inchisa (S-002): faza 16.

## Ce ramane pentru alte faze

- Pornirea Hot Folder din meniul Start si iconul din bara de sistem cand
  aplicatia e inchisa (S-002) cer un proces separat, instalat: faza 16.
- Linia de comanda pentru sarcini: faza 14.
