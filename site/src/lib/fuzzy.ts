// Search matching for the filter boxes: ignores case and punctuation
// ("gemma4" finds "gemma-4"), and a word of 4+ letters also matches with one
// typo ("qewn", "gema"). Runs in the browser.

export interface Text {
  flat: string;
  words: string[];
}

export const flat = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '');
const words = (s: string) => s.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
export const text = (s: string): Text => ({ flat: flat(s), words: words(s) });

/** Optimal string alignment distance, at most 1 (an edit or a swap). */
function oneEdit(a: string, b: string): boolean {
  if (Math.abs(a.length - b.length) > 1) return false;
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...new Array<number>(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
      }
    }
  }
  return d[a.length][b.length] <= 1;
}

/** A typed word (already `flat`) matches a text when it is part of it, or one typo away from a word in it (or that word's start). */
export function matches(term: string, t: Text): boolean {
  if (t.flat.includes(term)) return true;
  if (term.length < 4) return false;
  return t.words.some((w) => oneEdit(term, w) || (w.length > term.length && oneEdit(term, w.slice(0, term.length))));
}
