// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// Node 22+ 内置实验性 localStorage 全局（无 --localstorage-file 时值为 undefined），
// 且当前 vitest/jsdom 组合下 window.localStorage 亦不可用。此处提供最小内存实现，
// 供测试与实现代码（如 API token 存取）使用；浏览器运行时不受影响。
if (!globalThis.localStorage) {
  const store = new Map<string, string>();
  const memoryStorage: Storage = {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => { store.set(k, String(v)); },
    removeItem: (k: string) => { store.delete(k); },
    clear: () => store.clear(),
    key: (i: number) => [...store.keys()][i] ?? null,
    get length() { return store.size; },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: memoryStorage,
    configurable: true,
    writable: true,
  });
}
