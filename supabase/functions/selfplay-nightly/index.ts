// Supabase Edge Function: selfplay-nightly
// Runs head-to-head self-play evaluation rounds for all seeded skills.
// Triggered nightly at 2am UTC by pg_cron. No external imports — pure Deno fetch.

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANTHROPIC_KEY = Deno.env.get("ANTHROPIC_API_KEY")!;

const SKILLS = ["video-script", "ad-copy"];
const ROUNDS = 5;

const TASKS: Record<string, string[]> = {
  "video-script": [
    "Write a 60s video script for a SaaS launch targeting founders.",
    "Create a 30s social video for a fitness challenge.",
    "Write a 90s explainer about AI for small business.",
    "Create a 45s testimonial for a coffee brand.",
    "Write a 60s brand story for sustainable fashion.",
  ],
  "ad-copy": [
    "Write Google Ads for a B2B project management tool.",
    "Create Facebook ads for a meal delivery service.",
    "Write Instagram ads for a luxury skincare serum.",
    "Create LinkedIn ads for executive coaching.",
    "Write YouTube pre-roll for a finance app.",
  ],
};

async function sbGet(table: string, params: Record<string, string>) {
  const url = new URL(SUPABASE_URL + "/rest/v1/" + table);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const r = await fetch(url, {
    headers: { apikey: SUPABASE_KEY, Authorization: "Bearer " + SUPABASE_KEY },
  });
  return r.json();
}

async function sbPost(table: string, data: Record<string, unknown>) {
  const r = await fetch(SUPABASE_URL + "/rest/v1/" + table, {
    method: "POST",
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: "Bearer " + SUPABASE_KEY,
      "Content-Type": "application/json",
      Prefer: "return=representation",
    },
    body: JSON.stringify(data),
  });
  return r.json();
}

async function claude(system: string, prompt: string, temp = 0.7): Promise<string> {
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": ANTHROPIC_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 4096,
      temperature: temp,
      system: system || undefined,
      messages: [{ role: "user", content: prompt }],
    }),
  });
  const d = await r.json();
  return d.content?.[0]?.text || "";
}

Deno.serve(async () => {
  try {
    const results: Record<string, unknown[]> = {};

    for (const skill of SKILLS) {
      results[skill] = [];
      const candidates = await sbGet("prompt_population", {
        select: "*",
        skill_name: "eq." + skill,
        order: "score.desc",
        limit: "10",
      });
      if (!candidates || candidates.length < 2) continue;

      for (let round = 0; round < ROUNDS; round++) {
        const shuffled = [...candidates].sort(() => Math.random() - 0.5);
        const [a, b] = [shuffled[0], shuffled[1]];
        const stratA = `gen${a.generation}-${a.mutation_type || "seed"}`;
        const stratB = `gen${b.generation}-${b.mutation_type || "seed"}`;
        const tasks = TASKS[skill] || ["Create output for " + skill];
        const task = tasks[Math.floor(Math.random() * tasks.length)];

        const outA = await claude(a.prompt_text, task);
        const outB = await claude(b.prompt_text, task);

        const judgeText = await claude(
          "",
          `Compare outputs for ${skill}. Task: ${task}\nA (${stratA}):\n${outA.substring(0, 2000)}\nB (${stratB}):\n${outB.substring(0, 2000)}\n\nRespond ONLY JSON: {"winner":"a" or "b" or "tie","reasoning":"why","weakest_strategy":"name","improvement_suggestion":"tip"}`,
          0.2,
        );
        let judge: Record<string, unknown> = { winner: "tie", reasoning: "parse error" };
        try {
          const m = judgeText.match(/\{[\s\S]*?\}/);
          if (m) judge = JSON.parse(m[0]);
        } catch { /* keep default */ }

        await sbPost("selfplay_rounds", {
          skill_name: skill,
          round_number: round + 1,
          strategy_a: stratA,
          strategy_b: stratB,
          prompt_a_id: a.id,
          prompt_b_id: b.id,
          output_a: outA.substring(0, 5000),
          output_b: outB.substring(0, 5000),
          winner: judge.winner || "tie",
          judge_reasoning: judge.reasoning || "",
          weakest_strategy: judge.weakest_strategy || "",
          improvement_suggestion: judge.improvement_suggestion || "",
        });
        results[skill].push(judge);
      }

      await sbPost("reflection_events", {
        event_type: "self_play_result",
        source: "edge_selfplay_nightly",
        summary: `Nightly self-play ${skill}: ${results[skill].length} rounds`,
        skill_name: skill,
        severity: "info",
        details: { rounds: results[skill].length },
      });
    }

    return new Response(JSON.stringify({ success: true, results }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});
