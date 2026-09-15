/**
 * The only source of randomness in the TypeScript workspace.
 *
 * - `childSeed(root, namespace)`: SHA-256(`${root}:${namespace}`) -> first 4 bytes -> uint32.
 *   Every subsystem draws from its own named child; adding draws in one namespace never
 *   changes another's output.
 * - `Rng`: sfc32, a small 32-bit generator implemented identically in bench/rtlenv/rng.py.
 *   The streams are byte-identical across the two languages (tests/fixtures/rng-parity.json).
 *
 * No dependencies: SHA-256 and UTF-8 encoding are implemented here so the module runs the
 * same in the browser, Node and Vitest without an async crypto API.
 *
 * Math.random(), crypto.getRandomValues() and crypto.randomUUID() are forbidden everywhere
 * else in packages/ and sim/apps/Storefront (eslint.config.mjs).
 */

/** An unsigned 32-bit integer. */
export type Seed = number;

const TWO32 = 4294967296;

function assertSeed(seed: number, what = "seed"): void {
  if (!Number.isInteger(seed) || seed < 0 || seed >= TWO32) {
    throw new RangeError(`${what} must be an integer in [0, 2^32), got ${seed}`);
  }
}

// ----------------------------------------------------------------------------- UTF-8 + SHA-256

function utf8(text: string): Uint8Array {
  const out: number[] = [];
  for (let i = 0; i < text.length; i++) {
    let cp = text.charCodeAt(i);
    if (cp >= 0xd800 && cp <= 0xdbff && i + 1 < text.length) {
      const lo = text.charCodeAt(i + 1);
      if (lo >= 0xdc00 && lo <= 0xdfff) {
        cp = 0x10000 + ((cp - 0xd800) << 10) + (lo - 0xdc00);
        i++;
      }
    }
    if (cp < 0x80) out.push(cp);
    else if (cp < 0x800) out.push(0xc0 | (cp >> 6), 0x80 | (cp & 0x3f));
    else if (cp < 0x10000) out.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    else
      out.push(
        0xf0 | (cp >> 18),
        0x80 | ((cp >> 12) & 0x3f),
        0x80 | ((cp >> 6) & 0x3f),
        0x80 | (cp & 0x3f),
      );
  }
  return Uint8Array.from(out);
}

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

function rotr(x: number, n: number): number {
  return (x >>> n) | (x << (32 - n));
}

/** SHA-256 of the UTF-8 encoding of `text`, as 32 bytes. */
export function sha256Bytes(text: string): Uint8Array {
  const msg = utf8(text);
  const bitLen = msg.length * 8;
  const padded = new Uint8Array(((msg.length + 9 + 63) >> 6) << 6);
  padded.set(msg);
  padded[msg.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 4, bitLen >>> 0);
  view.setUint32(padded.length - 8, Math.floor(bitLen / TWO32));
  const h = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]);
  const w = new Uint32Array(64);
  for (let off = 0; off < padded.length; off += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(off + i * 4);
    for (let i = 16; i < 64; i++) {
      const w15 = w[i - 15] as number;
      const w2 = w[i - 2] as number;
      const s0 = rotr(w15, 7) ^ rotr(w15, 18) ^ (w15 >>> 3);
      const s1 = rotr(w2, 17) ^ rotr(w2, 19) ^ (w2 >>> 10);
      w[i] = ((w[i - 16] as number) + s0 + (w[i - 7] as number) + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, hh] = h as unknown as [number, number, number, number, number, number, number, number];
    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (hh + S1 + ch + (K[i] as number) + (w[i] as number)) >>> 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) >>> 0;
      hh = g;
      g = f;
      f = e;
      e = (d + t1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (t1 + t2) >>> 0;
    }
    h[0] = ((h[0] as number) + a) >>> 0;
    h[1] = ((h[1] as number) + b) >>> 0;
    h[2] = ((h[2] as number) + c) >>> 0;
    h[3] = ((h[3] as number) + d) >>> 0;
    h[4] = ((h[4] as number) + e) >>> 0;
    h[5] = ((h[5] as number) + f) >>> 0;
    h[6] = ((h[6] as number) + g) >>> 0;
    h[7] = ((h[7] as number) + hh) >>> 0;
  }
  const out = new Uint8Array(32);
  const ov = new DataView(out.buffer);
  for (let i = 0; i < 8; i++) ov.setUint32(i * 4, h[i] as number);
  return out;
}

/** SHA-256 of the UTF-8 encoding of `text`, lowercase hex. */
export function sha256Hex(text: string): string {
  return Array.from(sha256Bytes(text), (b) => b.toString(16).padStart(2, "0")).join("");
}

function firstWord(bytes: Uint8Array): number {
  return new DataView(bytes.buffer, bytes.byteOffset, 4).getUint32(0);
}

// ----------------------------------------------------------------------------- seeds

/** Named child seed: SHA-256(`${root}:${namespace}`) -> first 4 bytes big-endian -> uint32. */
export function childSeed(root: Seed, namespace: string): Seed {
  assertSeed(root, "root seed");
  return firstWord(sha256Bytes(`${root}:${namespace}`));
}

/** A stable uint32 seed for a string such as a run id. */
export function seedFromString(text: string): Seed {
  return firstWord(sha256Bytes(text));
}

// ----------------------------------------------------------------------------- generator

/**
 * sfc32 ("Small Fast Counting", 32-bit). State comes from SHA-256 of the decimal seed,
 * followed by 12 discarded outputs. Identical to rtlenv.rng.Rng in Python.
 */
export class Rng {
  readonly seed: Seed;
  readonly namespace: string;
  private a: number;
  private b: number;
  private c: number;
  private d: number;

  constructor(seed: Seed, namespace = "root") {
    assertSeed(seed);
    this.seed = seed;
    this.namespace = namespace;
    const s = sha256Bytes(String(seed));
    const v = new DataView(s.buffer);
    this.a = v.getUint32(0) | 0;
    this.b = v.getUint32(4) | 0;
    this.c = v.getUint32(8) | 0;
    this.d = v.getUint32(12) | 0;
    for (let i = 0; i < 12; i++) this.next32();
  }

  /** Next value as an unsigned 32-bit integer. */
  next32(): number {
    const t = (((this.a + this.b) | 0) + this.d) | 0;
    this.d = (this.d + 1) | 0;
    this.a = this.b ^ (this.b >>> 9);
    this.b = (this.c + (this.c << 3)) | 0;
    this.c = (this.c << 21) | (this.c >>> 11);
    this.c = (this.c + t) | 0;
    return t >>> 0;
  }

  /** Uniform in [0, 1) with 32 bits of resolution; exactly next32() / 2^32. */
  float(): number {
    return this.next32() / TWO32;
  }

  /** Uniform integer in [min, maxExclusive), unbiased by rejection sampling. */
  int(min: number, maxExclusive: number): number {
    if (!Number.isInteger(min) || !Number.isInteger(maxExclusive)) {
      throw new RangeError("int() bounds must be integers");
    }
    const range = maxExclusive - min;
    if (range < 1 || range > TWO32) throw new RangeError(`int() range must be in [1, 2^32], got ${range}`);
    const bound = TWO32 - (TWO32 % range);
    let u = this.next32();
    while (u >= bound) u = this.next32();
    return min + (u % range);
  }

  bool(p = 0.5): boolean {
    return this.float() < p;
  }

  pick<T>(items: readonly T[]): T {
    if (items.length === 0) throw new RangeError("pick() of an empty list");
    return items[this.int(0, items.length)] as T;
  }

  /** Weighted choice; weights are summed in order so both languages see the same doubles. */
  weighted<T>(items: readonly T[], weights: readonly number[]): T {
    if (items.length === 0 || items.length !== weights.length) {
      throw new RangeError("weighted() needs equal, non-empty items and weights");
    }
    let total = 0;
    for (const w of weights) {
      if (!(w >= 0)) throw new RangeError("weights must be non-negative numbers");
      total += w;
    }
    if (total <= 0) throw new RangeError("weights must not all be zero");
    const x = this.float() * total;
    let acc = 0;
    for (let i = 0; i < items.length; i++) {
      acc += weights[i] as number;
      if (x < acc) return items[i] as T;
    }
    return items[items.length - 1] as T;
  }

  /** Fisher-Yates on a copy; the input is never mutated. */
  shuffle<T>(items: readonly T[]): T[] {
    const out = items.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = this.int(0, i + 1);
      const tmp = out[i] as T;
      out[i] = out[j] as T;
      out[j] = tmp;
    }
    return out;
  }

  /** A generator for a named sub-system, independent of every other namespace. */
  child(namespace: string): Rng {
    return new Rng(childSeed(this.seed, namespace), `${this.namespace}/${namespace}`);
  }
}
