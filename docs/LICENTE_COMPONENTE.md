# Licentele componentelor DocuLens (Y-021)

DocuLens foloseste numai componente cu licente permisive sau LGPL, legate dinamic.
Componentele AGPL nu se folosesc (PyMuPDF e exclus, CLAUDE.md §5); niciuna dintre
componentele de mai jos nu e legata in proces sub GPL sau AGPL.

## Livrate cu programul

| Componenta | Licenta | Rolul |
|---|---|---|
| Python | PSF-2.0 | limbajul |
| PySide6 / Qt 6 | LGPL-3.0 (legare dinamica) | interfata |
| platformdirs | MIT | folderele aplicatiei |
| Pillow | MIT-CMU (HPND) | imaginile |
| pypdfium2 / PDFium | BSD-3-Clause, Apache-2.0 | randarea PDF |
| pikepdf / qpdf | MPL-2.0 / Apache-2.0 | manipularea PDF |
| numpy | BSD-3-Clause | calcul numeric |
| scipy | BSD-3-Clause | preprocesarea imaginilor |
| scikit-image | BSD-3-Clause | preprocesarea imaginilor |
| pytesseract | Apache-2.0 | legatura cu Tesseract |
| Tesseract OCR si modelele tessdata | Apache-2.0 | recunoasterea (proces separat) |
| zxing-cpp | Apache-2.0 | codurile de bare |
| fonttools | MIT | fonturile incorporate |
| python-docx | MIT | DOCX |
| openpyxl | MIT | XLSX |
| python-pptx | MIT | PPTX |
| XlsxWriter | BSD-2-Clause | dependenta python-pptx |
| lxml | BSD-3-Clause | XML |
| comtypes | MIT | scanarea WIA pe Windows |
| pyHanko, pyhanko-certvalidator | MIT | semnaturile PDF |
| asn1crypto, oscrypto | MIT | semnaturile PDF |
| cryptography | Apache-2.0 / BSD-3-Clause | semnaturile PDF |
| aiohttp si dependentele lui | Apache-2.0 / MIT | dependenta pyHanko; DocuLens nu face cereri de retea (Y-001) |
| tzlocal, tzdata | MIT / Apache-2.0 | ora locala la semnaturi |
| quickjs | MIT | JavaScript in formulare |

## Folosite numai la construire

| Componenta | Licenta | Rolul |
|---|---|---|
| PyInstaller | GPL-2.0 cu exceptie pentru bootloader | impachetarea; programul rezultat nu e sub GPL |
| Inno Setup | licenta Inno Setup (gratuita, si pentru uz comercial) | programul de instalare Windows |
| pytest, pytest-qt, ruff | MIT | testele si verificarile |
