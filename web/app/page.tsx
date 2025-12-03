"use client";

import { useState, useRef } from "react";

type TestResult = {
  case: number;
  status: "pass" | "fail" | "skip";
};

type Results = {
  standard: TestResult[];
  strict: TestResult[];
  model: string;
  timestamp: string;
};

export default function Home() {
  const [model, setModel] = useState("gpt-5-mini");
  const [openaiKey, setOpenaiKey] = useState("");
  const [langwatchKey, setLangwatchKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [googleKey, setGoogleKey] = useState("");
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState<string[]>([]);
  const [results, setResults] = useState<Results | null>(null);
  const [langwatchUrl, setLangwatchUrl] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const runTests = async () => {
    setRunning(true);
    setOutput([]);
    setResults(null);
    setLangwatchUrl(null);

    abortRef.current = new AbortController();

    try {
      const response = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          openaiKey,
          langwatchKey,
          anthropicKey,
          googleKey,
        }),
        signal: abortRef.current.signal,
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) return;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n").filter(Boolean);

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.slice(6));

            if (data.type === "output") {
              setOutput((prev) => [...prev, data.line]);
            } else if (data.type === "results") {
              setResults(data.results);
            } else if (data.type === "langwatch_url") {
              setLangwatchUrl(data.url);
            }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        setOutput((prev) => [...prev, `Error: ${err.message}`]);
      }
    } finally {
      setRunning(false);
    }
  };

  const stopTests = () => {
    abortRef.current?.abort();
  };

  const needsAnthropicKey = model === "claude-4.5-sonnet";
  const needsGoogleKey = model === "gemini-2.5-flash";

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>OneDay Test Runner</h1>
      <p style={{ color: "#666", marginTop: 0 }}>
        Run agent simulation tests locally
      </p>

      <div
        style={{
          backgroundColor: "white",
          padding: "1.5rem",
          borderRadius: "8px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
          marginBottom: "1rem",
        }}
      >
        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500 }}>
            Model
          </label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={running}
            style={{
              width: "100%",
              padding: "0.5rem",
              borderRadius: "4px",
              border: "1px solid #ddd",
              fontSize: "1rem",
            }}
          >
            <option value="gpt-5-mini">GPT-5 Mini (OpenAI)</option>
            <option value="claude-4.5-sonnet">Claude 4.5 Sonnet (Anthropic)</option>
            <option value="gemini-2.5-flash">Gemini 2.5 Flash (Google)</option>
          </select>
        </div>

        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500 }}>
            LangWatch API Key
          </label>
          <input
            type="password"
            value={langwatchKey}
            onChange={(e) => setLangwatchKey(e.target.value)}
            disabled={running}
            placeholder="lw_..."
            style={{
              width: "100%",
              padding: "0.5rem",
              borderRadius: "4px",
              border: "1px solid #ddd",
              fontSize: "1rem",
              boxSizing: "border-box",
            }}
          />
        </div>

        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500 }}>
            OpenAI API Key {!needsAnthropicKey && !needsGoogleKey && "(required)"}
          </label>
          <input
            type="password"
            value={openaiKey}
            onChange={(e) => setOpenaiKey(e.target.value)}
            disabled={running}
            placeholder="sk-..."
            style={{
              width: "100%",
              padding: "0.5rem",
              borderRadius: "4px",
              border: "1px solid #ddd",
              fontSize: "1rem",
              boxSizing: "border-box",
            }}
          />
        </div>

        {needsAnthropicKey && (
          <div style={{ marginBottom: "1rem" }}>
            <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500 }}>
              Anthropic API Key (required)
            </label>
            <input
              type="password"
              value={anthropicKey}
              onChange={(e) => setAnthropicKey(e.target.value)}
              disabled={running}
              placeholder="sk-ant-..."
              style={{
                width: "100%",
                padding: "0.5rem",
                borderRadius: "4px",
                border: "1px solid #ddd",
                fontSize: "1rem",
                boxSizing: "border-box",
              }}
            />
          </div>
        )}

        {needsGoogleKey && (
          <div style={{ marginBottom: "1rem" }}>
            <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500 }}>
              Google AI API Key (required)
            </label>
            <input
              type="password"
              value={googleKey}
              onChange={(e) => setGoogleKey(e.target.value)}
              disabled={running}
              placeholder="AI..."
              style={{
                width: "100%",
                padding: "0.5rem",
                borderRadius: "4px",
                border: "1px solid #ddd",
                fontSize: "1rem",
                boxSizing: "border-box",
              }}
            />
          </div>
        )}

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            onClick={runTests}
            disabled={running || !langwatchKey}
            style={{
              padding: "0.75rem 1.5rem",
              backgroundColor: running ? "#ccc" : "#0070f3",
              color: "white",
              border: "none",
              borderRadius: "4px",
              fontSize: "1rem",
              cursor: running ? "not-allowed" : "pointer",
            }}
          >
            {running ? "Running..." : "Run Tests"}
          </button>

          {running && (
            <button
              onClick={stopTests}
              style={{
                padding: "0.75rem 1.5rem",
                backgroundColor: "#dc3545",
                color: "white",
                border: "none",
                borderRadius: "4px",
                fontSize: "1rem",
                cursor: "pointer",
              }}
            >
              Stop
            </button>
          )}
        </div>
      </div>

      {langwatchUrl && (
        <div
          style={{
            backgroundColor: "#e7f3ff",
            padding: "1rem",
            borderRadius: "8px",
            marginBottom: "1rem",
          }}
        >
          <a
            href={langwatchUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "#0070f3" }}
          >
            View detailed results in LangWatch Dashboard
          </a>
        </div>
      )}

      {results && (
        <div
          style={{
            backgroundColor: "white",
            padding: "1.5rem",
            borderRadius: "8px",
            boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
            marginBottom: "1rem",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Results</h2>
          <p style={{ color: "#666" }}>
            Model: {results.model} | Time: {results.timestamp}
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div>
              <h3>Standard Tests</h3>
              <div style={{ fontFamily: "monospace", fontSize: "0.9rem" }}>
                {results.standard.map((r) => (
                  <div key={r.case} style={{ padding: "0.25rem 0" }}>
                    Case {r.case}: {r.status === "pass" ? "✓ PASS" : r.status === "fail" ? "✗ FAIL" : "○ SKIP"}
                  </div>
                ))}
              </div>
              <p style={{ color: "#666", fontSize: "0.9rem" }}>
                Passed: {results.standard.filter((r) => r.status === "pass").length} /{" "}
                {results.standard.length}
              </p>
            </div>

            <div>
              <h3>Strict Tests</h3>
              <div style={{ fontFamily: "monospace", fontSize: "0.9rem" }}>
                {results.strict.map((r) => (
                  <div key={r.case} style={{ padding: "0.25rem 0" }}>
                    Case {r.case}: {r.status === "pass" ? "✓ PASS" : r.status === "fail" ? "✗ FAIL" : "○ SKIP"}
                  </div>
                ))}
              </div>
              <p style={{ color: "#666", fontSize: "0.9rem" }}>
                Passed: {results.strict.filter((r) => r.status === "pass").length} /{" "}
                {results.strict.length}
              </p>
            </div>
          </div>
        </div>
      )}

      {output.length > 0 && (
        <div
          style={{
            backgroundColor: "#1e1e1e",
            color: "#d4d4d4",
            padding: "1rem",
            borderRadius: "8px",
            fontFamily: "monospace",
            fontSize: "0.85rem",
            maxHeight: "400px",
            overflow: "auto",
          }}
        >
          {output.map((line, i) => (
            <div key={i} style={{ whiteSpace: "pre-wrap" }}>
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
