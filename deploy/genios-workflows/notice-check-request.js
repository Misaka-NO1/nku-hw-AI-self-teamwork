// No model-generated date/estimate defaults. Explicit user fields only.
// Keep raw nested JSON so duplicate keys survive and the backend rejects them.
function handler(params) {
  const sourceRaw = params.read_request_json;
  const source = JSON.parse(sourceRaw);
  if (!source || Array.isArray(source) || typeof source !== 'object'
      || typeof params.item_id !== 'string' || !params.item_id) throw new Error('INVALID_ITEM');
  for (const name of ['user_confirmations_json','window_json','available_windows_json']) {
    if (typeof params[name] !== 'string') throw new Error('MISSING_EXPLICIT_INPUT');
    JSON.parse(params[name]);
  }
  let query = sourceRaw.trim().slice(0,-1) + ',"item_id":' + JSON.stringify(params.item_id)
    + ',"user_confirmations":' + params.user_confirmations_json + ',"window":' + params.window_json
    + ',"available_windows":' + params.available_windows_json;
  if (params.buffers_json !== undefined && params.buffers_json !== '') {
    JSON.parse(params.buffers_json); query += ',"buffers":' + params.buffers_json;
  }
  return {query_json:query+'}'};
}
