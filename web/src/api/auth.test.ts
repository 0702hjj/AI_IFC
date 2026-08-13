// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, vi } from "vitest";
import { getToken, setToken, clearToken, onUnauthorized, notifyUnauthorized, waitForToken, TOKEN_KEY } from "./auth";

beforeEach(() => {
  localStorage.clear();
});

describe("api auth token store (W-0010)", () => {
  it("默认无 token", () => {
    expect(getToken()).toBe("");
  });

  it("setToken 持久化到 localStorage，getToken 读回", () => {
    setToken("s3cret");
    expect(localStorage.getItem(TOKEN_KEY)).toBe("s3cret");
    expect(getToken()).toBe("s3cret");
  });

  it("clearToken 清除", () => {
    setToken("s3cret");
    clearToken();
    expect(getToken()).toBe("");
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("notifyUnauthorized 触发订阅者，退订后不再触发", () => {
    const fn = vi.fn();
    const off = onUnauthorized(fn);
    notifyUnauthorized();
    expect(fn).toHaveBeenCalledTimes(1);
    off();
    notifyUnauthorized();
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("waitForToken 在 setToken 后兑现（401 重试挂起的基础）", async () => {
    let resolved = false;
    const p = waitForToken().then(() => { resolved = true; });
    await Promise.resolve();
    expect(resolved).toBe(false);
    setToken("s3cret");
    await p;
    expect(resolved).toBe(true);
  });
});
