// Separate school-only reader: no database, identity, confirmation or save tool.
function handler(params) {
  const input = JSON.parse(params.notice_input);
  const keys = ['source_text', 'source_ref', 'reference_at'];
  if (!input || Array.isArray(input) || typeof input !== 'object'
      || Object.keys(input).length !== keys.length
      || keys.some(k => !Object.prototype.hasOwnProperty.call(input, k))) {
    throw new Error('INVALID_READ_ONLY_INPUT');
  }
  if (typeof input.source_text !== 'string' || !input.source_text.trim()
      || input.source_text.length > 20000) throw new Error('INVALID_SOURCE');
  if (typeof input.source_ref !== 'string' || !input.source_ref.trim()
      || input.source_ref.length > 128) throw new Error('INVALID_SOURCE_REF');
  if (input.reference_at !== null && (typeof input.reference_at !== 'string'
      || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00$/.test(input.reference_at)
      || !Number.isFinite(Date.parse(input.reference_at))
      || new Date(Date.parse(input.reference_at) + 8 * 3600000).toISOString().slice(0,19)
        !== input.reference_at.slice(0,19))) throw new Error('INVALID_REFERENCE_TIME');
  const source = {source_text:input.source_text, source_ref:input.source_ref,
    reference_at:input.reference_at, extracted_at:new Date().toISOString()};
  return {source_json:JSON.stringify(source), model_input:JSON.stringify({...source,
    source_segments:input.source_text.split(/\n/).filter(s=>s.trim())})};
}
