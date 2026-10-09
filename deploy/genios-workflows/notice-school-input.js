// Single-string school Start adapter. This workflow accepts fictional text only.
function handler(params) {
  const input = JSON.parse(params.notice_input);
  const keys = ['source_text', 'source_ref', 'reference_at', 'fictional_data_confirmed'];
  if (!input || Array.isArray(input) || Object.keys(input).length !== keys.length
      || keys.some(k => !Object.prototype.hasOwnProperty.call(input, k))
      || input.fictional_data_confirmed !== true) throw new Error('FICTIONAL_INPUT_REQUIRED');
  if (typeof input.source_text !== 'string' || !input.source_text.trim()
      || input.source_text.length > 20000) throw new Error('INVALID_SOURCE');
  if (typeof input.source_ref !== 'string' || !input.source_ref.trim()
      || input.source_ref.length > 128) throw new Error('INVALID_SOURCE_REF');
  if (input.reference_at !== null && (typeof input.reference_at !== 'string'
      || !/[+]08:00$/.test(input.reference_at)
      || !Number.isFinite(Date.parse(input.reference_at)))) throw new Error('INVALID_REFERENCE_TIME');
  const source_json = JSON.stringify({source_text:input.source_text, source_ref:input.source_ref,
    reference_at:input.reference_at, extracted_at:new Date().toISOString()});
  return {source_json, model_input:JSON.stringify({...JSON.parse(source_json),
    source_segments:input.source_text.split(/\n/).filter(s=>s.trim())})};
}
