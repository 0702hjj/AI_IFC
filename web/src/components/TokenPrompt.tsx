// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

import { useEffect, useState } from "react";
import { onUnauthorized, setToken } from "@/api/auth";
import "./TokenPrompt.css";

export default function TokenPrompt() {
  const [visible, setVisible] = useState(false);
  const [value, setValue] = useState("");

  useEffect(() => onUnauthorized(() => setVisible(true)), []);

  if (!visible) return null;

  const save = () => {
    const token = value.trim();
    if (!token) return;
    setToken(token);
    setValue("");
    setVisible(false);
  };

  return (
    <div className="token-prompt-backdrop">
      <div className="token-prompt" role="dialog" aria-label="API token 输入">
        <h2>需要 API Token</h2>
        <p>服务端已开启鉴权（VIEWER_API_TOKEN）。请输入 token，保存后自动重试请求：</p>
        <label htmlFor="token-prompt-input">API token</label>
        <input
          id="token-prompt-input"
          type="password"
          value={value}
          autoFocus
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && save()}
        />
        <button onClick={save} disabled={!value.trim()}>保存</button>
      </div>
    </div>
  );
}
