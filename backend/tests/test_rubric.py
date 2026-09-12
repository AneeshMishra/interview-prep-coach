import pytest

from app.interview.rubric import Rubric, RubricNotFoundError, load_rubric


def test_load_rubric_reads_system_design_yaml():
    rubric = load_rubric("system_design")
    assert rubric.name == "system_design"
    assert rubric.version == "1.0"
    assert "architecture" in rubric.criteria
    assert rubric.score.min == 1
    assert rubric.score.max == 5


def test_load_rubric_raises_for_unknown_name():
    with pytest.raises(RubricNotFoundError):
        load_rubric("does-not-exist")


def test_weighted_score_is_a_weighted_average():
    rubric = Rubric(
        name="test",
        version="1.0",
        criteria={"a": {"weight": 3}, "b": {"weight": 1}},
        score={"min": 1, "max": 5},
    )
    # (5*3 + 1*1) / 4 = 4.0
    assert rubric.weighted_score({"a": 5, "b": 1}) == pytest.approx(4.0)


def test_weighted_score_clamps_out_of_range_values():
    rubric = Rubric(
        name="test", version="1.0", criteria={"a": {"weight": 1}}, score={"min": 1, "max": 5}
    )
    assert rubric.weighted_score({"a": 100}) == 5
    assert rubric.weighted_score({"a": -3}) == 1


def test_weighted_score_treats_missing_criteria_as_minimum():
    rubric = Rubric(
        name="test",
        version="1.0",
        criteria={"a": {"weight": 1}, "b": {"weight": 1}},
        score={"min": 1, "max": 5},
    )
    # "b" missing entirely -> scored at the rubric minimum, not skipped/ignored.
    assert rubric.weighted_score({"a": 5}) == pytest.approx(3.0)
