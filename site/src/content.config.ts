// The docs collection reads ../docs (ADR 2026-10-31-1 D-1). The loader takes the folder
// exclusion and index basenames from the integration in astro.config.mjs; pass neither here.
import { defineCollection } from 'astro:content';
import { docKittyDocsLoader, docKittyDocsSchema } from '@spec-kitty/doc-toolkit/schema';

export const collections = {
  docs: defineCollection({ loader: docKittyDocsLoader({ base: '../docs' }), schema: docKittyDocsSchema() }),
};
