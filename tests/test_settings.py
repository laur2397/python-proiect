"""Teste pentru app/core/settings.py (pasul 0b): catalogul X-* si SettingsStore.

Lista cheilor e in docs/plan/faza_0b_setari.md. Testele sunt grupate pe
tab-urile dialogului Options (SPEC_03 capitolul X).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.core import db
from app.core.model import (
    AreaType,
    AutoProcessMode,
    ExportFormat,
    LayoutMode,
    OcrQuality,
    PdfRecognitionMode,
    PrintType,
)
from app.core.settings import (
    CATALOG,
    VALUE_TYPES,
    AppSettingsStore,
    OcrSettings,
    PreprocessSettings,
    SettingsStore,
    definition,
)

ROOT = Path(__file__).resolve().parent.parent
SPEC_07 = ROOT / "docs" / "spec" / "SPEC_07_matrice_trasabilitate.csv"


@pytest.fixture
def con(tmp_path):
    c = db.open_app_db(tmp_path / "app.db")
    yield c
    c.close()


@pytest.fixture
def store(con):
    return AppSettingsStore(con)


# =============================================================================
# Catalogul
# =============================================================================


def test_store_satisfies_contract(store):
    assert isinstance(store, SettingsStore)


def test_keys_are_unique():
    keys = [d.key for d in CATALOG]
    assert len(keys) == len(set(keys))


def test_value_types_match_spec04_check(con):
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name = 'setting'").fetchone()[0]
    for vt in VALUE_TYPES:
        assert f"'{vt}'" in sql
    assert {d.value_type for d in CATALOG} <= set(VALUE_TYPES)


def test_every_default_passes_its_own_validation():
    for d in CATALOG:
        assert d.validate(d.default) == d.default, d.key


def test_every_spec_id_is_a_real_requirement():
    """Trasabilitate: fiecare cheie trimite la o cerinta care exista in SPEC_07."""
    with SPEC_07.open(encoding="utf-8") as f:
        ids = {row["ID cerinta"] for row in csv.DictReader(f, delimiter=";")}
    for d in CATALOG:
        assert d.spec_id in ids, f"{d.key}: {d.spec_id} nu exista in specificatie"


def test_T_Y001_1_no_update_telemetry_or_marketing_keys():
    """T-Y001.1 / X-142..X-144: produsul offline nu are aceste setari."""
    banned = ("update", "telemetry", "analytics", "marketing", "usage_data", "online")
    for d in CATALOG:
        assert not any(b in d.key for b in banned), d.key
        assert d.spec_id not in {"X-142", "X-143", "X-144"}


def test_no_password_is_ever_a_setting():
    """CLAUDE.md §9: parolele nu se salveaza. Doar bifa X-083."""
    for d in CATALOG:
        if "password" in d.key:
            assert d.value_type == "bool", d.key


def test_unknown_key():
    with pytest.raises(ValueError):
        definition("nu.exista")


# =============================================================================
# Stocarea in app.db
# =============================================================================


def test_catalog_is_seeded_in_setting_table(con, store):
    rows = {r[0]: r for r in con.execute(
        "SELECT key, value, value_type, default_value, min_value, max_value,"
        " allowed_values, spec_id FROM setting")}
    assert set(rows) == {d.key for d in CATALOG}
    _, value, vtype, default, mn, mx, _, spec = rows["ocr.confidence_threshold"]
    assert (json.loads(value), vtype, json.loads(default), mn, mx, spec) == (
        70.0, "float", 70.0, 0.0, 100.0, "X-167")
    assert json.loads(rows["ocr.quality"][6]) == ["thorough", "fast"]


def test_values_survive_reopen(tmp_path):
    path = tmp_path / "app.db"
    c = db.open_app_db(path)
    AppSettingsStore(c).set("ocr.quality", "fast")
    c.close()
    c = db.open_app_db(path)
    assert AppSettingsStore(c).get("ocr.quality") == "fast"
    c.close()


def test_reopen_does_not_reset_values_and_refreshes_metadata(con):
    AppSettingsStore(con).set("pdf.use_mrc", True)
    with con:
        con.execute("UPDATE setting SET spec_id = 'vechi' WHERE key = 'pdf.use_mrc'")
    AppSettingsStore(con)
    value, spec = con.execute(
        "SELECT value, spec_id FROM setting WHERE key = 'pdf.use_mrc'").fetchone()
    assert (json.loads(value), spec) == (True, "X-086")


def test_corrupt_stored_value_falls_back_to_default(con):
    AppSettingsStore(con)
    with con:
        con.execute("UPDATE setting SET value = '\"nu-e-mod\"' WHERE key = 'ocr.quality'")
        con.execute("UPDATE setting SET value = 'nu e json' WHERE key = 'image.deskew'")
    store = AppSettingsStore(con)
    assert store.get("ocr.quality") == "thorough"
    assert store.get("image.deskew") is True


def test_rows_with_unknown_keys_are_ignored(con):
    AppSettingsStore(con)
    with con:
        con.execute(
            "INSERT INTO setting (key, value, value_type) VALUES ('vechi.cheie', '1', 'int')")
    store = AppSettingsStore(con)
    assert store.get("vechi.cheie", "implicit") == "implicit"


def test_get_unknown_key_returns_default(store):
    assert store.get("nu.exista") is None
    assert store.get("nu.exista", 5) == 5


def test_set_unknown_key_is_refused(store):
    with pytest.raises(ValueError):
        store.set("nu.exista", 1)


def test_returned_lists_are_copies(store):
    langs = store.get("lang.manual")
    langs.append("deu")
    assert store.get("lang.manual") == ["ron", "eng"]


def test_updated_at_is_touched(con, store):
    with con:
        con.execute("UPDATE setting SET updated_at = '2000-01-01T00:00:00Z'")
    store.set("ocr.quality", "fast")
    (ts,) = con.execute("SELECT updated_at FROM setting WHERE key = 'ocr.quality'").fetchone()
    assert ts != "2000-01-01T00:00:00Z"


# --- validarea, pe tipuri ------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("image.deskew", 1),  # bool: 1 nu e True
        ("image.deskew", "true"),
        ("ocr.max_threads", 0),  # int: sub minim
        ("ocr.max_threads", 2.5),
        ("ocr.max_threads", True),
        ("ocr.confidence_threshold", 100.5),  # float: peste maxim
        ("ocr.confidence_threshold", -1),
        ("ocr.confidence_threshold", float("nan")),
        ("ocr.confidence_threshold", "70"),
        ("ocr.header_repeat_ratio", 0),  # strict peste 0
        ("ocr.quality", "rapid"),  # enum
        ("areas.color.text", "red"),  # color
        ("areas.color.text", "#12345"),
        ("app.temp_folder", ""),  # path
        ("app.temp_folder", 5),
        ("areas.plain_text_font", 12),  # string
        ("ui.language", None),  # nu e nullable
    ],
)
def test_invalid_values_are_refused(store, key, bad):
    before = store.get(key)
    with pytest.raises(ValueError):
        store.set(key, bad)
    assert store.get(key) == before


def test_valid_values_are_normalized(store):
    store.set("ocr.confidence_threshold", 80)
    assert store.get("ocr.confidence_threshold") == 80.0
    store.set("areas.color.text", "#abcdef")
    assert store.get("areas.color.text") == "#ABCDEF"
    store.set("ocr.quality", OcrQuality.FAST)
    assert store.get("ocr.quality") == "fast"
    store.set("app.temp_folder", Path("/tmp/doculens"))
    assert store.get("app.temp_folder") == str(Path("/tmp/doculens"))
    store.set("app.temp_folder", None)
    assert store.get("app.temp_folder") is None


def test_get_typed(store):
    assert store.get_typed("ocr.quality", OcrQuality) is OcrQuality.THOROUGH
    assert store.get_typed("image.deskew", bool) is True
    assert store.get_typed("ocr.confidence_threshold", float) == 70.0
    assert store.get_typed("ocr.max_threads", int) is None
    store.set("app.temp_folder", "/tmp/x")
    assert store.get_typed("app.temp_folder", Path) == Path("/tmp/x")
    with pytest.raises(TypeError):
        store.get_typed("image.deskew", int)
    with pytest.raises(TypeError):
        store.get_typed("ocr.quality", int)
    with pytest.raises(ValueError):
        store.get_typed("nu.exista", str)


# --- X-147 -----------------------------------------------------------------------


def test_T_X147_1_reset_all_resets_every_tab(con, store):
    """T-X147.1: Reset readuce toate tab-urile, nu doar unul."""
    changes = {
        "general.startup_screen": "ocr_last_project",
        "image.deskew": False,
        "lang.manual": ["deu"],
        "ocr.quality": "fast",
        "pdf.create_pdfa": True,
        "docx.layout": "plain",
        "ui.language": "en",
        "areas.color.table": "#000000",
    }
    for k, v in changes.items():
        store.set(k, v)
    store.reset_all()
    for k in changes:
        assert store.get(k) == definition(k).default, k
    # si persistat, nu doar in memorie
    assert AppSettingsStore(con).get("ocr.quality") == "thorough"


# =============================================================================
# Tab 1: General (X-001..X-005)
# =============================================================================


def test_T_X001_1_startup_screen(store):
    assert store.get("general.startup_screen") == "new_task"
    for v in ("ocr_new_project", "ocr_last_project", "new_task"):
        store.set("general.startup_screen", v)


def test_T_X002_1_capture_device_defaults_to_first_available(store):
    assert store.get("general.capture_device") is None


def test_T_X003_1_scan_interface(store):
    assert store.get("general.scan_interface") == "app"
    store.set("general.scan_interface", "driver")


def test_T_X005_1_shell_integration_can_be_disabled(store):
    """X-005 (X): la noi e setare, ca produsul sa poata fi scos din meniul contextual."""
    assert store.get("general.shell_integration") is True
    store.set("general.shell_integration", False)
    assert store.get("general.shell_integration") is False


# =============================================================================
# Tab 2: Image Processing (X-010..X-031, X-413, X-414)
# =============================================================================

IMAGE_DEFAULTS = {
    "image.background_recognition_pdf": True,  # X-010
    "image.auto_process": True,  # X-011
    "image.split_facing_pages": False,  # X-016
    "image.correct_orientation": True,  # X-017
    "image.use_recommended": True,  # X-018
    "image.deskew": True,  # X-020
    "image.straighten_lines": True,  # X-021
    "image.correct_resolution": True,  # X-022
    "image.detect_page_edges": True,  # X-023
    "image.whiten_background": True,  # X-024
    "image.reduce_iso_noise": True,  # X-025
    "image.remove_motion_blur": False,  # X-026
    "image.fix_inverted_colors": True,  # X-028
    "image.convert_to_bw": False,  # X-029
    "image.remove_color_marks": False,  # X-030
}


@pytest.mark.parametrize(("key", "expected"), sorted(IMAGE_DEFAULTS.items()))
def test_image_defaults_match_spec03(store, key, expected):
    assert store.get(key) is expected


def test_T_X012_1_auto_mode_mapping(store):
    assert store.preprocess_settings().auto_mode is AutoProcessMode.READ
    store.set("image.auto_mode", "analyze")
    assert store.preprocess_settings().auto_mode is AutoProcessMode.ANALYZE_AND_READ
    store.set("image.auto_mode", "preprocess")
    assert store.preprocess_settings().auto_mode is AutoProcessMode.PREPROCESS_ONLY


def test_T_X011_1_auto_process_off_means_none(store):
    store.set("image.auto_process", False)
    assert store.preprocess_settings().auto_mode is AutoProcessMode.NONE


def test_preprocess_defaults_equal_contract_defaults(store):
    """Valorile livrate sunt cele din SPEC_05 PreprocessSettings."""
    assert store.preprocess_settings() == PreprocessSettings()


def test_T_X413_1_auto_mode_uses_shipped_values(store):
    store.set("image.deskew", False)  # bifa manuala, ignorata in modul auto
    assert store.preprocess_settings().deskew is True


def test_T_X413_2_manual_mode_uses_saved_values(store):
    store.set("image.preprocess_mode", "manual")
    store.set("image.deskew", False)
    store.set("image.convert_to_bw", True)
    p = store.preprocess_settings()
    assert (p.deskew, p.convert_to_bw) == (False, True)


def test_T_X031_1_no_preprocessing_disables_everything(store):
    store.set("image.preprocess_mode", "none")
    p = store.preprocess_settings()
    assert not any(getattr(p, f) for f in (
        "split_facing_pages", "correct_orientation", "use_recommended", "deskew",
        "straighten_lines", "correct_resolution", "detect_page_edges",
        "whiten_background", "reduce_iso_noise", "remove_motion_blur",
        "fix_inverted_colors", "convert_to_bw", "remove_color_marks"))


def test_T_X414_1_switching_mode_keeps_checkboxes(store):
    """T-X414.1: trecerea pe `No preprocessing` si inapoi nu pierde bifele."""
    store.set("image.preprocess_mode", "manual")
    store.set("image.deskew", False)
    store.set("image.remove_color_marks", True)
    store.set("image.preprocess_mode", "none")
    store.set("image.preprocess_mode", "manual")
    p = store.preprocess_settings()
    assert (p.deskew, p.remove_color_marks) == (False, True)


def test_T_X027_1_trapezoid_is_a_setting(store):
    assert store.get("image.correct_trapezoid") is True
    store.set("image.correct_trapezoid", False)
    assert store.get("image.correct_trapezoid") is False


# =============================================================================
# Tab 3: Languages (X-040..X-042)
# =============================================================================


def test_T_X041_1_default_languages(store):
    assert store.ocr_settings().languages == ("ron", "eng")


def test_T_X040_1_auto_vs_manual_languages(store):
    store.set("lang.auto_candidates", ["ron", "eng", "deu"])
    store.set("lang.manual", ["fra"])
    assert store.ocr_settings().languages == ("ron", "eng", "deu")
    store.set("lang.mode", "manual")
    assert store.ocr_settings().languages == ("fra",)


@pytest.mark.parametrize("bad", [[], ["ron", "ron"], [""], ["ron", 5], "ron"])
def test_T_P001_1_at_least_one_valid_language(store, bad):
    """T-P001.1: minimum o limba; fara duplicate."""
    with pytest.raises(ValueError):
        store.set("lang.manual", bad)


def test_language_tuple_is_accepted(store):
    store.set("lang.manual", ("ron",))
    assert store.get("lang.manual") == ["ron"]


# =============================================================================
# Tab 4: OCR (X-060..X-071, X-416)
# =============================================================================


def test_ocr_defaults_equal_contract_defaults(store):
    """Valorile livrate sunt cele din SPEC_05 OcrSettings."""
    assert store.ocr_settings() == OcrSettings()


def test_T_X060_1_pdf_mode(store):
    for v in PdfRecognitionMode:
        store.set("ocr.pdf_mode", v)
        assert store.ocr_settings().pdf_mode is v


def test_T_X062_X063_quality(store):
    assert store.ocr_settings().quality is OcrQuality.THOROUGH
    store.set("ocr.quality", "fast")
    assert store.ocr_settings().quality is OcrQuality.FAST


def test_T_X064_1_document_type(store):
    store.set("ocr.document_type", "typewriter")
    assert store.ocr_settings().print_type is PrintType.TYPEWRITER


def test_T_X065_1_structural_elements_all_on(store):
    o = store.ocr_settings()
    assert o.detect_headers_footers and o.detect_footnotes
    assert o.detect_table_of_contents and o.detect_numbered_lists


def test_T_X066_X067_off_by_default(store):
    o = store.ocr_settings()
    assert o.convert_barcodes_to_text is False and o.use_training is False


def test_T_X068_1_user_patterns(store):
    store.set("ocr.patterns", "user")
    o = store.ocr_settings()
    assert (o.use_user_patterns, o.use_builtin_patterns, o.also_use_builtin) == (True, False, False)
    store.set("ocr.user_patterns_also_builtin", True)
    assert store.ocr_settings().also_use_builtin is True


def test_T_X416_1_each_also_builtin_checkbox_needs_its_parent(store):
    """T-X416.1: fiecare bifa `Also use built-in patterns` conteaza doar cu parintele ei."""
    store.set("ocr.user_patterns_also_builtin", True)
    store.set("ocr.training_also_builtin", True)
    assert store.ocr_settings().also_use_builtin is False  # niciun parinte activ
    store.set("ocr.use_training", True)
    assert store.ocr_settings().also_use_builtin is True
    store.set("ocr.use_training", False)
    store.set("ocr.patterns", "user")
    assert store.ocr_settings().also_use_builtin is True


def test_T_X071_1_export_fonts(store):
    assert store.get("ocr.export_fonts") is None
    store.set("ocr.export_fonts", ["Liberation Serif", "DejaVu Sans"])
    with pytest.raises(ValueError):
        store.set("ocr.export_fonts", ["", 3])


def test_T_X141_1_threads(store):
    assert store.ocr_settings().max_threads is None
    store.set("ocr.max_threads", 4)
    assert store.ocr_settings().max_threads == 4


def test_T_X167_1_confidence_threshold(store):
    """T-X167.1: pragul implicit 70, interval 0..100."""
    assert store.ocr_settings().confidence_threshold == 70.0
    store.set("ocr.confidence_threshold", 0)
    store.set("ocr.confidence_threshold", 100)
    assert store.ocr_settings().confidence_threshold == 100.0


# =============================================================================
# Tab 5: Format Settings (X-080..X-127)
# =============================================================================


def test_T_X081_1_pdfa_defaults_to_2b(store):
    assert store.get("pdf.create_pdfa") is False
    assert store.get("pdf.pdfa_version") == "2b"
    with pytest.raises(ValueError):
        store.set("pdf.pdfa_version", "4")


def test_T_X084_1_delete_objects_items(store):
    assert store.get("pdf.delete_objects_items") == [
        "comments", "links_media_forms", "bookmarks", "attachments"]
    store.set("pdf.delete_objects_items", ["bookmarks"])
    store.set("pdf.delete_objects_items", [])
    for bad in (["scripts"], ["bookmarks", "bookmarks"]):
        with pytest.raises(ValueError):
            store.set("pdf.delete_objects_items", bad)


@pytest.mark.parametrize(("key", "expected"), [
    ("pdf.create_pdfua", False),  # X-082
    ("pdf.protect_with_password", False),  # X-083
    ("pdf.single_paper_size", False),  # X-085
    ("pdf.use_mrc", False),  # X-086
    ("pdf.preserve_metadata", True),  # X-093
    ("pdf.enable_javascript", False),  # X-145
    ("pdf.detect_urls", True),  # X-146
])
def test_pdf_defaults_match_spec03(store, key, expected):
    assert store.get(key) is expected


@pytest.mark.parametrize(("key", "fmt"), [
    ("docx.layout", ExportFormat.DOCX),
    ("xlsx.layout", ExportFormat.XLSX),
    ("txt.layout", ExportFormat.TXT),
    ("html.layout", ExportFormat.HTML),
    ("epub.layout", ExportFormat.EPUB),
])
def test_T_Q001_2_format_layouts_follow_layout_matrix(store, key, fmt):
    """T-Q001.2: fiecare format accepta exact modurile din matricea Q."""
    allowed = {m.value for m in LayoutMode if fmt in ExportFormat.allowed_for(m)}
    assert set(definition(key).allowed) == allowed
    for m in LayoutMode:
        if m.value in allowed:
            store.set(key, m)
        else:
            with pytest.raises(ValueError):
                store.set(key, m)


def test_T_X100_X124_layout_values_match_spec03():
    """Modurile listate in SPEC_03 pentru fiecare format."""
    assert set(definition("docx.layout").allowed) == {"exact", "editable", "formatted", "plain"}
    assert set(definition("xlsx.layout").allowed) == {"formatted", "plain"}
    assert set(definition("txt.layout").allowed) == {"formatted", "plain"}
    assert set(definition("html.layout").allowed) == {"flexible", "formatted", "plain"}
    assert set(definition("epub.layout").allowed) == {"formatted", "plain"}


def test_T_X127_1_djvu_layers_default_auto(store):
    assert store.get("djvu.multiple_layers") == "auto"


# =============================================================================
# Tab 6: Other (X-140..X-150)
# =============================================================================


def test_T_X140_1_interface_language_ro_en(store):
    """CLAUDE.md §6.5: romana si engleza obligatorii."""
    assert store.get("ui.language") == "ro"
    store.set("ui.language", "en")
    with pytest.raises(ValueError):
        store.set("ui.language", "de")


def test_T_X150_1_temp_folder_defaults_to_system(store):
    assert store.get("app.temp_folder") is None


def test_T_X149_1_dark_theme_off(store):
    assert store.get("ui.dark_theme") is False


# =============================================================================
# Tab 7: Areas and Text (X-160..X-169, M-100)
# =============================================================================


def test_T_M100_1_every_area_type_has_color_and_width(store):
    """T-M100.1 / X-165: cele sase culori si grosimi vin din setari."""
    for t in AreaType:
        assert store.get(f"areas.color.{t.value}").startswith("#")
        assert 1 <= store.get(f"areas.border_width.{t.value}") <= 6
    colors = [store.get(f"areas.color.{t.value}") for t in AreaType]
    assert len(set(colors)) == len(colors), "tipurile se deosebesc prin culoare (M-007)"


def test_T_X165_1_area_colors_are_configurable(store):
    store.set("areas.color.text", "#112233")
    store.set("areas.border_width.text", 4)
    assert store.get("areas.color.text") == "#112233"
    with pytest.raises(ValueError):
        store.set("areas.border_width.text", 7)


def test_T_X166_1_uncertain_color(store):
    assert store.get("areas.uncertain_color") == "#FFB000"


@pytest.mark.parametrize(("key", "expected"), [
    ("areas.check_uncertain", True),  # X-160
    ("areas.show_numbers", True),  # X-168
    ("areas.show_nonprinting", False),  # X-169
])
def test_areas_defaults_match_spec03(store, key, expected):
    assert store.get(key) is expected


# =============================================================================
# J-039: suprascrieri pe proiect
# =============================================================================


def test_T_J039_1_project_overrides_global(store):
    store.set("ocr.quality", "thorough")
    project = store.with_overrides({"ocr.quality": "fast", "lang.manual": ["deu"]})
    assert isinstance(project, SettingsStore)
    assert project.get("ocr.quality") == "fast"
    assert project.get("image.deskew") is True  # din global
    assert project.ocr_settings().quality is OcrQuality.FAST
    assert store.get("ocr.quality") == "thorough"  # globalul neatins


def test_overrides_are_validated(store):
    with pytest.raises(ValueError):
        store.with_overrides({"ocr.quality": "rapid"})
    with pytest.raises(ValueError):
        store.with_overrides({"nu.exista": 1})


def test_override_set_and_reset_do_not_touch_global(con, store):
    project = store.with_overrides({})
    project.set("image.deskew", False)
    assert project.overrides == {"image.deskew": False}
    assert store.get("image.deskew") is True
    project.reset_all()
    assert project.overrides == {}
    assert AppSettingsStore(con).get("image.deskew") is True


def test_overrides_are_json_serializable(store):
    project = store.with_overrides({"lang.manual": ("ron", "deu"), "ocr.max_threads": 2})
    assert json.loads(json.dumps(project.overrides)) == {"lang.manual": ["ron", "deu"],
                                                        "ocr.max_threads": 2}


# =============================================================================
# Y-022: export si import (pasul 0c)
# =============================================================================


def test_T_Y022_1_export_import_round_trip(tmp_path, con, store):
    """T-Y022.1: setarile se exporta intr-un fisier si se importa pe alt profil."""
    store.set("ocr.quality", "fast")
    store.set("lang.manual", ["ron", "deu"])
    store.set("areas.color.text", "#112233")
    out = tmp_path / "export" / "setari.json"
    store.export_to(out)

    other_con = db.open_app_db(tmp_path / "alt" / "app.db")
    other = AppSettingsStore(other_con)
    other.import_from(out)
    assert other.get("ocr.quality") == "fast"
    assert other.get("lang.manual") == ["ron", "deu"]
    assert other.get("areas.color.text") == "#112233"
    assert AppSettingsStore(other_con).get("ocr.quality") == "fast"  # persistat
    other_con.close()


def test_export_file_format(tmp_path, store):
    out = tmp_path / "s.json"
    store.export_to(out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format"] == "doculens-settings"
    assert payload["version"] == 1
    assert payload["exported_at"].endswith("Z")
    assert set(payload["settings"]) == {d.key for d in CATALOG}
    assert not list(tmp_path.glob(".*.tmp"))  # fara resturi de la scrierea atomica


def _write_export(path, settings, **extra):
    payload = {"format": "doculens-settings", "version": 1, "settings": settings, **extra}
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_import_is_all_or_nothing(tmp_path, store):
    f = tmp_path / "s.json"
    _write_export(f, {"ocr.quality": "fast", "image.deskew": "da"})
    with pytest.raises(ValueError, match="image.deskew"):
        store.import_from(f)
    assert store.get("ocr.quality") == "thorough"


def test_import_ignores_unknown_keys_and_keeps_missing_ones(tmp_path, store):
    store.set("pdf.use_mrc", True)
    f = tmp_path / "s.json"
    _write_export(f, {"ocr.quality": "fast", "din.versiune.noua": 1})
    store.import_from(f)
    assert store.get("ocr.quality") == "fast"
    assert store.get("pdf.use_mrc") is True


@pytest.mark.parametrize("content", [
    "nu e json",
    json.dumps([1, 2]),
    json.dumps({"format": "altceva", "version": 1, "settings": {}}),
    json.dumps({"format": "doculens-settings", "version": 2, "settings": {}}),
    json.dumps({"format": "doculens-settings", "version": "1", "settings": {}}),
    json.dumps({"format": "doculens-settings", "version": 1, "settings": [1]}),
])
def test_import_rejects_bad_files(tmp_path, store, content):
    f = tmp_path / "s.json"
    f.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        store.import_from(f)


def test_import_into_project_overrides_only(tmp_path, store):
    f = tmp_path / "s.json"
    _write_export(f, {"ocr.quality": "fast"})
    project = store.with_overrides({})
    project.import_from(f)
    assert project.get("ocr.quality") == "fast"
    assert store.get("ocr.quality") == "thorough"


def test_core_does_not_import_gui():
    """CLAUDE.md §4: core nu importa gui. Niciodata."""
    for path in (ROOT / "app" / "core").rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "from app.gui" not in src and "import app.gui" not in src, path.name
