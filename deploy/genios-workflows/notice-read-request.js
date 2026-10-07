// Code-node candidate: preserve this new input and ORIGINAL model JSON.
// Sends a proposal to OAuth read only; no fixture substitution or save call.
function handler(params) {
  const source = JSON.parse(params.source_json);
  if (!source || typeof source.source_text !== 'string' || typeof source.source_ref !== 'string'
      || !Object.hasOwn(source,'reference_at')) throw new Error('INVALID_SOURCE');
  if (typeof params.extraction !== 'string') throw new Error('INVALID_EXTRACTION');
  const request = {source_text:source.source_text,source_ref:source.source_ref,
    reference_at:source.reference_at || null,model_output:params.extraction,fictional_data_confirmed:true};
  return {query_json:JSON.stringify(request)};
}
