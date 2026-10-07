// Verify the actual generated deployment migration, not just schema source.
import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const pg = new PGlite();
try {
  await pg.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;');
  await pg.exec(await readFile(process.argv[2], 'utf8'));
  const tables = await pg.query("SELECT count(*)::int total,bool_and(relrowsecurity) secured FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='nku_identity_pilot_v1' AND c.relkind='r'");
  assert.deepEqual(tables.rows[0], {total: 15, secured: true});
  const fixtures = await pg.query('SELECT kind,count(*)::int total FROM nku_identity_pilot_v1.fixtures GROUP BY kind ORDER BY kind');
  assert.deepEqual(fixtures.rows, [{kind: 'schedule', total: 1}, {kind: 'task', total: 3}]);
  process.stdout.write(JSON.stringify({migration: 'passed', tables: 15, fixtures: 4, live_cloud: false})+'\n');
} finally { await pg.close(); }
