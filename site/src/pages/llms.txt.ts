// /llms.txt: doc-kitty's `llmsTxtRoute` plus the version stance (ADR 2026-10-31-1 D-9, #6934).
//
// A thin wrapper, not a fork. doc-kitty v0.7.0 has no preamble option on `llmsTxtRoute`
// (spec-kitty/doc-kitty#265), so this inserts `llmsStance` from dockitty-contract.json (projected
// from LLMS_STANCE in scripts/docs/_dockitty_contract.py, the single authority) after the title
// and description header. Everything else is doc-kitty's: only sections whose `feeds` include
// `llms` are listed. Delete this wrapper, and mount `llmsTxtRoute` with its preamble option, when
// #265 ships. The route always prints its machine-index line (spec-kitty/doc-kitty#312), so
// src/pages/api/index.json.ts mounts the agent index it names.
import type { APIRoute } from 'astro';
import { llmsTxtRoute } from '@spec-kitty/doc-toolkit/routes';
import contract from '../../dockitty-contract.json';

const title = 'Spec Kitty';
const description = 'Spec Kitty documentation: governed, spec-driven delivery from agreed intent to a verified result.';
const header = `# ${title}\n\n> ${description}\n\n`;
const generated = llmsTxtRoute({ title, description, indexBasename: contract.indexBasename });

export const GET: APIRoute = async (context) => {
  const response = await generated(context);
  const body = await response.text();
  // Fail the build rather than emit a file without the stance if doc-kitty's header shape moves.
  if (!body.startsWith(header)) {
    throw new Error('llms.txt: doc-kitty no longer opens llms.txt with the title and description header; re-check the stance insertion (#265).');
  }
  return new Response(`${header}${contract.llmsStance}\n${body.slice(header.length)}`, {
    headers: response.headers,
  });
};
