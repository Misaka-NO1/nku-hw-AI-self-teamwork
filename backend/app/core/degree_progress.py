"""Personal module credits only. No course grades, identity input or inferred graduation."""
from decimal import Decimal
import json
import re
from uuid import uuid4
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError, field_validator, model_validator
from app.core.errors import AppError
from app.core.security import canonical_json, payload_hash, require_idempotency_key

Credit = Annotated[str, Field(strict=True, pattern=r'^(?:0|[1-9]\d{0,2})(?:\.\d{1,2})?$')]
Text = Annotated[str, Field(strict=True, min_length=1, max_length=300)]

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class Summary(Strict):
    required_credits: Credit | None
    completed_credits: Credit | None
    actual_credits: Credit | None
    reported_result: Text | None
    reviewed_at: Text | None
    note: Text | None

class Module(Strict):
    title: Text
    required_credits: Credit
    school_actual_credits: Credit
    school_status: Text | None
    school_note: Text | None
    school_in_progress_credits: Credit | None = None
    school_direct_in_progress_credits: Credit | None = None

    @field_validator('school_in_progress_credits', 'school_direct_in_progress_credits')
    @classmethod
    def bounded_ongoing(cls, value):
        if value is not None and Decimal(value) > 300:
            raise ValueError('credit out of range')
        return value

    @model_validator(mode='after')
    def consistent_ongoing(self):
        total, value = self.school_in_progress_credits, self.school_direct_in_progress_credits
        if total is not None and Decimal(total) > Decimal(self.school_actual_credits):
            raise ValueError('in-progress exceeds reported actual')
        if value is not None and (total is None or Decimal(value) > Decimal(total)):
            raise ValueError('direct in-progress requires bounded total')
        return self

class Progress(Strict):
    schema_version: Literal['1.0.0']
    kind: Literal['degree_credit_progress']
    program: Text | None
    cohort: Text | None
    summary: Summary
    modules: Annotated[list[Module], Field(min_length=1, max_length=200)]
    has_in_progress_courses: StrictBool

    @field_validator('modules', 'summary')
    @classmethod
    def bounded_credits(cls, value):
        records = value if isinstance(value, list) else [value]
        for record in records:
            for name, credit in record.model_dump().items():
                if 'credits' in name and credit is not None and Decimal(credit) > 300:
                    raise ValueError('credit out of range')
        return value

class SaveProgress(Strict):
    report: Progress
    expected_revision: Annotated[StrictInt, Field(ge=0, le=2147483646)]
    expected_workspace_ref: Annotated[str, Field(strict=True, min_length=1, max_length=128)]
    confirmed: StrictBool

def gap(required, actual):
    if required is None or actual is None:
        return None
    result = max(Decimal(required) - Decimal(actual), Decimal(0))
    return format(result, 'f').rstrip('0').rstrip('.') if '.' in format(result, 'f') else format(result, 'f')

def validate_save(value):
    try:
        body = SaveProgress.model_validate(value)
        if len(canonical_json(body.model_dump()).encode()) > 131072:
            raise ValueError('oversize')
    except (ValueError, TypeError, ValidationError):
        raise AppError(422, 'VALIDATION_ERROR', 'Expected module credit progress only; courses, grades and identity fields are not accepted') from None
    if not body.confirmed:
        raise AppError(409, 'CONFIRMATION_REQUIRED', 'Review your report and explicitly confirm saving')
    return body

def agent_report(arguments):
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate key')
            value[key] = item
        return value
    try:
        if type(arguments) is not dict or set(arguments) != {'report_json'}:
            raise ValueError('unexpected fields')
        raw = arguments['report_json']
        if type(raw) is not str or len(raw.encode()) > 131072:
            raise ValueError('oversize')
        value = json.loads(raw, object_pairs_hook=unique_pairs)
        report = Progress.model_validate(value).model_dump(exclude_unset=True)
        if len(canonical_json(report).encode()) > 131072:
            raise ValueError('oversize')
        return report
    except (ValueError, TypeError, RecursionError, ValidationError):
        raise AppError(422, 'VALIDATION_ERROR', 'Upload the complete degree-progress.json module report; no grades, courses or identity fields') from None

class DegreeAgentImportService:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store

    def gate(self):
        if not (self.settings.cloud_degree_progress_enabled and self.settings.cloud_degree_agent_write_enabled):
            raise AppError(403, 'FORBIDDEN', 'Agent degree import is not enabled')

    def prepare(self, args, arguments):
        self.gate()
        report = agent_report(arguments)
        result = self.store.degree_agent_call('prepare', {**args, 'report': report,
            'draft_id': 'degree_' + uuid4().hex, 'payload_hash': payload_hash(report)})
        return {**result, 'report': question_progress(result['report']), 'saved': False,
            'confirmation_required': True}

    def confirm(self, args, arguments):
        self.gate()
        if (type(arguments) is not dict or set(arguments) != {'draft_id','payload_hash','confirmed'}
            or type(arguments['draft_id']) is not str or not re.fullmatch(r'degree_[0-9a-f]{32}', arguments['draft_id'])
            or type(arguments['payload_hash']) is not str or not re.fullmatch(r'[0-9a-f]{64}', arguments['payload_hash'])):
            raise AppError(422, 'VALIDATION_ERROR', 'Use only the actual preview draft and hash')
        if arguments['confirmed'] is not True:
            raise AppError(409, 'CONFIRMATION_REQUIRED', 'Wait for explicit confirmation of this exact preview')
        result = self.store.degree_agent_call('confirm', {**args, **arguments})
        return {**format_degree_receipt(result), 'report': question_progress(result['report'])}

def question_progress(report):
    # Revalidate persisted contents and recalculate gaps; never trust model/client math.
    try:
        value = Progress.model_validate(report).model_dump(exclude_unset=True)
    except (ValidationError, ValueError):
        raise AppError(503, 'DEPENDENCY_UNAVAILABLE', 'Saved degree progress needs verification') from None
    value['summary']['credit_gap'] = gap(value['summary']['required_credits'], value['summary']['completed_credits'])
    for index, module in enumerate(value['modules']):
        module['source_index'] = index
        module['provisional_credit_gap'] = gap(module['required_credits'], module['school_actual_credits'])
        ongoing = module.get('school_in_progress_credits')
        module['reported_actual_excluding_marked_in_progress'] = (
            gap(module['school_actual_credits'], ongoing) if ongoing is not None else None)
    value['limitations'] = ['教务实修/预审可能包含在读；暂计差额不是最终未取得学分。',
        '父子分类不相加，原审核状态及缺必修仍需核对；未知不补零，不作毕业资格结论。']
    value['general_elective_policy'] = {
        'source': 'knowledge/degree/cs-2025/plan-rules.md',
        'source_url': 'https://jwc.nankai.edu.cn/2026/0119/c35436a589267/page.htm',
        'verification_status': 'needs_policy',
        'minimum_modules': 4, 'minimum_credits_per_selected_module': '2',
        'module_names': ['公能素质和服务中国','艺术审美与文化思辨','科学精神与健康生活',
            '社会发展与国家治理','工程素养与未来科技','世界文明与国际视野'],
        'art_requirement': {'cohort_from': 2023, 'minimum_credits': '2', 'course_kind': '艺术类课程'},
        'notes': ['至少选四个，不是六个都必须修满；总要求以本人方案为准，14 仅为计算机科学与技术 2025 版参考。',
            '艺术审美模块总学分不能证明艺术类课程要求满足；年级、模块归属及学校学分认定未核实则待核对。'],
    }
    value['general_elective_progress'] = elective_progress(value['modules'])
    return value

ELECTIVE_NAMES = ('公能素质和服务中国', '艺术审美与文化思辨', '科学精神与健康生活',
    '社会发展与国家治理', '工程素养与未来科技', '世界文明与国际视野')

def elective_progress(modules):
    """Read-only arithmetic, NOT course recognition or a graduation/policy verdict."""
    def title_without_number(title):
        return re.sub(r'^(?:[（(][一二三四五六七八九十0-9]+[）)]|[一二三四五六七八九十]+)[\s、.]*', '', title).strip()

    def is_named(title, name):
        text = title_without_number(title)
        return text == name or text.startswith(name + '(') or text.startswith(name + '（')

    def credit(value):
        text = format(value, 'f')
        return text.rstrip('0').rstrip('.') if '.' in text else text

    unavailable = {'status': 'unavailable', 'policy_verification_status': 'needs_policy',
        'reason': '需要唯一通识选修父项及六个可明确归属的子模块；不补零或猜归属。'}
    parents = [i for i, item in enumerate(modules) if is_named(item['title'], '通识选修课')]
    if len(parents) != 1:
        return unavailable
    parent_index = parents[0]
    children = []
    for item in modules[parent_index + 1:]:
        # A subsequent top-level category ends the group. Do not borrow similarly named
        # categories from another parent or treat the flat report as one giant group.
        if re.match(r'^[一二三四五六七八九十]+[\s、.]', item['title']):
            break
        children.append(item)
    matched = {name: [item for item in children if is_named(item['title'], name)] for name in ELECTIVE_NAMES}
    if any(len(items) != 1 for items in matched.values()):
        return unavailable
    actuals = {name: Decimal(items[0]['school_actual_credits']) for name, items in matched.items()}
    parent = modules[parent_index]
    reached = sum(amount >= 2 for amount in actuals.values())
    subtotal = sum(actuals.values(), Decimal(0))
    difference = Decimal(parent['school_actual_credits']) - subtotal
    art_name = ELECTIVE_NAMES[1]
    art_adds_module = int(actuals[art_name] < 2)
    direct_ongoing = parent.get('school_direct_in_progress_credits')
    child_ongoing = [matched[name][0].get('school_in_progress_credits') for name in ELECTIVE_NAMES]
    child_ongoing_sum = sum((Decimal(v) for v in child_ongoing), Decimal(0)) if all(v is not None for v in child_ongoing) else None
    ongoing = parent.get('school_in_progress_credits')
    explained = (direct_ongoing is not None and ongoing is not None and child_ongoing_sum is not None
        and Decimal(direct_ongoing) == difference
        and Decimal(ongoing) == Decimal(direct_ongoing) + child_ongoing_sum)
    return {
        'status': 'provisional', 'policy_verification_status': 'needs_policy',
        'parent_source_index': parent['source_index'],
        'parent_required_credits': parent['required_credits'],
        'parent_reported_actual_credits': parent['school_actual_credits'],
        'parent_provisional_credit_gap': parent['provisional_credit_gap'],
        'reported_submodule_actual_sum': credit(subtotal),
        'parent_minus_submodule_actual_credits': credit(difference),
        'aggregate_matches_submodules': difference == 0,
        'parent_marked_in_progress_credits': ongoing,
        'parent_direct_marked_in_progress_credits': direct_ongoing,
        'submodule_marked_in_progress_credits_sum': credit(child_ongoing_sum) if child_ongoing_sum is not None else None,
        'difference_explained_by_direct_marked_in_progress': explained,
        'minimum_modules': 4, 'minimum_credits_per_selected_module': '2',
        'reached_module_count': reached,
        'additional_modules_to_reach_four': max(0, 4 - reached),
        'art_module_is_part_of_six': True,
        'art_module_threshold_gap': credit(max(Decimal(2) - actuals[art_name], Decimal(0))),
        'additional_other_modules_if_art_brought_to_threshold': max(0, 4 - reached - art_adds_module),
        'other_module_options_below_threshold': [name for name in ELECTIVE_NAMES
            if name != art_name and actuals[name] < 2],
        'modules': [{'name': name, 'source_index': matched[name][0]['source_index'],
            'reported_actual_credits': credit(actuals[name]), 'provisionally_reaches_two': actuals[name] >= 2}
            for name in ELECTIVE_NAMES],
        'limitations': [
            '艺术属于六个模块，补足艺术也计入四个模块，不能额外多算。',
            '模块数量门槛不替代父项总学分缺口；艺术类课程认定和年级规则适用仍需核对。',
            '仅明确在读汇总可解释父子差额；旧报告未知不补零、不推测来源，不把父项直属课程自动分配给六子模块。',
            '剔除明确在读后的数值不是最终已取得学分；在读不等于未选，须单列说明。',
            '所有计数仅基于本报告的实修数，含在读预审，不表示正式认定或毕业资格。'],
    }

def format_degree_receipt(result):
    from app.cloud_identity_site import format_times
    if result.get('confirmed_epoch') is None:
        return {**{key:value for key,value in result.items() if key != 'confirmed_epoch'}, 'confirmed_at':None}
    return format_times(result)

class DegreeProgressService:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store

    def gate(self):
        if not self.settings.cloud_degree_progress_enabled:
            raise AppError(403, 'FORBIDDEN', 'Personal degree progress is not enabled')

    def read(self, args):
        self.gate()
        result = self.store.degree_call('read', args)
        if result['report'] is not None:
            result = {**result, 'report': question_progress(result['report'])}
        return result

    def save(self, args, value, key):
        self.gate()
        body = validate_save(value)
        return self.store.degree_call('save', {**args, **body.model_dump(),
            'key': require_idempotency_key(key), 'request_hash': payload_hash(body.model_dump())})
