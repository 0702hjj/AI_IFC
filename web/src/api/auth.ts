// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// API token 存取与 401 通知（W-0010）。token 存 localStorage，键名 aiifc_token；
// 服务端默认关闭鉴权（VIEWER_API_TOKEN 为空），此时全部逻辑零行为变化。
export const TOKEN_KEY = "aiifc_token";

type Listener = () => void;

let listeners: Listener[] = [];
let waiters: Listener[] = [];

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  const pending = waiters;
  waiters = [];
  for (const resolve of pending) resolve();
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function onUnauthorized(fn: Listener): () => void {
  listeners.push(fn);
  return () => {
    listeners = listeners.filter((l) => l !== fn);
  };
}

export function notifyUnauthorized(): void {
  for (const fn of listeners) fn();
}

export function waitForToken(): Promise<void> {
  return new Promise((resolve) => waiters.push(resolve));
}
