# app/

Structura din CLAUDE.md secțiunea 4. Inca goala — se umple pe faze.

Regula care nu se incalca: **`core` nu importa niciodata din `gui`.**

- `core/` — toata logica. Nu stie ca exista o interfata. Fara dialoguri,
  fara `print`, fara `input`. Progresul prin callback, erorile prin excepții.
- `gui/` — PySide6. Fara reguli de business.
- `cli/` — strat subtire peste `core`. Traduce argumente in apeluri si
  excepții in coduri de ieșire.

Contractul complet, cu semnaturi si excepții: `docs/spec/SPEC_05_api_core.py`.
