// Supabase Edge Function: evolve-step
// MAP-Elites evolution step: select parent, mutate, evaluate, update archive.
// Triggered every 6 hours by pg_cron. No external imports — pure Deno fetch.

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANTHROPIC_KEY = Deno.env.get("ANTHROPIC_API_KEY")!;

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

Deno.serve(async (req) => {
  try {
    const body = await req.json().catch(() => ({}));
    const skill = body.skill || "video-script";
    const taskType = body.task_type || "brand_story";
    const numOffspring = body.num_offspring || 2;

    const tasks: Record<string, Record<string, string>> = {
      "video-script": {
        brand_story: "Write a 60-second brand story video for a sustainable fashion company.",
        product_launch: "Write a 60-second video script for a SaaS product launch targeting startup founders.",
        explainer: "Write a 90-second explainer video about how AI transforms small business operations.",
        testimonial: "Create a 45-second testimonial-style video script for a premium coffee brand.",
        social_short: "Create a 30-second social media video promoting a summer fitness challenge.",
      },
      "ad-copy": {
        google_ads: "Write Google Ads copy for a B2B project management tool targeting remote teams.",
        facebook_ads: "Create Facebook ad copy for a new meal delivery service.",
        instagram_ads: "Write Instagram ad copy for a luxury skincare brand launching a new serum.",
        linkedin_ads: "Create LinkedIn ad copy for an executive coaching program.",
        youtube_preroll: "Write YouTube pre-roll ad copy for a personal finance app targeting millennials.",
      },
    };
    const task = tasks[skill]?.[taskType] || "Create quality " + taskType + " output for " + skill;

    const candidates = await sbGet("prompt_population", {
      select: "*",
      skill_name: "eq." + skill,
      order: "score.desc",
      limit: "10",
    });
    if (!candidates || candidates.length === 0) {
      return new Response(JSON.stringify({ error: "no prompts" }), { status: 400 });
    }

    const parent = candidates[0];
    const strategies = ["guided", "random", "simplify", "expand", "rephrase"];
    const offspring: Record<string, unknown>[] = [];

    for (let i = 0; i < numOffspring; i++) {
      const strat = strategies[Math.floor(Math.random() * strategies.length)];
      const mutText = await claude(
        "",
        `Improve this prompt for ${skill} (${taskType}). Strategy: ${strat}. Current:\n${parent.prompt_text.substring(0, 1500)}\n\nRespond ONLY JSON: {"prompt_text":"new","mutation_description":"what"}`,
        0.8,
      );
      let mut = { prompt_text: parent.prompt_text, mutation_description: "failed" };
      try {
        const m = mutText.match(/\{[\s\S]*\}/);
        if (m) mut = JSON.parse(m[0]);
      } catch { /* keep default */ }
      if (mut.prompt_text === parent.prompt_text) continue;

      const output = await claude(mut.prompt_text, task);
      const judgeText = await claude(
        "",
        `Score output for ${skill}. Task: ${task}\nOutput: ${output.substring(0, 2000)}\n\nScore 0-1: relevance,quality,creativity,specificity,actionability. overall=quality*.3+relevance*.25+specificity*.2+creativity*.15+actionability*.1. ONLY JSON: {"overall":0.0,"reasoning":"brief"}`,
        0.2,
      );
      let scores: Record<string, unknown> = { overall: 0 };
      try {
        const m = judgeText.match(/\{[^{}]*\}/);
        if (m) scores = JSON.parse(m[0]);
      } catch { /* keep default */ }

      const newScore = Number(scores.overall) || 0;
      await sbPost("prompt_population", {
        skill_name: skill,
        task_type: taskType,
        tone: "default",
        model_target: "claude-sonnet-4-6",
        prompt_text: mut.prompt_text,
        score: newScore,
        score_breakdown: scores,
        generation: parent.generation + 1,
        parent_id: parent.id,
        mutation_type: strat,
        mutation_description: mut.mutation_description,
        is_elite: newScore > parent.score,
      });
      offspring.push({
        score: newScore,
        parent_score: parent.score,
        improved: newScore > parent.score,
        strategy: strat,
      });
    }

    await sbPost("reflection_events", {
      event_type: "skill_execution",
      source: "edge_evolve",
      summary: `Evolution ${skill}::${taskType} - ${offspring.length} offspring`,
      skill_name: skill,
      severity: "info",
      details: { offspring, parent_id: parent.id },
    });

    return new Response(JSON.stringify({ success: true, skill, taskType, offspring }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});
