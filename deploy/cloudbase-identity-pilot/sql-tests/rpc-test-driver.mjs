// Private pipe for Python API integration tests. PostgreSQL stays in this
// process while HTTP application instances restart. Never used in deployment.
import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createInterface } from 'node:readline';
const pg=new PGlite();
await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
await pg.exec(await readFile(new URL('../schema.sql',import.meta.url),'utf8'));
// Additive compatibility is exercised only in this private test pipe.
await pg.exec(await readFile(new URL('../competition-oauth-migration.sql',import.meta.url),'utf8'));
await pg.query("SELECT set_config('request.jwt.claims',$1,false)",[JSON.stringify({role:'service_role'})]);
const canonical=value=>value && typeof value==='object' ? Array.isArray(value) ? value.map(canonical) :
  Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])) : value;
for(const name of ['timetable.demo.json','notice-event.demo.json','notice-deadline.demo.json','notice-ambiguous.demo.json']) {
  const raw=JSON.parse(await readFile(new URL('../../../fixtures/'+name,import.meta.url),'utf8'));
  const hash=createHash('sha256').update(JSON.stringify(canonical(raw))).digest('hex');
  await pg.query('INSERT INTO nku_identity_pilot_v1.fixtures VALUES($1,$2,$3::jsonb)',[hash,name.startsWith('timetable')?'schedule':'task',JSON.stringify(raw)]);
}
process.stdout.write('{"ready":true}\n');
for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
  try {
    const {op,args}=JSON.parse(line);
    if (op==='__test_expire_browser_session__') {
      // Test pipe only (excluded from deployment): bounded fixed SQL, never a
      // caller-supplied query. Expire the synthetic session to exercise PG.
      if (!/^[0-9a-f]{64}$/.test(args.token_hash ?? '')) throw new Error('invalid test hash');
      await pg.query("UPDATE nku_identity_pilot_v1.browser_sessions SET expires_at=0 WHERE token_hash=$1",[args.token_hash]);
      process.stdout.write('{"ok":true,"data":{}}\n');
      continue;
    }
    const compatibility=op.startsWith('__competition__:');
    const sql=compatibility ? 'SELECT public.nku_competition_oauth_v1_rpc($1,$2::jsonb) result' : 'SELECT public.nku_identity_pilot_v1_rpc($1,$2::jsonb) result';
    const result=await pg.query(sql,[compatibility ? op.slice('__competition__:'.length) : op,JSON.stringify(args)]);
    process.stdout.write(JSON.stringify(result.rows[0].result)+'\n');
  } catch {
    // Do not print submitted params/SQL/credential hashes even on test failures.
    process.stdout.write('{"driver_error":true}\n');
  }
}
await pg.close();
