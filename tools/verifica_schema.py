#!/usr/bin/env python3
"""
Verifica schema SPEC_04_schema_bd.sql: o executa pe o baza de date in memorie
si testeaza regulile de business care sunt impuse la nivel de schema.

Rulare:  python -I tools/verifica_schema.py   (din radacina proiectului)
Ieșire:  cod 0 daca toate testele trec, 1 altfel.
"""
import sqlite3
import sys
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parent.parent / "docs" / "spec"
SQL = SPEC_DIR / "SPEC_04_schema_bd.sql"


def build():
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SQL.read_text(encoding="utf-8"))
    return con


def main():
    con = build()
    trecut, picat = [], []

    def check(nume, fn, trebuie_sa_cada):
        try:
            fn()
            con.commit()
            (picat if trebuie_sa_cada else trecut).append(nume)
        except sqlite3.Error as exc:
            con.rollback()
            (trecut if trebuie_sa_cada else picat).append(f"{nume} -> {exc}")

    # --- date minime ---
    con.execute(
        "insert into project (id,name,schema_version,app_version,created_at,updated_at)"
        " values (1,'test',1,'0.1','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')"
    )
    for n in (1, 2):
        con.execute(
            "insert into page (page_number,image_path,original_path,width_px,height_px,"
            "dpi_x,dpi_y,color_mode) values (?,?,?,100,100,300,300,'gray')",
            (n, f"i{n}.png", f"o{n}.png"),
        )
    con.commit()

    # --- M. zone ---
    check("M-008 zona sub 8 px refuzata", lambda: con.execute(
        "insert into area (page_id,order_index,area_type,bbox_x,bbox_y,bbox_w,bbox_h,polygon)"
        " values (1,0,'text',0,0,4,4,'[]')"), True)
    check("M-008 zona valida acceptata", lambda: con.execute(
        "insert into area (page_id,order_index,area_type,bbox_x,bbox_y,bbox_w,bbox_h,polygon)"
        " values (1,0,'text',0,0,50,20,'[[0,0]]')"), False)
    check("M-024 functia de text pe o zona de tabel refuzata", lambda: con.execute(
        "insert into area (page_id,order_index,area_type,bbox_x,bbox_y,bbox_w,bbox_h,polygon,"
        "text_function) values (1,1,'table',0,0,50,20,'[]','header')"), True)
    check("M-021 doua zone cu acelasi numar de ordine refuzate", lambda: con.execute(
        "insert into area (page_id,order_index,area_type,bbox_x,bbox_y,bbox_w,bbox_h,polygon)"
        " values (1,0,'picture',0,0,50,20,'[]')"), True)

    # --- N-026 invalidarea paginii ---
    con.execute("update page set status='recognized' where id=1")
    con.commit()
    con.execute("update area set bbox_w=60 where page_id=1")
    con.commit()
    stare = con.execute("select status from page where id=1").fetchone()[0]
    (trecut if stare == "analyzed" else picat).append(
        f"N-026 modificarea unei zone invalideaza textul paginii (={stare})")

    # --- J-055 ---
    con.execute("delete from page where id=2")
    con.commit()
    check("J-055 ultima pagina nu se poate sterge",
          lambda: con.execute("delete from page where id=1"), True)

    # --- H. formulare ---
    check("H-030 nume de camp cu punct final refuzat", lambda: con.execute(
        "insert into form_field (page_id,field_name,field_type,pos_x,pos_y,width,height)"
        " values (1,'nume.','text',0,0,10,10)"), True)
    check("H-020 camp mai mic de 8 px refuzat", lambda: con.execute(
        "insert into form_field (page_id,field_name,field_type,pos_x,pos_y,width,height)"
        " values (1,'c1','text',0,0,4,4)"), True)
    check("H-033 buton radio fara grup refuzat", lambda: con.execute(
        "insert into form_field (page_id,field_name,field_type,pos_x,pos_y,width,height)"
        " values (1,'r1','radio',0,0,10,10)"), True)
    check("H-030 limita de caractere pe o bifa refuzata", lambda: con.execute(
        "insert into form_field (page_id,field_name,field_type,pos_x,pos_y,width,height,"
        "max_symbols) values (1,'c2','checkbox',0,0,10,10,20)"), True)

    # --- P. limbi si dictionare ---
    con.execute("insert into ocr_language (code,display_name,script,is_builtin)"
                " values ('ron','Romana','latin',1)")
    con.commit()
    check("P-020 limba livrata nu se poate sterge",
          lambda: con.execute("delete from ocr_language where code='ron'"), True)
    check("P-041 cuvant de dictionar cu spatiu refuzat", lambda: con.execute(
        "insert into user_dictionary_word (language_id,word) values (1,'doua cuvinte')"), True)

    # --- T. sarcini automatizate ---
    con.execute("insert into automated_task (name) values ('t1')")
    con.commit()
    check("T-007 primul pas trebuie sa fie obtinerea imaginilor", lambda: con.execute(
        "insert into automated_task_step (task_id,order_index,step_type)"
        " values (1,0,'recognize')"), True)
    check("T-003 sarcina livrata nu se poate sterge", lambda: (
        con.execute("insert into automated_task (name,is_builtin) values ('builtin',1)"),
        con.execute("delete from automated_task where name='builtin'")), True)

    # --- S. Hot Folder ---
    check("S-038 mutarea originalului fara folder tinta refuzata", lambda: con.execute(
        "insert into hot_folder_task (name,source_kind,source_path,original_action,"
        "schedule_kind,schedule_interval_minutes) values ('h1','folder','/x','move','interval',5)"),
        True)
    check("S-032 planificare pe interval fara minute refuzata", lambda: con.execute(
        "insert into hot_folder_task (name,source_kind,source_path,schedule_kind)"
        " values ('h2','folder','/x','interval')"), True)

    # --- X, F, D ---
    check("X-148 scurtatura duplicata refuzata", lambda: (
        con.execute("insert into keyboard_shortcut (command_id,display_name,category,shortcut)"
                    " values ('a','A','x','Ctrl+S')"),
        con.execute("insert into keyboard_shortcut (command_id,display_name,category,shortcut)"
                    " values ('b','B','x','Ctrl+S')")), True)
    check("F-037 semn de carte fara titlu refuzat", lambda: con.execute(
        "insert into bookmark (order_index,title) values (0,'')"), True)
    check("F-036 nivel de semn de carte peste 10 refuzat", lambda: con.execute(
        "insert into bookmark (order_index,title,level) values (0,'t',11)"), True)
    check("D-018 grosime de linie de 20 pt refuzata", lambda: con.execute(
        "insert into annotation (page_id,annot_type,line_width,geometry,bbox_x,bbox_y,"
        "bbox_w,bbox_h) values (1,'line',20,'[]',0,0,1,1)"), True)

    # --- O. text ---
    con.execute("insert into text_block (area_id,order_index,bbox_x,bbox_y,bbox_w,bbox_h)"
                " values (1,0,0,0,10,10)")
    con.execute("insert into text_line (block_id,order_index,bbox_x,bbox_y,bbox_w,bbox_h)"
                " values (1,0,0,0,10,10)")
    con.execute("insert into word (line_id,order_index,text,confidence,is_verified,"
                "bbox_x,bbox_y,bbox_w,bbox_h) values (1,0,'factuar',55,1,0,0,10,10)")
    con.commit()
    con.execute("update word set text='factura' where id=1")
    con.commit()
    r = con.execute("select text,original_text,is_edited,is_verified from word where id=1").fetchone()
    (trecut if r == ("factura", "factuar", 1, 0) else picat).append(
        f"O-020 editarea unui cuvant pastreaza originalul si scoate starea verificata (={r})")

    con.execute("insert into word (line_id,order_index,text,confidence,bbox_x,bbox_y,"
                "bbox_w,bbox_h) values (1,1,'hotărâre',88,0,0,10,10)")
    con.commit()
    n = con.execute("select count(*) from word_fts where word_fts match 'hotarare'").fetchone()[0]
    (trecut if n == 1 else picat).append(f"C-002 cautarea ignora diacriticele (={n})")

    check("N-024 incredere peste 100 refuzata", lambda: con.execute(
        "insert into word (line_id,order_index,text,confidence,bbox_x,bbox_y,bbox_w,bbox_h)"
        " values (1,2,'x',150,0,0,10,10)"), True)

    # --- vederi ---
    for v in ("v_project_status", "v_pages_needing_recognition",
              "v_uncertain_words_ordered", "v_page_text",
              "v_incomplete_required_fields"):
        try:
            con.execute(f"select * from {v}").fetchall()
            trecut.append(f"vederea {v} se interogheaza")
        except sqlite3.Error as exc:
            picat.append(f"vederea {v} -> {exc}")

    print(f"TRECUT {len(trecut)}/{len(trecut) + len(picat)}")
    for x in trecut:
        print("  +", x)
    if picat:
        print("PICAT:")
        for x in picat:
            print("  -", x)
    return 1 if picat else 0


if __name__ == "__main__":
    sys.exit(main())
