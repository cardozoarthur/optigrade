from app.services.constraint_intelligence import interpret_teacher_constraint


def test_heuristic_extracts_unavailability() -> None:
    result = interpret_teacher_constraint("Nao posso trabalhar sexta a tarde")

    assert result.rule["type"] == "availability"
    assert result.rule["preference"] < 0
    assert 4 in result.rule["days"]


def test_heuristic_extracts_course_preference() -> None:
    result = interpret_teacher_constraint("Prefiro dar Pesquisa Operacional")

    assert result.rule["type"] in {"preference", "course_preference"}
    assert result.rule["preference"] > 0

