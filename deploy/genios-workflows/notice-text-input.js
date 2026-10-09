// School code-node candidate. No network, identity, fixtures, or writes.
function handler(params) {
  if (typeof params.source_text !== 'string' || !params.source_text.trim()) throw new Error('EMPTY_NOTICE');
  if (params.source_text.length > 20000) throw new Error('NOTICE_TOO_LONG');
  if (typeof params.source_ref !== 'string' || !params.source_ref.trim() || params.source_ref.length > 128) {
    throw new Error('INVALID_SOURCE_REF');
  }
  const reference = params.reference_at || null;
  if (reference !== null && (typeof reference !== 'string' || !/[+]08:00$/.test(reference) || !Number.isFinite(Date.parse(reference)))) {
    throw new Error('INVALID_REFERENCE_TIME');
  }
  const source = {source_text: params.source_text, source_ref: params.source_ref, reference_at: reference,
    extracted_at: new Date().toISOString()};
  const source_json = JSON.stringify(source);
  return {source_json, model_input: source_json};
}
