from copy import deepcopy
import pytest
from app.core.degree_progress import ELECTIVE_NAMES, question_progress


def progress(actuals=('0', '0', '2', '0', '0', '2'), parent_actual='7'):
    def module(title, required, actual):
        return {'title': title, 'required_credits': required,
            'school_actual_credits': actual, 'school_status': '是', 'school_note': None}
    return {'schema_version': '1.0.0', 'kind': 'degree_credit_progress',
        'program': '虚构验收专业', 'cohort': '2025',
        'summary': {'required_credits': '150', 'completed_credits': '10', 'actual_credits': '10',
            'reported_result': '预审', 'reviewed_at': None, 'note': None},
        'modules': [module('二 通识选修课(必须通过的子组数量4)', '14', parent_actual)] +
            [module(f'({number}) {name}', '2' if number == '二' else '0', actual)
                for number, name, actual in zip('一二三四五六', ELECTIVE_NAMES, actuals)] +
            [module('三 大类基础课程', '18', '18')],
        'has_in_progress_courses': True}


def test_exact_sum_art_counts_within_four_and_no_unknown_credit_allocation():
    original = progress()
    before = deepcopy(original)
    data = question_progress(original)['general_elective_progress']
    assert original == before  # projection must not change a persisted/uploaded report
    assert data['status'] == 'provisional'
    assert data['reached_module_count'] == 2
    assert data['additional_modules_to_reach_four'] == 2
    assert data['art_module_threshold_gap'] == '2'
    assert data['additional_other_modules_if_art_brought_to_threshold'] == 1
    assert data['reported_submodule_actual_sum'] == '4'  # 2 + 2 is not 7
    assert data['parent_minus_submodule_actual_credits'] == '3'
    assert not data['aggregate_matches_submodules']
    assert data['parent_provisional_credit_gap'] == '7'  # never subtract unallocated 3 again
    assert len(data['other_module_options_below_threshold']) == 3
    assert data['policy_verification_status'] == 'needs_policy'


@pytest.mark.parametrize('actuals,reached,other', [
    (('0', '2', '2', '0', '0', '2'), 3, 1),
    (('2', '2', '2', '0', '0', '2'), 4, 0),
    (('2', '0', '2', '2', '0', '2'), 4, 0),
    (('1.5', '1.5', '2', '0', '0', '2'), 2, 1),
    (('2', '2', '2', '2', '2', '2'), 6, 0),
])
def test_count_is_dynamic_not_fixed_to_one_users_example(actuals, reached, other):
    data = question_progress(progress(actuals))['general_elective_progress']
    assert data['reached_module_count'] == reached
    assert data['additional_modules_to_reach_four'] == max(0, 4 - reached)
    assert data['additional_other_modules_if_art_brought_to_threshold'] == other


def test_decimal_and_negative_aggregate_difference_are_not_hidden():
    data = question_progress(progress(('0', '0', '2.25', '0', '0', '2.1'), '3'))['general_elective_progress']
    assert data['reported_submodule_actual_sum'] == '4.35'
    assert data['parent_minus_submodule_actual_credits'] == '-1.35'
    assert not data['aggregate_matches_submodules']

def test_explicit_parent_direct_in_progress_explains_difference_without_guessing_or_reallocation():
    report = progress()
    for index, module in enumerate(report['modules']):
        module['school_in_progress_credits'] = '3' if index == 0 else '0'
        module['school_direct_in_progress_credits'] = '3' if index == 0 else '0'
    result = question_progress(report)
    data = result['general_elective_progress']
    assert data['difference_explained_by_direct_marked_in_progress']
    assert data['parent_direct_marked_in_progress_credits'] == '3'
    assert data['submodule_marked_in_progress_credits_sum'] == '0'
    assert result['modules'][0]['reported_actual_excluding_marked_in_progress'] == '4'
    assert data['parent_provisional_credit_gap'] == '7'  # current school/pre-audit gap stays distinct
    assert data['reached_module_count'] == 2
    old = question_progress(progress())
    assert old['modules'][0]['reported_actual_excluding_marked_in_progress'] is None
    assert not old['general_elective_progress']['difference_explained_by_direct_marked_in_progress']

@pytest.mark.parametrize('total,direct', [('8','3'),('3','4'),(None,'1'),('301',None)])
def test_invalid_in_progress_totals_do_not_become_read_answers(total, direct):
    from app.core.errors import AppError
    report=progress()
    report['modules'][0].update(school_in_progress_credits=total,school_direct_in_progress_credits=direct)
    with pytest.raises(AppError): question_progress(report)


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'wrong_group', 'two_parents', 'no_parent'])
def test_missing_ambiguous_or_out_of_group_modules_are_not_guessed(change):
    report = progress()
    if change == 'missing':
        report['modules'].pop(2)
    elif change == 'duplicate':
        report['modules'].insert(2, deepcopy(report['modules'][1]))
    elif change == 'wrong_group':
        report['modules'].insert(4, deepcopy(report['modules'][-1]))
    elif change == 'two_parents':
        report['modules'].append(deepcopy(report['modules'][0]))
    else:
        report['modules'][0]['title'] = '五 专业选修课'
    data = question_progress(report)['general_elective_progress']
    assert data['status'] == 'unavailable'
    assert 'reached_module_count' not in data
