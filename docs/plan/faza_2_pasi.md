# Faza 2 — impartirea in pasi, inainte de cod

Document de lucru pentru confirmare. Faza 2 din CLAUDE.md §8: preprocesarea,
cele 14 unelte (`L-010`…`L-023`).

Surse citite: SPEC_02 L.1…L.3 (L-001…L-035), SPEC_10 L-100…L-109, SPEC_05
sectiunea 5 (`PreprocessTool`, `PreprocessPipeline`), SPEC_04 `page_operation`,
SPEC_03 X.2 (setarile de preprocesare, deja in `settings.py`).

Regula ramane: un pas = o sesiune = un commit cu CI verde.

**Status:** impartirea si cele 4 propuneri au fost confirmate de utilizator
pe 2026-11-20. Pasul 2a e implementat.

---

## Ce intra in nucleu si ce ramane pentru interfata

Fiecare unealta e o functie pura `apply(imagine, parametri) -> imagine`
(SPEC_02 L, SPEC_05 `PreprocessTool`), apelata din Image Editor, din
preprocesarea automata si din Hot Folder.

Raman pentru faza GUI: L-001, L-002, L-004 si L-100…L-108 (Image Editor:
antet, panoul de unelte, parametrii inline, grila trapezului, histograma).
Nucleul da uneltele, parametrii si validarea lor.

---

## Pasii

### 2a — Infrastructura si uneltele simple

`app/core/images/preprocess.py`: `PreprocessTool`, registrul
(`PreprocessPipeline.register`, `tool_for`), conversia Pillow ↔ ndarray.

Uneltele exacte, fara detectie:

| Unealta | Cerinta | Regula de validat |
|---|---|---|
| Rotire si oglindire | L-015 | fara pierdere de calitate |
| Decupare | L-017 | valorile nu pot depasi imaginea; inci sau milimetri |
| Inversare | L-018 | — |
| Rezolutie | L-019 | intre 72 si 1200 dpi |
| Luminozitate si contrast | L-020 | — |
| Niveluri | L-021 | punctul negru nu poate depasi punctul alb |
| Radiera | L-022 | zona se umple cu fundalul detectat |
| Alb-negru | L-033 | ireversibila |

**Dependenta noua: numpy** — licenta BSD-3.

### 2b — Uneltele cu detectie simpla

| Unealta | Cerinta / setare |
|---|---|
| Indreptarea paginii (deskew), cu unghiul detectat | L-011, X-020 |
| Detectarea si corectarea culorilor inversate | X-028 |
| Eliminarea marcajelor colorate, doar pe fundal alb | L-023, X-030 |
| Albirea fundalului | X-024 |
| Eliminarea zgomotului ISO | X-025 |

**Dependenta noua propusa: OpenCV** (`opencv-python-headless`), licenta
Apache-2.0. Verific la instalare ce biblioteci include pachetul si ce
licente au. Daca apare ceva problematic, alternativa e scikit-image (BSD-3),
mai lenta si cu mai putine unelte gata facute.

### 2c — Uneltele geometrice grele

| Unealta | Cerinta / setare |
|---|---|
| Detectarea marginilor paginii (fotografii) | X-023 |
| Corectarea trapezului: automata si cu cele patru colturi date | L-014, X-027 |
| Impartirea paginilor alaturate (verticala, orizontala, pe o linie) | L-016, X-016 |
| Indreptarea randurilor curbate | L-012, X-021 |
| Eliminarea neclaritatii de miscare | X-026 |

Indreptarea randurilor si neclaritatea de miscare au algoritmi de nivel de
cercetare. Propun o varianta de baza, marcata ca atare. Calitatea reala se
masoara abia cu OCR-ul, in faza 4: SPEC_06 cere ≥ 90% acuratete pe caracter
pentru fotografiile de telefon dupa preprocesare.

### 2d — Pipeline-ul pe paginile proiectului

- `PreprocessPipeline.run`: aplica lantul pe o pagina si scrie imaginea noua
  langa original. Inregistreaza operatiile in `page_operation`. Pagina devine
  `preprocessed`, iar textul unei pagini recunoscute se invalideaza.
- `split` face din o pagina doua (L-016): contorul creste, renumerotare.
- `revert_to_original`.
- `recommended_chain` (L-010) si grupul „Photo Correction” (L-013), dupa
  setarile X.2 si tipul imaginii (L-032).
- Detectia fotografie / scanare din zgomot si fundal (L-035), care completeaza
  ce e acum in `loader.py`.
- Preprocesarea automata la adaugarea paginilor (J-051, L-030, X-011, X-012):
  se aplica doar imaginilor adaugate de acum inainte.
- Selectia de pagini din L-003: impare, pare, curenta, selectate.
- Undo pentru operatiile pe imagine (L-109, J-041): istoricul din 1e se
  extinde cu `page_operation`.

---

## Decizii care cer confirmarea ta

1. **Impartirea de mai sus**, in 4 pasi (2a…2d).
2. **Dependentele:** numpy (BSD-3) in 2a; OpenCV headless (Apache-2.0) in 2b,
   cu verificarea bibliotecilor incluse la instalare.
3. **Formatul imaginii in unelte:** ndarray `uint8`, `(inaltime, latime)`
   pentru gri si alb-negru (0/255), `(inaltime, latime, 3)` pentru culoare,
   cum cere SPEC_05 („image e un ndarray”).
4. **Indreptarea randurilor si neclaritatea de miscare:** o varianta de baza,
   marcata, de imbunatatit dupa ce exista OCR-ul care o poate masura.

## Nepotriviri gasite

ID-urile din SPEC_05 pentru preprocesare sunt din numerotarea veche, ca la
fazele anterioare:

| In SPEC_05 | Scrie | Cerinta reala |
|---|---|---|
| `PreprocessOp.DESKEW` | L-002 | L-011 |
| `PreprocessOp.STRAIGHTEN_LINES` | L-003 | L-012 |
| `PreprocessOp.PHOTO_CORRECTION` | L-004 | L-013 |
| `PreprocessOp.RESOLUTION` | L-010 | L-019 |
| `PreprocessOp.BRIGHTNESS_CONTRAST` | L-011 | L-020 |
| `PreprocessOp.LEVELS` | L-012 | L-021 |
| `PreprocessOp.ERASE` | L-013 | L-022 |
| `PreprocessOp.REMOVE_COLOR_MARKS` | L-014 | L-023 |
| `PreprocessTool.photo_only` | L-018 | L-032 |
| `LoadedImage.is_photo` | L-018 | L-035 |

Comentariile din `app/core/model.py` au copiat ID-urile vechi; le corectez in 2a.
