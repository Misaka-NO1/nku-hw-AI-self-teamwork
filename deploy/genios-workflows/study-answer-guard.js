// Fixed public evidence, not an ApiEnvelope and not a saved record.
function handler(params) {
  if (!params || typeof params.status !== 'string' || typeof params.sources_json !== 'string'
      || params.sources_json.length > 30000) throw new Error('INVALID_STUDY_RESULT');
  const sources = JSON.parse(params.sources_json);
  if (!Array.isArray(sources) || sources.length > 20) throw new Error('INVALID_STUDY_SOURCES');
  const warning = '历史复习资料，不代表当前考试范围；提取/OCR尚未逐页人工核对，公式、代码、图表请对照原PDF。';
  if (params.status !== 'grounded' || !sources.length) {
    return {result: {status: ['unknown_course', 'unknown_material'].includes(params.status) ? params.status : 'no_matching_body',
      answer: '未检索到指定课程/材料可引用的正文，不改换学期、课程或材料，也不使用演示笔记补答。', sources: [], warnings: [warning]}};
  }
  if (typeof params.answer !== 'string' || !params.answer.trim() || params.answer.length > 12000) {
    throw new Error('INVALID_STUDY_ANSWER');
  }
  // Require explicit material/page pairs rather than accepting unrelated known IDs and pages.
  const pairs = new Set(sources.map(source => source.material_id + '@' + source.page));
  const citations = [...params.answer.matchAll(/\[(study-[a-z0-9-]+)@([1-9][0-9]{0,3})\]/g)];
  const ids = new Set(sources.map(source => source.material_id));
  const pages = new Set(sources.map(source => source.page));
  const citedIds = params.answer.match(/study-[a-z0-9-]+/g) || [];
  const citedPages = [...params.answer.matchAll(/PDF\s*第\s*([0-9]+)\s*页/g)].map(match => Number(match[1]));
  if (!citations.length || citations.some(match => !pairs.has(match[1] + '@' + Number(match[2])))
      || citedIds.some(id => !ids.has(id)) || citedPages.some(page => !pages.has(page))
      || /https?:\/\//i.test(params.answer)) {
    return {result: {status: 'citation_check_failed', answer: '生成回答的引用校验未通过，暂不展示该回答；请查看下列实际召回来源。',
      sources, warnings: [warning]}};
  }
  return {result: {status: 'grounded', answer: params.answer, sources, warnings: [warning]}};
}
