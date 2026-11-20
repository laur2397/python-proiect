-- =============================================================================
-- SPECIFICATIE 04 - SCHEMA BAZEI DE DATE
-- Alternativa desktop la ABBYY FineReader PDF
-- SQLite 3 (fara server, un fisier pe proiect + un fisier global de setari)
-- =============================================================================
--
-- DOUA BAZE DE DATE SEPARATE:
--   1. app.db      - globala, in profilul utilizatorului. Setari, istoric,
--                    sarcini automatizate, sarcini Hot Folder, limbi, sabloane.
--   2. project.db  - una per proiect OCR, in folderul proiectului, langa
--                    subfolderul images/. Pagini, zone, text, cuvinte.
--
-- De ce separate: un proiect se copiaza, se trimite si se deschide pe alt
-- calculator fara sa duca cu el setarile si istoricul utilizatorului.
--
-- CONVENTII:
--   - toate cheile primare sunt INTEGER PRIMARY KEY (rowid, autoincrement)
--   - timestamp-urile sunt TEXT in format ISO 8601 UTC ('2026-11-19T10:23:00Z')
--   - coordonatele sunt in pixeli de imagine, intregi, origine stanga-sus
--   - valorile de enumerare sunt TEXT cu CHECK, nu INTEGER: jurnalul si
--     fisierul de proiect ramanin citibile cu orice unealta SQLite
--   - PRAGMA foreign_keys = ON trebuie executat la fiecare conexiune
--
-- =============================================================================


-- #############################################################################
-- PARTEA I - app.db  (globala, per utilizator)
-- #############################################################################

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- -----------------------------------------------------------------------------
-- Versiunea schemei. Un singur rand. Migratiile se aplica in ordine.
-- -----------------------------------------------------------------------------
CREATE TABLE schema_version (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    version         INTEGER NOT NULL,
    applied_at      TEXT    NOT NULL
);
INSERT INTO schema_version (id, version, applied_at)
VALUES (1, 1, strftime('%Y-%m-%dT%H:%M:%SZ','now'));


-- -----------------------------------------------------------------------------
-- Setari. Cheie-valoare, cu tip declarat, ca interfata sa stie ce control
-- sa deseneze si ce validare sa aplice. Cheia e ID-ul din SPEC_03 capitolul X
-- (de exemplu 'ocr.quality' corespunde X-041).
-- -----------------------------------------------------------------------------
CREATE TABLE setting (
    key             TEXT    PRIMARY KEY,
    value           TEXT,                      -- serializat ca text; JSON pentru liste
    value_type      TEXT    NOT NULL
                    CHECK (value_type IN ('bool','int','float','string','enum','json','path','color')),
    default_value   TEXT,
    min_value       REAL,                      -- doar pentru int si float
    max_value       REAL,
    allowed_values  TEXT,                      -- JSON array, doar pentru enum
    spec_id         TEXT,                      -- 'X-041', pentru trasabilitate
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TRIGGER setting_touch
AFTER UPDATE OF value ON setting
BEGIN
    UPDATE setting
       SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE key = NEW.key;
END;


-- -----------------------------------------------------------------------------
-- Documente recente (A-052). Maximum 50; triggerul taie surplusul.
-- -----------------------------------------------------------------------------
CREATE TABLE recent_document (
    id              INTEGER PRIMARY KEY,
    path            TEXT    NOT NULL UNIQUE,
    display_name    TEXT    NOT NULL,
    doc_kind        TEXT    NOT NULL
                    CHECK (doc_kind IN ('pdf','ocr_project','image','office','other')),
    page_count      INTEGER CHECK (page_count IS NULL OR page_count > 0),
    opened_at       TEXT    NOT NULL,
    last_page       INTEGER DEFAULT 1 CHECK (last_page >= 1),
    last_zoom       REAL    DEFAULT 1.0 CHECK (last_zoom > 0),
    thumbnail_blob  BLOB
);

CREATE INDEX idx_recent_document_opened ON recent_document (opened_at DESC);

CREATE TRIGGER recent_document_cap
AFTER INSERT ON recent_document
BEGIN
    DELETE FROM recent_document
     WHERE id IN (
        SELECT id FROM recent_document
         ORDER BY opened_at DESC
         LIMIT -1 OFFSET 50
     );
END;


-- -----------------------------------------------------------------------------
-- Comparatii recente (A-051). Maximum 20.
-- -----------------------------------------------------------------------------
CREATE TABLE recent_comparison (
    id              INTEGER PRIMARY KEY,
    path_left       TEXT    NOT NULL,
    path_right      TEXT    NOT NULL,
    language_codes  TEXT    NOT NULL,          -- JSON array: ["ron","eng"]
    difference_count INTEGER CHECK (difference_count IS NULL OR difference_count >= 0),
    compared_at     TEXT    NOT NULL,
    UNIQUE (path_left, path_right)
);

CREATE TRIGGER recent_comparison_cap
AFTER INSERT ON recent_comparison
BEGIN
    DELETE FROM recent_comparison
     WHERE id IN (
        SELECT id FROM recent_comparison
         ORDER BY compared_at DESC
         LIMIT -1 OFFSET 20
     );
END;


-- -----------------------------------------------------------------------------
-- Limbi de recunoastere. Cele livrate au is_builtin = 1 si nu se pot sterge.
-- (P-001 ... P-012)
-- -----------------------------------------------------------------------------
CREATE TABLE ocr_language (
    id              INTEGER PRIMARY KEY,
    code            TEXT    NOT NULL UNIQUE,   -- 'ron', 'eng', 'ron_moldavia'
    display_name    TEXT    NOT NULL,
    script          TEXT    NOT NULL
                    CHECK (script IN ('latin','cyrillic','greek','hebrew','arabic',
                                      'cjk','thai','devanagari','other')),
    is_builtin      INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0,1)),
    base_language_id INTEGER REFERENCES ocr_language(id) ON DELETE SET NULL,
    model_path      TEXT,                      -- calea modelului de recunoastere
    model_available INTEGER NOT NULL DEFAULT 0 CHECK (model_available IN (0,1)),
    has_dictionary  INTEGER NOT NULL DEFAULT 0 CHECK (has_dictionary IN (0,1)),
    -- proprietati avansate (P-009)
    alphabet        TEXT,                      -- caracterele permise
    chars_word_start TEXT,
    chars_word_end  TEXT,
    chars_nonalpha  TEXT,
    chars_ignored   TEXT,
    chars_forbidden TEXT,
    allow_arabic_numerals  INTEGER NOT NULL DEFAULT 1 CHECK (allow_arabic_numerals IN (0,1)),
    allow_roman_numerals   INTEGER NOT NULL DEFAULT 1 CHECK (allow_roman_numerals IN (0,1)),
    allow_abbreviations    INTEGER NOT NULL DEFAULT 1 CHECK (allow_abbreviations IN (0,1)),
    dictionary_mode TEXT    NOT NULL DEFAULT 'builtin'
                    CHECK (dictionary_mode IN ('none','builtin','user','regex')),
    dictionary_regex TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX idx_ocr_language_code ON ocr_language (code);

-- Protejeaza limbile livrate (P-006, T-002 ca principiu general)
CREATE TRIGGER ocr_language_no_delete_builtin
BEFORE DELETE ON ocr_language
WHEN OLD.is_builtin = 1
BEGIN
    SELECT RAISE(ABORT, 'Limbile livrate nu pot fi sterse');
END;


-- -----------------------------------------------------------------------------
-- Grupuri de limbi (P-011). Un grup se foloseste ca o singura limba.
-- -----------------------------------------------------------------------------
CREATE TABLE language_group (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    chars_forbidden TEXT,
    is_builtin      INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0,1))
);

CREATE TABLE language_group_member (
    group_id        INTEGER NOT NULL REFERENCES language_group(id) ON DELETE CASCADE,
    language_id     INTEGER NOT NULL REFERENCES ocr_language(id)   ON DELETE CASCADE,
    PRIMARY KEY (group_id, language_id)
);

-- Un grup are nevoie de minimum 2 limbi (P-011). Verificarea la nivel de
-- aplicatie; aici doar impiedicam golirea completa.
CREATE TRIGGER language_group_not_empty
BEFORE DELETE ON language_group_member
WHEN (SELECT COUNT(*) FROM language_group_member WHERE group_id = OLD.group_id) <= 2
BEGIN
    SELECT RAISE(ABORT, 'Un grup de limbi trebuie sa aiba cel putin doua limbi');
END;


-- -----------------------------------------------------------------------------
-- Dictionare utilizator (P-013 ... P-018)
-- -----------------------------------------------------------------------------
CREATE TABLE user_dictionary_word (
    id              INTEGER PRIMARY KEY,
    language_id     INTEGER NOT NULL REFERENCES ocr_language(id) ON DELETE CASCADE,
    word            TEXT    NOT NULL,
    added_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE (language_id, word),
    CHECK (word <> '' AND word NOT LIKE '% %')   -- P-014: fara spatii
);

CREATE INDEX idx_user_dict_lookup ON user_dictionary_word (language_id, word);


-- -----------------------------------------------------------------------------
-- Sabloane de caractere (P-022 ... P-028). Maximum 1000 de caractere per sablon.
-- -----------------------------------------------------------------------------
CREATE TABLE char_pattern_set (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    language_id     INTEGER REFERENCES ocr_language(id) ON DELETE SET NULL,
    is_active       INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0,1)),
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Un singur sablon activ
CREATE TRIGGER char_pattern_set_single_active
AFTER UPDATE OF is_active ON char_pattern_set
WHEN NEW.is_active = 1
BEGIN
    UPDATE char_pattern_set SET is_active = 0
     WHERE id <> NEW.id AND is_active = 1;
END;

CREATE TABLE char_pattern (
    id              INTEGER PRIMARY KEY,
    pattern_set_id  INTEGER NOT NULL REFERENCES char_pattern_set(id) ON DELETE CASCADE,
    glyph_image     BLOB    NOT NULL,          -- PNG, decuparea din imagine
    character       TEXT    NOT NULL,          -- ce a tastat utilizatorul (poate fi ligatura)
    trained_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX idx_char_pattern_set ON char_pattern (pattern_set_id);

-- P-023: limita de 1000
CREATE TRIGGER char_pattern_limit
BEFORE INSERT ON char_pattern
WHEN (SELECT COUNT(*) FROM char_pattern WHERE pattern_set_id = NEW.pattern_set_id) >= 1000
BEGIN
    SELECT RAISE(ABORT, 'Sablonul a atins limita de 1000 de caractere');
END;


-- -----------------------------------------------------------------------------
-- Sabloane de zone (M-040, M-041)
-- -----------------------------------------------------------------------------
CREATE TABLE area_template (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    source_width    INTEGER NOT NULL CHECK (source_width  > 0),
    source_height   INTEGER NOT NULL CHECK (source_height > 0),
    source_dpi      INTEGER NOT NULL CHECK (source_dpi    > 0),
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE area_template_item (
    id              INTEGER PRIMARY KEY,
    template_id     INTEGER NOT NULL REFERENCES area_template(id) ON DELETE CASCADE,
    area_type       TEXT    NOT NULL
                    CHECK (area_type IN ('recognition','text','table','picture',
                                         'background_picture','barcode')),
    polygon         TEXT    NOT NULL,          -- JSON: [[x,y],[x,y],...]
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    properties      TEXT,                      -- JSON cu proprietatile din M-025..M-030
    UNIQUE (template_id, order_index)
);


-- -----------------------------------------------------------------------------
-- Stiluri de text (O-021 ... O-026). Rolul de titlu genereaza semne de carte.
-- -----------------------------------------------------------------------------
CREATE TABLE text_style (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    font_name       TEXT,
    font_size       REAL    CHECK (font_size IS NULL OR (font_size >= 1 AND font_size <= 1638)),
    horizontal_scale REAL   DEFAULT 100 CHECK (horizontal_scale > 0),
    letter_spacing  REAL    DEFAULT 0,
    is_bold         INTEGER NOT NULL DEFAULT 0 CHECK (is_bold      IN (0,1)),
    is_italic       INTEGER NOT NULL DEFAULT 0 CHECK (is_italic    IN (0,1)),
    is_underline    INTEGER NOT NULL DEFAULT 0 CHECK (is_underline IN (0,1)),
    is_smallcaps    INTEGER NOT NULL DEFAULT 0 CHECK (is_smallcaps IN (0,1)),
    text_color      TEXT,                      -- '#RRGGBB'
    background_color TEXT,
    -- O-023: rolul de titlu, 0 = fara, 1..10 = Heading 1..Heading 10
    heading_level   INTEGER NOT NULL DEFAULT 0
                    CHECK (heading_level BETWEEN 0 AND 10),
    is_builtin      INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0,1))
);


-- -----------------------------------------------------------------------------
-- Stampile (D-035 ... D-038)
-- -----------------------------------------------------------------------------
CREATE TABLE stamp (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    stamp_kind      TEXT    NOT NULL CHECK (stamp_kind IN ('image','text')),
    image_blob      BLOB,                      -- pentru 'image'
    text_content    TEXT,                      -- pentru 'text'
    include_date    INTEGER NOT NULL DEFAULT 0 CHECK (include_date IN (0,1)),
    include_time    INTEGER NOT NULL DEFAULT 0 CHECK (include_time IN (0,1)),
    font_name       TEXT,
    font_size       REAL,
    text_color      TEXT,
    border_style    TEXT    CHECK (border_style IS NULL OR
                                   border_style IN ('none','solid','double','dashed')),
    is_builtin      INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0,1)),
    CHECK ((stamp_kind = 'image' AND image_blob   IS NOT NULL) OR
           (stamp_kind = 'text'  AND text_content IS NOT NULL))
);

CREATE TRIGGER stamp_no_delete_builtin
BEFORE DELETE ON stamp
WHEN OLD.is_builtin = 1
BEGIN
    SELECT RAISE(ABORT, 'Stampilele livrate nu pot fi sterse');
END;


-- -----------------------------------------------------------------------------
-- Semnaturi salvate (G-025 ... G-027)
-- -----------------------------------------------------------------------------
CREATE TABLE saved_signature (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    signature_kind  TEXT    NOT NULL CHECK (signature_kind IN ('text','image','digital')),
    text_content    TEXT,
    image_blob      BLOB,
    transparent_bg  INTEGER NOT NULL DEFAULT 0 CHECK (transparent_bg IN (0,1)),
    certificate_id  TEXT,                      -- amprenta certificatului, nu cheia
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
-- NOTA: niciun material de cheie privata nu se stocheaza in baza de date.
-- Certificatele stau in magazinul de certificate al sistemului sau in fisiere
-- PKCS#12 la care se pastreaza doar calea si amprenta.


-- -----------------------------------------------------------------------------
-- Sabloane de antet si subsol (F-035, F-036)
-- -----------------------------------------------------------------------------
CREATE TABLE header_footer_template (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    position        TEXT    NOT NULL
                    CHECK (position IN ('top_left','top_center','top_right',
                                        'bottom_left','bottom_center','bottom_right')),
    content         TEXT    NOT NULL,          -- cu variabile: {page}, {bates}, {date}
    margin_value    REAL    NOT NULL DEFAULT 1.0 CHECK (margin_value >= 0),
    margin_unit     TEXT    NOT NULL DEFAULT 'cm' CHECK (margin_unit IN ('cm','in','pt')),
    font_name       TEXT,
    font_size       REAL,
    text_color      TEXT,
    bates_start     INTEGER CHECK (bates_start IS NULL OR bates_start >= 0),
    bates_digits    INTEGER CHECK (bates_digits IS NULL OR bates_digits BETWEEN 1 AND 10)
);


-- -----------------------------------------------------------------------------
-- Liste de cuvinte cheie pentru redactare (C-017 ... C-019)
-- -----------------------------------------------------------------------------
CREATE TABLE redaction_keyword_list (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE redaction_keyword (
    id              INTEGER PRIMARY KEY,
    list_id         INTEGER NOT NULL REFERENCES redaction_keyword_list(id) ON DELETE CASCADE,
    keyword         TEXT    NOT NULL,
    match_case      INTEGER NOT NULL DEFAULT 0 CHECK (match_case  IN (0,1)),
    whole_word      INTEGER NOT NULL DEFAULT 0 CHECK (whole_word  IN (0,1)),
    is_regex        INTEGER NOT NULL DEFAULT 0 CHECK (is_regex     IN (0,1)),
    UNIQUE (list_id, keyword)
);


-- -----------------------------------------------------------------------------
-- Sarcini automatizate (T-001 ... T-018)
-- -----------------------------------------------------------------------------
CREATE TABLE automated_task (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    description     TEXT,
    is_builtin      INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0,1)),
    shortcut        TEXT    UNIQUE,            -- 'Ctrl+Alt+1'
    icon_name       TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- T-002: sarcinile livrate nu se modifica si nu se sterg
CREATE TRIGGER automated_task_no_delete_builtin
BEFORE DELETE ON automated_task
WHEN OLD.is_builtin = 1
BEGIN
    SELECT RAISE(ABORT, 'Sarcinile livrate nu pot fi sterse, doar duplicate');
END;

CREATE TRIGGER automated_task_no_update_builtin
BEFORE UPDATE OF name, description ON automated_task
WHEN OLD.is_builtin = 1
BEGIN
    SELECT RAISE(ABORT, 'Sarcinile livrate nu pot fi modificate, doar duplicate');
END;

CREATE TABLE automated_task_step (
    id              INTEGER PRIMARY KEY,
    task_id         INTEGER NOT NULL REFERENCES automated_task(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    step_type       TEXT    NOT NULL
                    CHECK (step_type IN ('get_images','preprocess','analyze',
                                         'recognize','save','send_to')),
    parameters      TEXT    NOT NULL DEFAULT '{}',   -- JSON
    UNIQUE (task_id, order_index)
);

CREATE INDEX idx_task_step_task ON automated_task_step (task_id, order_index);

-- T-006: primul pas trebuie sa fie get_images
CREATE TRIGGER automated_task_first_step
BEFORE INSERT ON automated_task_step
WHEN NEW.order_index = 0 AND NEW.step_type <> 'get_images'
BEGIN
    SELECT RAISE(ABORT, 'Primul pas al unei sarcini trebuie sa fie obtinerea imaginilor');
END;


-- -----------------------------------------------------------------------------
-- Hot Folder (S-001 ... S-034)
-- -----------------------------------------------------------------------------
CREATE TABLE hot_folder_task (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    is_enabled      INTEGER NOT NULL DEFAULT 0 CHECK (is_enabled IN (0,1)),
    -- sursa
    source_kind     TEXT    NOT NULL
                    CHECK (source_kind IN ('folder','ftp','outlook','network')),
    source_path     TEXT    NOT NULL,
    include_subfolders INTEGER NOT NULL DEFAULT 0 CHECK (include_subfolders IN (0,1)),
    file_pattern    TEXT    NOT NULL DEFAULT '*',
    -- FTP / retea: parola NU se stocheaza aici, doar referinta spre magazinul
    -- de credentiale al sistemului
    credential_ref  TEXT,
    ftp_host        TEXT,
    ftp_port        INTEGER CHECK (ftp_port IS NULL OR ftp_port BETWEEN 1 AND 65535),
    ftp_passive     INTEGER NOT NULL DEFAULT 1 CHECK (ftp_passive IN (0,1)),
    -- ce se face cu originalul (S-010)
    original_action TEXT    NOT NULL DEFAULT 'keep'
                    CHECK (original_action IN ('keep','move','delete')),
    original_move_to TEXT,
    -- planificare (S-012 ... S-015)
    schedule_kind   TEXT    NOT NULL
                    CHECK (schedule_kind IN ('once','interval','daily','weekly',
                                             'monthly','on_new_file')),
    schedule_at     TEXT,                      -- ISO pentru 'once'
    schedule_interval_minutes INTEGER CHECK (schedule_interval_minutes IS NULL OR
                                             schedule_interval_minutes >= 1),
    schedule_time   TEXT,                      -- 'HH:MM' pentru daily/weekly/monthly
    schedule_days   TEXT,                      -- JSON array de zile
    -- stare
    status          TEXT    NOT NULL DEFAULT 'stopped'
                    CHECK (status IN ('stopped','running','error','completed')),
    last_run_at     TEXT,
    next_run_at     TEXT,
    last_error      TEXT,
    max_parallel    INTEGER NOT NULL DEFAULT 2 CHECK (max_parallel BETWEEN 1 AND 32),
    notify_on_error INTEGER NOT NULL DEFAULT 0 CHECK (notify_on_error IN (0,1)),
    notify_email    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    CHECK (original_action <> 'move' OR original_move_to IS NOT NULL),
    CHECK (schedule_kind <> 'once'     OR schedule_at IS NOT NULL),
    CHECK (schedule_kind <> 'interval' OR schedule_interval_minutes IS NOT NULL)
);

CREATE INDEX idx_hot_folder_next_run ON hot_folder_task (is_enabled, next_run_at);

CREATE TABLE hot_folder_step (
    id              INTEGER PRIMARY KEY,
    hot_folder_id   INTEGER NOT NULL REFERENCES hot_folder_task(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    step_type       TEXT    NOT NULL
                    CHECK (step_type IN ('preprocess','analyze','recognize','save')),
    parameters      TEXT    NOT NULL DEFAULT '{}',
    -- pentru pasii de salvare (S-020 ... S-023)
    output_format   TEXT,
    output_folder   TEXT,
    name_template   TEXT    DEFAULT '{name}',
    on_name_clash   TEXT    DEFAULT 'number'
                    CHECK (on_name_clash IN ('overwrite','number','skip')),
    UNIQUE (hot_folder_id, order_index),
    CHECK (step_type <> 'save' OR (output_format IS NOT NULL AND output_folder IS NOT NULL))
);


-- -----------------------------------------------------------------------------
-- Jurnalul de procesare. Serveste si la Hot Folder, si la CLI, si la sarcini.
-- (S-030, U-024)
-- -----------------------------------------------------------------------------
CREATE TABLE processing_log (
    id              INTEGER PRIMARY KEY,
    hot_folder_id   INTEGER REFERENCES hot_folder_task(id) ON DELETE CASCADE,
    automated_task_id INTEGER REFERENCES automated_task(id) ON DELETE SET NULL,
    source_file     TEXT    NOT NULL,
    output_file     TEXT,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    status          TEXT    NOT NULL
                    CHECK (status IN ('pending','running','success','error','skipped','cancelled')),
    page_count      INTEGER CHECK (page_count IS NULL OR page_count >= 0),
    duration_ms     INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    error_code      TEXT,
    error_message   TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0)
);

CREATE INDEX idx_processing_log_task ON processing_log (hot_folder_id, started_at DESC);
CREATE INDEX idx_processing_log_status ON processing_log (status, started_at DESC);
CREATE INDEX idx_processing_log_source ON processing_log (source_file);

-- S-033: un fisier eșuat nu se reprocesează la infinit
-- Regula de aplicatie: retry_count >= 3 duce fisierul in subfolderul Errors.
-- Aici doar impiedicam depasirea.
CREATE TRIGGER processing_log_retry_cap
BEFORE UPDATE OF retry_count ON processing_log
WHEN NEW.retry_count > 3
BEGIN
    SELECT RAISE(ABORT, 'Numarul maxim de reincercari a fost depasit');
END;


-- -----------------------------------------------------------------------------
-- Scurtaturi de tastatura reatribuibile (X-085, X-086)
-- -----------------------------------------------------------------------------
CREATE TABLE keyboard_shortcut (
    id              INTEGER PRIMARY KEY,
    command_id      TEXT    NOT NULL UNIQUE,   -- 'pdf.save_as', 'ocr.recognize_all'
    display_name    TEXT    NOT NULL,
    category        TEXT    NOT NULL,
    shortcut        TEXT,                      -- NULL = nealocata
    default_shortcut TEXT,
    UNIQUE (shortcut)                          -- X-085: fara conflicte
);

CREATE INDEX idx_shortcut_category ON keyboard_shortcut (category, display_name);


-- -----------------------------------------------------------------------------
-- Fisiere de recuperare (I-015, J-005, J-006, Y-008)
-- -----------------------------------------------------------------------------
CREATE TABLE recovery_entry (
    id              INTEGER PRIMARY KEY,
    original_path   TEXT,                      -- NULL pentru documente nesalvate
    recovery_path   TEXT    NOT NULL UNIQUE,
    doc_kind        TEXT    NOT NULL CHECK (doc_kind IN ('pdf','ocr_project')),
    session_id      TEXT    NOT NULL,
    saved_at        TEXT    NOT NULL,
    is_clean_exit   INTEGER NOT NULL DEFAULT 0 CHECK (is_clean_exit IN (0,1))
);

CREATE INDEX idx_recovery_session ON recovery_entry (session_id, saved_at DESC);



-- #############################################################################
-- PARTEA II - project.db  (una per proiect OCR)
-- #############################################################################
-- Se creeaza in folderul proiectului. Imaginile stau pe disc, in
-- <proiect>/images/, nu in baza de date: un proiect de 500 de pagini la 300 dpi
-- depaseste cu usurinta limitele practice ale SQLite pentru BLOB-uri mari.
-- In baza de date se pastreaza doar calea relativa si o miniatura.
-- #############################################################################

-- -----------------------------------------------------------------------------
-- Antetul proiectului. Un singur rand.
-- -----------------------------------------------------------------------------
CREATE TABLE project (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    name            TEXT    NOT NULL,
    schema_version  INTEGER NOT NULL,
    app_version     TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    -- limbile proiectului (P-001)
    language_codes  TEXT    NOT NULL DEFAULT '["ron","eng"]',   -- JSON array
    -- setari care suprascriu globalele pentru acest proiect (J-021)
    settings_override TEXT  NOT NULL DEFAULT '{}',              -- JSON
    -- metadate pentru export (J-020)
    meta_title      TEXT,
    meta_author     TEXT,
    meta_subject    TEXT,
    meta_keywords   TEXT,
    -- modul de layout curent (Q-001)
    layout_mode     TEXT    NOT NULL DEFAULT 'editable'
                    CHECK (layout_mode IN ('exact','editable','formatted','plain','flexible')),
    keep_pictures   INTEGER NOT NULL DEFAULT 1 CHECK (keep_pictures IN (0,1)),
    keep_headers_footers INTEGER NOT NULL DEFAULT 0 CHECK (keep_headers_footers IN (0,1)),
    keep_line_breaks INTEGER NOT NULL DEFAULT 0 CHECK (keep_line_breaks IN (0,1))
);


-- -----------------------------------------------------------------------------
-- Pagini
-- -----------------------------------------------------------------------------
CREATE TABLE page (
    id              INTEGER PRIMARY KEY,
    page_number     INTEGER NOT NULL UNIQUE CHECK (page_number >= 1),
    -- fisierele de pe disc, cai relative la folderul proiectului
    image_path      TEXT    NOT NULL,          -- imaginea curenta, dupa preprocesare
    original_path   TEXT    NOT NULL,          -- imaginea nemodificata, pentru revenire
    thumbnail_blob  BLOB,
    width_px        INTEGER NOT NULL CHECK (width_px  > 0),
    height_px       INTEGER NOT NULL CHECK (height_px > 0),
    dpi_x           INTEGER NOT NULL CHECK (dpi_x > 0),
    dpi_y           INTEGER NOT NULL CHECK (dpi_y > 0),
    color_mode      TEXT    NOT NULL
                    CHECK (color_mode IN ('bw','gray','color')),
    rotation        INTEGER NOT NULL DEFAULT 0
                    CHECK (rotation IN (0,90,180,270)),
    -- provenienta
    source_file     TEXT,
    source_page     INTEGER CHECK (source_page IS NULL OR source_page >= 1),
    source_kind     TEXT    NOT NULL DEFAULT 'file'
                    CHECK (source_kind IN ('file','scanner','camera','pdf','clipboard')),
    -- starea in pipeline. N-024: o modificare duce statusul inapoi la 'analyzed'
    status          TEXT    NOT NULL DEFAULT 'imported'
                    CHECK (status IN ('imported','preprocessed','analyzed',
                                      'recognized','verified','error')),
    -- metrici de calitate, folosite pentru avertismente (N-007)
    skew_angle      REAL,
    estimated_dpi   INTEGER,
    blank_score     REAL    CHECK (blank_score IS NULL OR
                                   (blank_score >= 0 AND blank_score <= 1)),
    -- rezultate
    recognized_at   TEXT,
    recognition_ms  INTEGER CHECK (recognition_ms IS NULL OR recognition_ms >= 0),
    avg_confidence  REAL    CHECK (avg_confidence IS NULL OR
                                   (avg_confidence >= 0 AND avg_confidence <= 100)),
    uncertain_count INTEGER NOT NULL DEFAULT 0 CHECK (uncertain_count >= 0),
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX idx_page_number ON page (page_number);
CREATE INDEX idx_page_status ON page (status);

-- J-012: proiectul nu poate rămâne fara pagini
CREATE TRIGGER page_not_last
BEFORE DELETE ON page
WHEN (SELECT COUNT(*) FROM page) <= 1
BEGIN
    SELECT RAISE(ABORT, 'Proiectul trebuie sa aiba cel putin o pagina');
END;


-- -----------------------------------------------------------------------------
-- Operatii de preprocesare aplicate, in ordine. Permite revenirea la original
-- si reaplicarea lantului (L-001 ... L-014, J-023).
-- -----------------------------------------------------------------------------
CREATE TABLE page_operation (
    id              INTEGER PRIMARY KEY,
    page_id         INTEGER NOT NULL REFERENCES page(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    operation       TEXT    NOT NULL
                    CHECK (operation IN ('deskew','straighten_lines','photo_correction',
                                         'trapezoid','rotate','flip','split','crop',
                                         'invert','resolution','brightness_contrast',
                                         'levels','erase','remove_color_marks',
                                         'denoise','deblur','whiten_background',
                                         'detect_edges','to_bw')),
    parameters      TEXT    NOT NULL DEFAULT '{}',   -- JSON
    applied_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE (page_id, order_index)
);

CREATE INDEX idx_page_operation_page ON page_operation (page_id, order_index);


-- -----------------------------------------------------------------------------
-- Zone (M-001 ... M-042)
-- -----------------------------------------------------------------------------
CREATE TABLE area (
    id              INTEGER PRIMARY KEY,
    page_id         INTEGER NOT NULL REFERENCES page(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    area_type       TEXT    NOT NULL
                    CHECK (area_type IN ('recognition','text','table','picture',
                                         'background_picture','barcode')),
    -- dreptunghiul incadrator, pentru interogari rapide
    bbox_x          INTEGER NOT NULL CHECK (bbox_x >= 0),
    bbox_y          INTEGER NOT NULL CHECK (bbox_y >= 0),
    bbox_w          INTEGER NOT NULL CHECK (bbox_w >= 8),   -- M-007: minimum 8 px
    bbox_h          INTEGER NOT NULL CHECK (bbox_h >= 8),
    -- conturul real; o zona poate fi poligon dupa add/cut part (M-013, M-014)
    polygon         TEXT    NOT NULL,          -- JSON: [[x,y],...]
    is_polygon      INTEGER NOT NULL DEFAULT 0 CHECK (is_polygon IN (0,1)),
    -- proprietati (M-025 ... M-030)
    language_codes  TEXT,                      -- JSON; NULL = limbile proiectului
    text_function   TEXT    CHECK (text_function IS NULL OR
                                   text_function IN ('body','header','footer',
                                                     'footnote','caption')),
    orientation     TEXT    NOT NULL DEFAULT 'auto'
                    CHECK (orientation IN ('auto','0','90','180','270')),
    print_type      TEXT    NOT NULL DEFAULT 'auto'
                    CHECK (print_type IN ('auto','typewriter','fax')),
    is_inverted     INTEGER NOT NULL DEFAULT 0 CHECK (is_inverted IN (0,1)),
    cjk_direction   TEXT    CHECK (cjk_direction IS NULL OR
                                   cjk_direction IN ('horizontal','vertical')),
    -- doar pentru barcode
    barcode_type    TEXT,
    barcode_value   TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE (page_id, order_index),
    -- M-026: functia de text doar pentru zone de tip text
    CHECK (text_function IS NULL OR area_type = 'text')
);

CREATE INDEX idx_area_page ON area (page_id, order_index);
CREATE INDEX idx_area_type ON area (page_id, area_type);
CREATE INDEX idx_area_bbox ON area (page_id, bbox_y, bbox_x);

-- N-024: schimbarea unei zone invalideaza textul paginii
CREATE TRIGGER area_invalidates_page_on_update
AFTER UPDATE OF polygon, bbox_x, bbox_y, bbox_w, bbox_h, area_type,
                language_codes, orientation, print_type, is_inverted ON area
BEGIN
    UPDATE page
       SET status = CASE WHEN status IN ('recognized','verified')
                         THEN 'analyzed' ELSE status END,
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = NEW.page_id;
END;

CREATE TRIGGER area_invalidates_page_on_insert
AFTER INSERT ON area
BEGIN
    UPDATE page
       SET status = CASE WHEN status IN ('recognized','verified')
                         THEN 'analyzed' ELSE status END,
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = NEW.page_id;
END;

CREATE TRIGGER area_invalidates_page_on_delete
AFTER DELETE ON area
BEGIN
    UPDATE page
       SET status = CASE WHEN status IN ('recognized','verified')
                         THEN 'analyzed' ELSE status END,
           updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = OLD.page_id;
END;


-- -----------------------------------------------------------------------------
-- Structura de tabel (M-031 ... M-039)
-- -----------------------------------------------------------------------------
CREATE TABLE table_cell (
    id              INTEGER PRIMARY KEY,
    area_id         INTEGER NOT NULL REFERENCES area(id) ON DELETE CASCADE,
    row_index       INTEGER NOT NULL CHECK (row_index >= 0),
    col_index       INTEGER NOT NULL CHECK (col_index >= 0),
    row_span        INTEGER NOT NULL DEFAULT 1 CHECK (row_span >= 1),
    col_span        INTEGER NOT NULL DEFAULT 1 CHECK (col_span >= 1),
    bbox_x          INTEGER NOT NULL,
    bbox_y          INTEGER NOT NULL,
    bbox_w          INTEGER NOT NULL CHECK (bbox_w > 0),
    bbox_h          INTEGER NOT NULL CHECK (bbox_h > 0),
    -- M-038: o celula poate fi tratata ca imagine
    as_picture      INTEGER NOT NULL DEFAULT 0 CHECK (as_picture IN (0,1)),
    is_header       INTEGER NOT NULL DEFAULT 0 CHECK (is_header  IN (0,1)),
    UNIQUE (area_id, row_index, col_index)
);

CREATE INDEX idx_table_cell_area ON table_cell (area_id, row_index, col_index);

CREATE TABLE table_separator (
    id              INTEGER PRIMARY KEY,
    area_id         INTEGER NOT NULL REFERENCES area(id) ON DELETE CASCADE,
    axis            TEXT    NOT NULL CHECK (axis IN ('horizontal','vertical')),
    position_px     INTEGER NOT NULL CHECK (position_px >= 0),
    is_manual       INTEGER NOT NULL DEFAULT 0 CHECK (is_manual IN (0,1)),
    UNIQUE (area_id, axis, position_px)
);


-- -----------------------------------------------------------------------------
-- Textul recunoscut, pe trei niveluri: paragraf, rand, cuvant.
-- Caracterele individuale NU se stocheaza ca randuri: la 500 de pagini ar fi
-- milioane de randuri. Increderea per caracter se pastreaza ca sir compact
-- pe cuvant.
-- -----------------------------------------------------------------------------
CREATE TABLE text_block (
    id              INTEGER PRIMARY KEY,
    area_id         INTEGER NOT NULL REFERENCES area(id) ON DELETE CASCADE,
    table_cell_id   INTEGER REFERENCES table_cell(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    block_type      TEXT    NOT NULL DEFAULT 'paragraph'
                    CHECK (block_type IN ('paragraph','list_item','heading',
                                          'caption','footnote','header','footer')),
    style_name      TEXT,                      -- referinta la text_style.name din app.db
    list_level      INTEGER CHECK (list_level IS NULL OR list_level BETWEEN 1 AND 10),
    alignment       TEXT    CHECK (alignment IS NULL OR
                                   alignment IN ('left','center','right','justify')),
    direction       TEXT    NOT NULL DEFAULT 'ltr' CHECK (direction IN ('ltr','rtl')),
    bbox_x          INTEGER NOT NULL,
    bbox_y          INTEGER NOT NULL,
    bbox_w          INTEGER NOT NULL,
    bbox_h          INTEGER NOT NULL,
    UNIQUE (area_id, order_index)
);

CREATE INDEX idx_text_block_area ON text_block (area_id, order_index);
CREATE INDEX idx_text_block_cell ON text_block (table_cell_id);

CREATE TABLE text_line (
    id              INTEGER PRIMARY KEY,
    block_id        INTEGER NOT NULL REFERENCES text_block(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    baseline_y      INTEGER,
    bbox_x          INTEGER NOT NULL,
    bbox_y          INTEGER NOT NULL,
    bbox_w          INTEGER NOT NULL,
    bbox_h          INTEGER NOT NULL,
    -- randul intrerupt la capat prin cratima (R-024 si exportul)
    ends_with_hyphen INTEGER NOT NULL DEFAULT 0 CHECK (ends_with_hyphen IN (0,1)),
    UNIQUE (block_id, order_index)
);

CREATE INDEX idx_text_line_block ON text_line (block_id, order_index);

CREATE TABLE word (
    id              INTEGER PRIMARY KEY,
    line_id         INTEGER NOT NULL REFERENCES text_line(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    text            TEXT    NOT NULL,
    -- increderea pe cuvant si pe caracter (N-022, N-023)
    confidence      REAL    NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    char_confidences TEXT,                     -- sir compact: "98,97,42,99"
    is_uncertain    INTEGER NOT NULL DEFAULT 0 CHECK (is_uncertain IN (0,1)),
    in_dictionary   INTEGER NOT NULL DEFAULT 0 CHECK (in_dictionary IN (0,1)),
    -- editarea manuala (O-006): se pastreaza originalul
    original_text   TEXT,
    is_edited       INTEGER NOT NULL DEFAULT 0 CHECK (is_edited IN (0,1)),
    is_verified     INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0,1)),
    -- redactarea (O-030)
    is_redacted     INTEGER NOT NULL DEFAULT 0 CHECK (is_redacted IN (0,1)),
    -- formatare locala, cand difera de stilul blocului
    font_name       TEXT,
    font_size       REAL,
    is_bold         INTEGER CHECK (is_bold      IS NULL OR is_bold      IN (0,1)),
    is_italic       INTEGER CHECK (is_italic    IS NULL OR is_italic    IN (0,1)),
    is_underline    INTEGER CHECK (is_underline IS NULL OR is_underline IN (0,1)),
    is_superscript  INTEGER CHECK (is_superscript IS NULL OR is_superscript IN (0,1)),
    is_subscript    INTEGER CHECK (is_subscript   IS NULL OR is_subscript   IN (0,1)),
    text_color      TEXT,
    language_code   TEXT,
    bbox_x          INTEGER NOT NULL,
    bbox_y          INTEGER NOT NULL,
    bbox_w          INTEGER NOT NULL,
    bbox_h          INTEGER NOT NULL,
    UNIQUE (line_id, order_index)
);

CREATE INDEX idx_word_line ON word (line_id, order_index);
CREATE INDEX idx_word_uncertain ON word (is_uncertain) WHERE is_uncertain = 1;
CREATE INDEX idx_word_text ON word (text);

-- O-006 si O-018: editarea unui cuvant il scoate din starea verificata
CREATE TRIGGER word_edit_marks_dirty
AFTER UPDATE OF text ON word
WHEN NEW.text <> OLD.text
BEGIN
    UPDATE word
       SET is_edited     = 1,
           original_text = COALESCE(OLD.original_text, OLD.text),
           is_verified   = 0
     WHERE id = NEW.id;
END;


-- -----------------------------------------------------------------------------
-- Cautare full-text in textul recunoscut. Tabel extern, sincronizat prin
-- triggere, ca sa nu dublam textul.
-- -----------------------------------------------------------------------------
CREATE VIRTUAL TABLE word_fts USING fts5 (
    text,
    content = 'word',
    content_rowid = 'id',
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER word_fts_insert AFTER INSERT ON word BEGIN
    INSERT INTO word_fts (rowid, text) VALUES (NEW.id, NEW.text);
END;

CREATE TRIGGER word_fts_delete AFTER DELETE ON word BEGIN
    INSERT INTO word_fts (word_fts, rowid, text) VALUES ('delete', OLD.id, OLD.text);
END;

CREATE TRIGGER word_fts_update AFTER UPDATE OF text ON word BEGIN
    INSERT INTO word_fts (word_fts, rowid, text) VALUES ('delete', OLD.id, OLD.text);
    INSERT INTO word_fts (rowid, text) VALUES (NEW.id, NEW.text);
END;


-- -----------------------------------------------------------------------------
-- Avertismente per pagina (N-007, O-031)
-- -----------------------------------------------------------------------------
CREATE TABLE page_warning (
    id              INTEGER PRIMARY KEY,
    page_id         INTEGER NOT NULL REFERENCES page(id) ON DELETE CASCADE,
    severity        TEXT    NOT NULL CHECK (severity IN ('info','warning','error')),
    code            TEXT    NOT NULL,          -- 'LOW_RESOLUTION', 'NO_TEXT_FOUND'
    message         TEXT    NOT NULL,
    is_dismissed    INTEGER NOT NULL DEFAULT 0 CHECK (is_dismissed IN (0,1)),
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX idx_page_warning_page ON page_warning (page_id, severity);


-- -----------------------------------------------------------------------------
-- Adnotari PDF. Proiectul OCR le poarta cand documentul vine din PDF Editor
-- si se intoarce acolo (I-012, I-013).
-- -----------------------------------------------------------------------------
CREATE TABLE annotation (
    id              INTEGER PRIMARY KEY,
    page_id         INTEGER NOT NULL REFERENCES page(id) ON DELETE CASCADE,
    parent_id       INTEGER REFERENCES annotation(id) ON DELETE CASCADE,  -- D-018
    annot_type      TEXT    NOT NULL
                    CHECK (annot_type IN ('note','highlight','underline','strikethrough',
                                          'insert_text','ink','line','arrow','rectangle',
                                          'oval','polygon','cloud','polyline','text_box',
                                          'stamp','redaction','link','signature')),
    author          TEXT,
    subject         TEXT,
    content         TEXT,
    color           TEXT,
    fill_color      TEXT,
    opacity         REAL    NOT NULL DEFAULT 1.0 CHECK (opacity >= 0 AND opacity <= 1),
    line_width      REAL    CHECK (line_width IS NULL OR
                                   (line_width >= 0.5 AND line_width <= 12)),  -- D-016
    -- D-031
    review_status   TEXT    CHECK (review_status IS NULL OR
                                   review_status IN ('accepted','rejected',
                                                     'cancelled','completed')),
    is_checked      INTEGER NOT NULL DEFAULT 0 CHECK (is_checked IN (0,1)),  -- D-030
    geometry        TEXT    NOT NULL,          -- JSON: puncte, quadpoints sau rect
    bbox_x          INTEGER NOT NULL,
    bbox_y          INTEGER NOT NULL,
    bbox_w          INTEGER NOT NULL,
    bbox_h          INTEGER NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    modified_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX idx_annotation_page ON annotation (page_id, annot_type);
CREATE INDEX idx_annotation_parent ON annotation (parent_id);
CREATE INDEX idx_annotation_author ON annotation (author);

-- D-031: istoricul schimbarilor de status, cu autor si data
CREATE TABLE annotation_status_history (
    id              INTEGER PRIMARY KEY,
    annotation_id   INTEGER NOT NULL REFERENCES annotation(id) ON DELETE CASCADE,
    old_status      TEXT,
    new_status      TEXT,
    author          TEXT,
    changed_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TRIGGER annotation_status_log
AFTER UPDATE OF review_status ON annotation
WHEN IFNULL(NEW.review_status,'') <> IFNULL(OLD.review_status,'')
BEGIN
    INSERT INTO annotation_status_history (annotation_id, old_status, new_status, author)
    VALUES (NEW.id, OLD.review_status, NEW.review_status, NEW.author);
END;


-- -----------------------------------------------------------------------------
-- Semne de carte (F-042 ... F-046). Arbore, maximum 10 niveluri.
-- -----------------------------------------------------------------------------
CREATE TABLE bookmark (
    id              INTEGER PRIMARY KEY,
    parent_id       INTEGER REFERENCES bookmark(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    level           INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 10),
    title           TEXT    NOT NULL CHECK (title <> ''),   -- F-045
    target_page     INTEGER REFERENCES page(page_number),
    target_y        INTEGER,
    target_zoom     REAL,
    -- generat automat dintr-un stil cu rol de titlu (O-023)
    generated_from_style TEXT
);

CREATE INDEX idx_bookmark_parent ON bookmark (parent_id, order_index);


-- -----------------------------------------------------------------------------
-- Campuri de formular (H-001 ... H-052)
-- -----------------------------------------------------------------------------
CREATE TABLE form_field (
    id              INTEGER PRIMARY KEY,
    page_id         INTEGER NOT NULL REFERENCES page(id) ON DELETE CASCADE,
    -- H-013: numele e obligatoriu si unic in document
    field_name      TEXT    NOT NULL UNIQUE
                    CHECK (field_name <> ''
                       AND field_name NOT LIKE '.%'
                       AND field_name NOT LIKE '%.'
                       AND field_name NOT LIKE '%..%'),
    field_type      TEXT    NOT NULL
                    CHECK (field_type IN ('text','checkbox','radio','dropdown',
                                          'listbox','button','signature')),
    tooltip         TEXT,
    is_required     INTEGER NOT NULL DEFAULT 0 CHECK (is_required IN (0,1)),
    is_readonly     INTEGER NOT NULL DEFAULT 0 CHECK (is_readonly IN (0,1)),
    -- geometrie
    pos_x           REAL    NOT NULL,
    pos_y           REAL    NOT NULL,
    width           REAL    NOT NULL CHECK (width  >= 8),   -- H-005
    height          REAL    NOT NULL CHECK (height >= 8),
    units           TEXT    NOT NULL DEFAULT 'cm' CHECK (units IN ('cm','in','pt')),
    -- aspect (H-016)
    fill_color      TEXT,
    border_color    TEXT,
    border_width    REAL    CHECK (border_width IS NULL OR border_width >= 0),
    font_name       TEXT,
    font_size       REAL,
    text_color      TEXT,
    check_color     TEXT,                      -- H-017
    -- format (H-018, H-019)
    text_format     TEXT    CHECK (text_format IS NULL OR
                                   text_format IN ('text','date')),
    date_format     TEXT,
    is_multiline    INTEGER NOT NULL DEFAULT 0 CHECK (is_multiline IN (0,1)),
    max_symbols     INTEGER CHECK (max_symbols IS NULL OR
                                   max_symbols BETWEEN 1 AND 32767),
    -- grup pentru butoane radio (H-027)
    group_name      TEXT,
    group_tooltip   TEXT,
    -- liste (H-025, H-026)
    allow_custom    INTEGER NOT NULL DEFAULT 0 CHECK (allow_custom     IN (0,1)),
    allow_multiple  INTEGER NOT NULL DEFAULT 0 CHECK (allow_multiple   IN (0,1)),
    -- copii legate (H-041)
    linked_to_id    INTEGER REFERENCES form_field(id) ON DELETE SET NULL,
    -- valoarea completata (H-048)
    field_value     TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    -- H-027: butoanele radio au nevoie de grup
    CHECK (field_type <> 'radio' OR group_name IS NOT NULL),
    -- H-019: limita de caractere doar la camp text
    CHECK (max_symbols IS NULL OR field_type = 'text')
);

CREATE INDEX idx_form_field_page ON form_field (page_id);
CREATE INDEX idx_form_field_group ON form_field (group_name) WHERE group_name IS NOT NULL;

CREATE TABLE form_field_item (
    id              INTEGER PRIMARY KEY,
    field_id        INTEGER NOT NULL REFERENCES form_field(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    item_text       TEXT    NOT NULL,
    item_value      TEXT,
    is_default      INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0,1)),
    UNIQUE (field_id, order_index)
);

-- H-023: un singur element implicit per camp
CREATE TRIGGER form_field_item_single_default
AFTER UPDATE OF is_default ON form_field_item
WHEN NEW.is_default = 1
BEGIN
    UPDATE form_field_item SET is_default = 0
     WHERE field_id = NEW.field_id AND id <> NEW.id AND is_default = 1;
END;

CREATE TABLE form_field_action (
    id              INTEGER PRIMARY KEY,
    field_id        INTEGER NOT NULL REFERENCES form_field(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    trigger_event   TEXT    NOT NULL
                    CHECK (trigger_event IN ('click','drop','mouse_enter','mouse_exit',
                                             'on_focus','on_blur')),
    action_type     TEXT    NOT NULL,          -- H-031 ... H-038
    parameters      TEXT    NOT NULL DEFAULT '{}',
    UNIQUE (field_id, order_index)
);


-- -----------------------------------------------------------------------------
-- Atasamente incorporate (F-047, F-048)
-- -----------------------------------------------------------------------------
CREATE TABLE attachment (
    id              INTEGER PRIMARY KEY,
    file_name       TEXT    NOT NULL,
    description     TEXT,
    mime_type       TEXT,
    size_bytes      INTEGER NOT NULL CHECK (size_bytes >= 0),
    -- fisierul pe disc, in <proiect>/attachments/
    stored_path     TEXT    NOT NULL UNIQUE,
    sha256          TEXT    NOT NULL,
    -- F-048: avertisment la deschiderea fisierelor executabile
    is_executable   INTEGER NOT NULL DEFAULT 0 CHECK (is_executable IN (0,1)),
    added_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);


-- -----------------------------------------------------------------------------
-- Semnaturi digitale aplicate (G-010 ... G-024). Doar metadate de verificare.
-- -----------------------------------------------------------------------------
CREATE TABLE digital_signature (
    id              INTEGER PRIMARY KEY,
    page_id         INTEGER REFERENCES page(id) ON DELETE SET NULL,
    form_field_id   INTEGER REFERENCES form_field(id) ON DELETE SET NULL,
    signer_name     TEXT,
    certificate_thumbprint TEXT NOT NULL,
    certificate_issuer     TEXT,
    certificate_valid_from TEXT,
    certificate_valid_to   TEXT,
    sign_reason     TEXT,
    sign_location   TEXT,
    sign_contact    TEXT,
    signed_at       TEXT    NOT NULL,
    hash_algorithm  TEXT    NOT NULL DEFAULT 'SHA-256'
                    CHECK (hash_algorithm IN ('SHA-256','SHA-384','SHA-512')),
    -- G-014, G-019
    timestamp_url   TEXT,
    has_timestamp   INTEGER NOT NULL DEFAULT 0 CHECK (has_timestamp IN (0,1)),
    is_ltv          INTEGER NOT NULL DEFAULT 0 CHECK (is_ltv IN (0,1)),
    -- G-022
    validation_status TEXT  NOT NULL DEFAULT 'unknown'
                    CHECK (validation_status IN ('valid','invalid','expired',
                                                 'untrusted','unknown')),
    validated_at    TEXT,
    appearance      TEXT    NOT NULL DEFAULT '{}'   -- JSON: campurile afisate (G-015)
);


-- -----------------------------------------------------------------------------
-- Diferentele unei comparatii (R-020 ... R-052). Salvate ca sa se poata
-- redeschide o comparatie fara a o reface.
-- -----------------------------------------------------------------------------
CREATE TABLE comparison (
    id              INTEGER PRIMARY KEY,
    path_left       TEXT    NOT NULL,
    path_right      TEXT    NOT NULL,
    language_codes  TEXT    NOT NULL,
    ignore_whitespace INTEGER NOT NULL DEFAULT 1 CHECK (ignore_whitespace IN (0,1)),
    ignore_hyphenation INTEGER NOT NULL DEFAULT 1 CHECK (ignore_hyphenation IN (0,1)),
    ignore_tables   INTEGER NOT NULL DEFAULT 0 CHECK (ignore_tables IN (0,1)),
    compared_at     TEXT    NOT NULL,
    duration_ms     INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0)
);

CREATE TABLE comparison_difference (
    id              INTEGER PRIMARY KEY,
    comparison_id   INTEGER NOT NULL REFERENCES comparison(id) ON DELETE CASCADE,
    order_index     INTEGER NOT NULL CHECK (order_index >= 0),
    diff_type       TEXT    NOT NULL
                    CHECK (diff_type IN ('inserted','deleted','replaced','formatting')),
    text_left       TEXT,
    text_right      TEXT,
    page_left       INTEGER,
    page_right      INTEGER,
    bbox_left       TEXT,                      -- JSON
    bbox_right      TEXT,
    -- R-036
    is_ignored      INTEGER NOT NULL DEFAULT 0 CHECK (is_ignored IN (0,1)),
    UNIQUE (comparison_id, order_index)
);

CREATE INDEX idx_comparison_diff ON comparison_difference (comparison_id, order_index);
CREATE INDEX idx_comparison_diff_active
    ON comparison_difference (comparison_id) WHERE is_ignored = 0;


-- -----------------------------------------------------------------------------
-- Istoricul de operatii pentru undo/redo (J-023, E-042). Se pastreaza in baza
-- de date ca sa supravietuiasca unei caderi; se goleste la inchiderea curata.
-- -----------------------------------------------------------------------------
CREATE TABLE undo_entry (
    id              INTEGER PRIMARY KEY,
    sequence        INTEGER NOT NULL UNIQUE,
    operation       TEXT    NOT NULL,
    description     TEXT    NOT NULL,          -- textul din meniul Undo
    forward_payload TEXT    NOT NULL,          -- JSON, ce s-a facut
    reverse_payload TEXT    NOT NULL,          -- JSON, cum se desface
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX idx_undo_sequence ON undo_entry (sequence DESC);

-- minimum 50 de pasi; taiem la 200 ca sa nu creasca nelimitat
CREATE TRIGGER undo_entry_cap
AFTER INSERT ON undo_entry
BEGIN
    DELETE FROM undo_entry
     WHERE id IN (SELECT id FROM undo_entry ORDER BY sequence DESC LIMIT -1 OFFSET 200);
END;


-- =============================================================================
-- VEDERI UTILE
-- =============================================================================

-- Starea proiectului intr-un singur rand: ce se arata in bara de stare.
CREATE VIEW v_project_status AS
SELECT
    (SELECT COUNT(*) FROM page)                                  AS total_pages,
    (SELECT COUNT(*) FROM page WHERE status = 'recognized')      AS recognized_pages,
    (SELECT COUNT(*) FROM page WHERE status = 'verified')        AS verified_pages,
    (SELECT COUNT(*) FROM page WHERE status = 'analyzed')        AS pending_pages,
    (SELECT COUNT(*) FROM page WHERE status = 'error')           AS error_pages,
    (SELECT COUNT(*) FROM word WHERE is_uncertain = 1)           AS uncertain_words,
    (SELECT COUNT(*) FROM page_warning WHERE is_dismissed = 0)   AS open_warnings;

-- Q-034: paginile care au fost invalidate dupa ultima recunoastere
CREATE VIEW v_pages_needing_recognition AS
SELECT p.id, p.page_number, p.status
  FROM page p
 WHERE p.status = 'analyzed'
   AND EXISTS (SELECT 1 FROM area a WHERE a.page_id = p.id);

-- O-004, O-005: navigarea la urmatorul cuvant nesigur, in ordinea documentului
CREATE VIEW v_uncertain_words_ordered AS
SELECT w.id        AS word_id,
       w.text,
       w.confidence,
       p.page_number,
       a.order_index AS area_order,
       tb.order_index AS block_order,
       tl.order_index AS line_order,
       w.order_index  AS word_order,
       w.bbox_x, w.bbox_y, w.bbox_w, w.bbox_h
  FROM word w
  JOIN text_line  tl ON tl.id = w.line_id
  JOIN text_block tb ON tb.id = tl.block_id
  JOIN area       a  ON a.id  = tb.area_id
  JOIN page       p  ON p.id  = a.page_id
 WHERE w.is_uncertain = 1
   AND w.is_verified  = 0
 ORDER BY p.page_number, a.order_index, tb.order_index,
          tl.order_index, w.order_index;

-- Textul unei pagini, reconstituit in ordinea corecta. Folosit la export si la
-- verificarea redactarii (G-029).
CREATE VIEW v_page_text AS
SELECT p.page_number,
       a.order_index  AS area_order,
       tb.order_index AS block_order,
       tl.order_index AS line_order,
       GROUP_CONCAT(w.text, ' ') AS line_text
  FROM page p
  JOIN area       a  ON a.page_id  = p.id
  JOIN text_block tb ON tb.area_id = a.id
  JOIN text_line  tl ON tl.block_id = tb.id
  JOIN word       w  ON w.line_id   = tl.id
 WHERE w.is_redacted = 0
 GROUP BY p.page_number, a.order_index, tb.order_index, tl.order_index
 ORDER BY p.page_number, a.order_index, tb.order_index, tl.order_index;

-- H-047: campurile obligatorii necompletate, pentru avertismentul la trimitere
CREATE VIEW v_incomplete_required_fields AS
SELECT f.id, f.field_name, f.field_type, p.page_number
  FROM form_field f
  JOIN page p ON p.id = f.page_id
 WHERE f.is_required = 1
   AND (f.field_value IS NULL OR f.field_value = '');

-- S-030: ultima rulare a fiecarei sarcini Hot Folder (in app.db)
-- (vederea se creeaza in app.db, nu in project.db)
