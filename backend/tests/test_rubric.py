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


def test_average_criteria_averages_each_criterion_across_evaluations():
    rubric = Rubric(
        name="test",
        version="1.0",
        criteria={"a": {"weight": 1}, "b": {"weight": 1}},
        score={"min": 1, "max": 5},
    )
    breakdown = rubric.average_criteria([{"a": 4, "b": 2}, {"a": 2, "b": 4}, {"a": 3, "b": 3}])
    assert breakdown == pytest.approx({"a": 3.0, "b": 3.0})


def test_average_criteria_clamps_out_of_range_values():
    rubric = Rubric(name="test", version="1.0", criteria={"a": {"weight": 1}}, score={"min": 1, "max": 5})
    breakdown = rubric.average_criteria([{"a": 100}, {"a": -3}])
    # (5 + 1) / 2 = 3, not (100 + -3) / 2
    assert breakdown == pytest.approx({"a": 3.0})


def test_average_criteria_omits_a_criterion_never_scored_rather_than_defaulting_it():
    rubric = Rubric(
        name="test",
        version="1.0",
        criteria={"a": {"weight": 1}, "b": {"weight": 1}},
        score={"min": 1, "max": 5},
    )
    # "b" never appears in any evaluation — unlike weighted_score, it must
    # not be fabricated as the minimum; there's nothing to average.
    breakdown = rubric.average_criteria([{"a": 5}, {"a": 3}])
    assert breakdown == {"a": 4.0}


def test_average_criteria_only_averages_over_evaluations_that_actually_scored_it():
    rubric = Rubric(
        name="test",
        version="1.0",
        criteria={"a": {"weight": 1}, "b": {"weight": 1}},
        score={"min": 1, "max": 5},
    )
    # "b" was only scored once (2nd answer) — its average must be 2, not
    # averaged in as if it were 0/missing on the other two answers.
    breakdown = rubric.average_criteria([{"a": 4}, {"a": 2, "b": 2}, {"a": 3}])
    assert breakdown == pytest.approx({"a": 3.0, "b": 2.0})


def test_average_criteria_with_no_evaluations_returns_empty():
    rubric = Rubric(name="test", version="1.0", criteria={"a": {"weight": 1}}, score={"min": 1, "max": 5})
    assert rubric.average_criteria([]) == {}


def test_average_criteria_preserves_rubric_definition_order():
    rubric = Rubric(
        name="test",
        version="1.0",
        criteria={"z": {"weight": 1}, "a": {"weight": 1}, "m": {"weight": 1}},
        score={"min": 1, "max": 5},
    )
    breakdown = rubric.average_criteria([{"z": 1, "a": 2, "m": 3}])
    assert list(breakdown.keys()) == ["z", "a", "m"]
