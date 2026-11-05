import { DatabaseSync } from 'node:sqlite';
import { resolve } from 'node:path';

// Published quality scores (model cards, papers), copied from the private
// benchmark repo into site/data/. Read once at build time; nothing ships to
// the browser but the generated HTML.
const DB_PATH = resolve('data/benchmarks.sqlite');

/** How many benchmarks the models table shows: the ones with the most models. */
const TOP_COUNT = 5;

export interface Benchmark {
  id: string;
  name: string;
  category: string;
  description: string;
  higherIsBetter: boolean;
  unit: string;
}

export interface Score {
  benchmarkId: string;
  score: number;
  raw: string;
  /** split_or_subset, e.g. "reasoning-on" or "5-shot"; "" when none. */
  setting: string;
  sourceType: string;
  sourceUrl: string;
  extractedAt: string;
  notes: string;
}

export interface Model {
  id: string;
  slug: string;
  hfRepo: string;
  name: string;
  baseModel: string | null;
  author: string | null;
  pipelineTag: string | null;
  quantMethod: string | null;
  targetQuant: string | null;
  imatrix: boolean | null;
  params: number | null;
  tags: string[];
  meta: Record<string, unknown>;
  scores: Score[];
  /** False for a base model that only appears as a quant's base_model. */
  inDatabase: boolean;
}

/** A non-quantized model and the quantized builds made from it. */
export interface Group {
  slug: string;
  model: Model;
  quants: Model[];
}

export interface QualityData {
  benchmarks: Map<string, Benchmark>;
  top: Benchmark[];
  groups: Group[];
}

/** One table row: the scores a model has under one setting. */
export interface VariantRow {
  setting: string;
  cells: Map<string, Score>;
}

let cache: QualityData | undefined;

export function qualityData(): QualityData {
  cache ??= load();
  return cache;
}

/** URL segment for a model: "google/gemma-4-31B-it" → "google-gemma-4-31b-it". */
export function modelSlug(id: string): string {
  return id.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

// The extraction tool writes Python's None as the text 'None' in some columns.
function text(v: unknown): string | null {
  return v === null || v === undefined || v === 'None' || v === '' ? null : String(v);
}

function json<T>(v: unknown, fallback: T): T {
  try {
    return typeof v === 'string' ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

function isQuant(m: Model): boolean {
  return m.quantMethod !== null;
}

function load(): QualityData {
  const db = new DatabaseSync(DB_PATH, { readOnly: true });
  try {
    const benchmarks = new Map<string, Benchmark>();
    for (const r of db.prepare('SELECT * FROM benchmarks').all()) {
      benchmarks.set(String(r.id), {
        id: String(r.id),
        name: String(r.name),
        category: text(r.category) ?? 'General',
        description: text(r.description) ?? '',
        higherIsBetter: Number(r.higher_is_better) !== 0,
        unit: text(r.unit) ?? 'score',
      });
    }

    const models = new Map<string, Model>();
    for (const r of db.prepare('SELECT * FROM models').all()) {
      const id = String(r.id);
      models.set(id, {
        id,
        slug: modelSlug(id),
        hfRepo: String(r.hf_repo),
        name: String(r.name),
        baseModel: text(r.base_model),
        author: text(r.author),
        pipelineTag: text(r.pipeline_tag),
        quantMethod: text(r.quant_method),
        targetQuant: text(r.target_quant),
        imatrix: r.imatrix_calibrated === null ? null : Number(r.imatrix_calibrated) !== 0,
        params: r.params_billion === null ? null : Number(r.params_billion),
        tags: json<string[]>(r.tags, []),
        meta: json<Record<string, unknown>>(r.metadata_json, {}),
        scores: [],
        inDatabase: true,
      });
    }

    for (const r of db.prepare('SELECT * FROM scores WHERE score IS NOT NULL').all()) {
      models.get(String(r.model_id))?.scores.push({
        benchmarkId: String(r.benchmark_id),
        score: Number(r.score),
        raw: String(r.score_raw),
        setting: text(r.split_or_subset) ?? '',
        sourceType: text(r.source_type) ?? '',
        sourceUrl: text(r.source_url) ?? '',
        extractedAt: text(r.extracted_at) ?? '',
        notes: text(r.notes) ?? '',
      });
    }

    // Top benchmarks: the most distinct models with a score, ties by name.
    const coverage = new Map<string, Set<string>>();
    for (const m of models.values()) {
      for (const s of m.scores) {
        coverage.set(s.benchmarkId, (coverage.get(s.benchmarkId) ?? new Set()).add(m.id));
      }
    }
    const top = [...coverage]
      .map(([id, set]) => ({ b: benchmarks.get(id)!, n: set.size }))
      .filter((x) => x.b)
      .sort((a, b) => b.n - a.n || a.b.name.localeCompare(b.b.name))
      .slice(0, TOP_COUNT)
      .map((x) => x.b);

    // Every non-quantized model is a group; a quant joins the group of its
    // base_model. A quant whose base model has no row gets a placeholder parent.
    const groups = new Map<string, Group>();
    const addGroup = (model: Model) => groups.set(model.id, { slug: model.slug, model, quants: [] });
    for (const m of models.values()) if (!isQuant(m)) addGroup(m);
    for (const m of models.values()) {
      if (!isQuant(m)) continue;
      const parentId = m.baseModel ?? m.id;
      if (!groups.has(parentId)) {
        addGroup(
          parentId === m.id
            ? m
            : {
                id: parentId,
                slug: modelSlug(parentId),
                hfRepo: parentId,
                name: parentId.split('/').pop() ?? parentId,
                baseModel: null,
                author: parentId.includes('/') ? parentId.split('/')[0] : null,
                pipelineTag: null,
                quantMethod: null,
                targetQuant: null,
                imatrix: null,
                params: null,
                tags: [],
                meta: {},
                scores: [],
                inDatabase: false,
              },
        );
      }
      const g = groups.get(parentId)!;
      if (g.model !== m) g.quants.push(m);
    }

    const slugs = new Set<string>();
    for (const m of [...groups.values()].flatMap((g) => [g.model, ...g.quants])) {
      if (slugs.has(m.slug)) throw new Error(`Two models share the URL slug "${m.slug}"`);
      slugs.add(m.slug);
    }

    const byName = (a: Model, b: Model) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base' });
    const list = [...groups.values()].sort((a, b) => byName(a.model, b.model));
    for (const g of list) g.quants.sort((a, b) => quantLabel(a).localeCompare(quantLabel(b)));

    return { benchmarks, top, groups: list };
  } finally {
    db.close();
  }
}

/** Settings sorted with the plain (no setting) one first. */
function settingOrder(a: string, b: string): number {
  return (a === '' ? 0 : 1) - (b === '' ? 0 : 1) || a.localeCompare(b);
}

/**
 * One row per setting the model has among `benchmarkIds`; a model with no
 * score there still gets one empty row.
 */
export function variantRows(model: Model, benchmarkIds: string[]): VariantRow[] {
  const wanted = new Set(benchmarkIds);
  const rows = new Map<string, VariantRow>();
  for (const s of model.scores) {
    if (!wanted.has(s.benchmarkId)) continue;
    const row = rows.get(s.setting) ?? { setting: s.setting, cells: new Map() };
    row.cells.set(s.benchmarkId, s);
    rows.set(s.setting, row);
  }
  if (rows.size === 0) return [{ setting: '', cells: new Map() }];
  return [...rows.values()].sort((a, b) => settingOrder(a.setting, b.setting));
}

export interface MatrixRow {
  benchmark: Benchmark;
  setting: string;
  /** One entry per column model, in column order. */
  cells: (Score | undefined)[];
}

/**
 * Every (benchmark, setting) any of `columns` has a score for, grouped by
 * category; categories and benchmarks by name, the plain setting first.
 */
export function scoreMatrix(
  columns: Model[],
  benchmarks: Map<string, Benchmark>,
): { category: string; rows: MatrixRow[] }[] {
  const keyed = new Map<string, MatrixRow>();
  columns.forEach((m, i) => {
    for (const s of m.scores) {
      const benchmark = benchmarks.get(s.benchmarkId);
      if (!benchmark) continue;
      const key = `${s.benchmarkId}\u0000${s.setting}`;
      const row = keyed.get(key) ?? { benchmark, setting: s.setting, cells: columns.map(() => undefined) };
      row.cells[i] = s;
      keyed.set(key, row);
    }
  });
  const byCategory = new Map<string, MatrixRow[]>();
  for (const row of keyed.values()) {
    const c = row.benchmark.category;
    byCategory.set(c, [...(byCategory.get(c) ?? []), row]);
  }
  return [...byCategory]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([category, rows]) => ({
      category,
      rows: rows.sort(
        (a, b) => a.benchmark.name.localeCompare(b.benchmark.name) || settingOrder(a.setting, b.setting),
      ),
    }));
}

/** "Q4_K_M · unsloth" — how a quant is named next to its base model. */
export function quantLabel(m: Model): string {
  return [m.targetQuant ?? m.quantMethod ?? m.name, m.author].filter(Boolean).join(' · ');
}

export function formatScore(n: number): string {
  return String(Math.round(n * 100) / 100);
}
