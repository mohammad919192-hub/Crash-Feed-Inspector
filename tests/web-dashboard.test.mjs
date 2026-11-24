import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('../site/index.html', import.meta.url), 'utf8');

test('dashboard exposes all expected views and auth controls', () => {
  for (const id of ['auth', 'login', 'app', 'view-overview', 'view-rounds', 'view-research', 'view-operations', 'refresh', 'export']) {
    assert.match(html, new RegExp('id="' + id + '"'));
  }
});

test('dashboard uses only a publishable key and no privileged browser credential', () => {
  assert.match(html, /sb_publishable_/);
  assert.doesNotMatch(html, /SUPABASE_SERVICE_ROLE_KEY|service_role_key\s*=/i);
});

test('inline dashboard script parses successfully', () => {
  const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  assert.equal(scripts.length, 1);
  assert.doesNotThrow(() => new vm.Script(scripts[0][1]));
});

test('all dashboard sections are hidden except overview by default', () => {
  assert.match(html, /class="view active" id="view-overview"/);
  for (const view of ['rounds', 'research', 'operations']) {
    assert.match(html, new RegExp('class="view" id="view-' + view + '"'));
  }
});

test('dashboard reads data only through the protected Edge Function', () => {
  assert.match(html, /functions\.invoke\(["']dashboard-read["']\)/);
  assert.doesNotMatch(html, /\.from\(["']crash_(rounds|predictions|ingestion_runs)["']\)/);
});

test('dashboard read function validates trusted app metadata before service-role queries', () => {
  const source = readFileSync(new URL('../supabase/functions/dashboard-read/index.ts', import.meta.url), 'utf8');
  assert.match(source, /auth\.getUser\(token\)/);
  assert.match(source, /app_metadata\?\.crash_dashboard !== true/);
  assert.match(source, /SUPABASE_SERVICE_ROLE_KEY/);
  assert.doesNotMatch(source, /user_metadata/);
});
