import { NextResponse } from "next/server";
import { runAssistant, runLLMAssistant } from "@/lib/assistant";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const { filled, asking, utterance } = (body ?? {}) as {
    filled?: Record<string, string>;
    asking?: string;
    utterance?: string;
  };
  if (!utterance || typeof utterance !== "string") {
    return NextResponse.json({ error: "Missing 'utterance'" }, { status: 400 });
  }
  const reqBody = { filled: filled ?? {}, asking, utterance };
  const llm = await runLLMAssistant(reqBody, process.env.OPENAI_API_KEY);
  const result = llm ?? runAssistant(reqBody);
  return NextResponse.json(result);
}
