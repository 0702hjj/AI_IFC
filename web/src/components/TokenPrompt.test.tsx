// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import TokenPrompt from "./TokenPrompt";
import { notifyUnauthorized, getToken, clearToken, waitForToken } from "@/api/auth";

beforeEach(() => {
  cleanup();
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  clearToken();
});

describe("TokenPrompt（W-0010，401 token 输入 UI）", () => {
  it("初始不渲染；收到 unauthorized 事件后弹出输入框", () => {
    render(<TokenPrompt />);
    expect(screen.queryByRole("dialog")).toBeNull();
    act(() => notifyUnauthorized());
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("输入并保存：写入 localStorage 并关闭弹窗", () => {
    render(<TokenPrompt />);
    act(() => notifyUnauthorized());
    fireEvent.change(screen.getByLabelText("API token"), { target: { value: "s3cret" } });
    fireEvent.click(screen.getByText("保存"));
    expect(getToken()).toBe("s3cret");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("保存兑现 waitForToken（挂起的请求得以重试）", async () => {
    render(<TokenPrompt />);
    act(() => notifyUnauthorized());
    let resolved = false;
    const p = waitForToken().then(() => { resolved = true; });
    fireEvent.change(screen.getByLabelText("API token"), { target: { value: "s3cret" } });
    fireEvent.click(screen.getByText("保存"));
    await p;
    expect(resolved).toBe(true);
  });

  it("空 token 不允许保存", () => {
    render(<TokenPrompt />);
    act(() => notifyUnauthorized());
    const btn = screen.getByText("保存") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("API token"), { target: { value: "  " } });
    expect(btn.disabled).toBe(true);
  });

  it("Enter 键提交", () => {
    render(<TokenPrompt />);
    act(() => notifyUnauthorized());
    fireEvent.change(screen.getByLabelText("API token"), { target: { value: "s3cret" } });
    fireEvent.keyDown(screen.getByLabelText("API token"), { key: "Enter" });
    expect(getToken()).toBe("s3cret");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
