import { spawn } from "child_process";
import path from "path";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const { model, openaiKey, langwatchKey, anthropicKey, googleKey } =
    await request.json();

  // Project root is one level up from web/
  const projectRoot = path.resolve(process.cwd(), "..");

  const env: Record<string, string> = {
    ...process.env,
    LANGWATCH_API_KEY: langwatchKey,
    OPENAI_API_KEY: openaiKey,
  } as Record<string, string>;

  if (anthropicKey) {
    env.ANTHROPIC_API_KEY = anthropicKey;
  }
  if (googleKey) {
    env.GOOGLE_API_KEY = googleKey;
  }

  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      const sendEvent = (data: object) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
      };

      sendEvent({ type: "output", line: `Starting tests with model: ${model}` });

      const pytest = spawn(
        "uv",
        ["run", "pytest", "-n", "auto", "--model", model, "oneday_evaluation.py"],
        {
          cwd: projectRoot,
          env,
        }
      );

      let outputBuffer = "";
      let resultsFound = false;

      const processOutput = (data: Buffer) => {
        const text = data.toString();
        outputBuffer += text;

        // Send each line as it comes
        const lines = text.split("\n");
        for (const line of lines) {
          if (line.trim()) {
            sendEvent({ type: "output", line });

            // Look for LangWatch URL
            if (line.includes("langwatch.ai") || line.includes("Follow it live")) {
              const urlMatch = line.match(/https?:\/\/[^\s]+/);
              if (urlMatch) {
                sendEvent({ type: "langwatch_url", url: urlMatch[0] });
              }
            }
          }
        }

        // Try to parse results from the summary block
        if (!resultsFound && outputBuffer.includes("TEST RESULTS SUMMARY")) {
          const results = parseResults(outputBuffer, model);
          if (results) {
            resultsFound = true;
            sendEvent({ type: "results", results });
          }
        }
      };

      pytest.stdout.on("data", processOutput);
      pytest.stderr.on("data", processOutput);

      pytest.on("close", (code) => {
        // Final attempt to parse results
        if (!resultsFound && outputBuffer.includes("TEST RESULTS SUMMARY")) {
          const results = parseResults(outputBuffer, model);
          if (results) {
            sendEvent({ type: "results", results });
          }
        }

        sendEvent({
          type: "output",
          line: `\nTests completed with exit code: ${code}`,
        });
        controller.close();
      });

      pytest.on("error", (err) => {
        sendEvent({ type: "output", line: `Error: ${err.message}` });
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}

function parseResults(output: string, model: string) {
  const results: {
    standard: { case: number; status: string }[];
    strict: { case: number; status: string }[];
    model: string;
    timestamp: string;
  } = {
    standard: [],
    strict: [],
    model,
    timestamp: "",
  };

  // Extract timestamp
  const timeMatch = output.match(/Time:\s*([^\s\n]+)/);
  if (timeMatch) {
    results.timestamp = timeMatch[1];
  }

  // Parse standard tests
  const standardMatch = output.match(
    /STANDARD TESTS[^\n]*\n[-\s]*\n([\s\S]*?)(?=\n\s*-{10,}|\n\s*Passed:)/
  );
  if (standardMatch) {
    const caseMatches = standardMatch[1].matchAll(/Case\s+(\d+):\s*(✓ PASS|✗ FAIL|○ SKIP)/g);
    for (const match of caseMatches) {
      results.standard.push({
        case: parseInt(match[1]),
        status: match[2].includes("PASS") ? "pass" : match[2].includes("FAIL") ? "fail" : "skip",
      });
    }
  }

  // Parse strict tests
  const strictMatch = output.match(
    /STRICT TESTS[^\n]*\n[-\s]*\n([\s\S]*?)(?=\n\s*-{10,}|\n\s*Passed:)/
  );
  if (strictMatch) {
    const caseMatches = strictMatch[1].matchAll(/Case\s+(\d+):\s*(✓ PASS|✗ FAIL|○ SKIP)/g);
    for (const match of caseMatches) {
      results.strict.push({
        case: parseInt(match[1]),
        status: match[2].includes("PASS") ? "pass" : match[2].includes("FAIL") ? "fail" : "skip",
      });
    }
  }

  if (results.standard.length === 0 && results.strict.length === 0) {
    return null;
  }

  return results;
}
