from python_proiect.__main__ import main


def test_main(capsys):
    main()
    assert "Salut" in capsys.readouterr().out
