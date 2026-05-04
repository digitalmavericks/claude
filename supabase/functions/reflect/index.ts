// Supabase Edge Function: reflect
// Weekly meta-cognitive reflection: analyzes events, proposes SOUL.md modifications.
// Triggered Monday 3am UTC by pg_cron. No external imports — pure Deno fetch.

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

async function claude(prompt: string, temp = 0.3): Promise<string> {
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
      messages: [{ role: "user", content: prompt }],
    }),
  });
  const d = await r.json();
  return d.content?.[0]?.text || "";
}

Deno.serve(async (req) => {
  try {
    const body = await req.json().catch(() => ({}));
    const _lookback = body.lookback_hours || 168;

    const events = await sbGet("reflection_events", {
      select: "*",
      order: "created_at.desc",
      limit: "100",
    });
    const elites = await sbGet("prompt_population", {
      select: "skill_name,task_type,score,generation",
      is_elite: "eq.true",
      order: "score.desc",
      limit: "20",
    });
    const selfplay = await sbGet("selfplay_rounds", {
      select: "skill_name,winner,weakest_strategy,improvement_suggestion",
      order: "created_at.desc",
      limit: "20",
    });

    if (!events || events.length === 0) {
      return new Response(
        JSON.stringify({ proposals: [], message: "No events" }),
        { headers: { "Content-Type": "application/json" } },
      );
    }

    const byType: Record<string, number> = {};
    for (const e of events) byType[e.event_type] = (byType[e.event_type] || 0) + 1;

    const prompt = `You are a meta-cognitive reflection agent for an AI content creation system.

Analyze recent activity and propose 0-3 targeted improvements to skill prompts or system configuration.

Events summary: ${JSON.stringify(byType)}

Recent events:
${JSON.stringify(events.slice(0, 20).map((e: Record<string, unknown>) => ({ type: e.event_type, summary: e.summary, severity: e.severity })), null, 2)}

Elite prompts: ${JSON.stringify(elites || [])}

Self-play results: ${JSON.stringify(selfplay || [])}

Rules:
- Each proposal must cite specific evidence from the data above
- Only propose changes for observed patterns, not hypotheticals
- Risk rating must be honest
- An empty array [] is valid if evidence is insufficient

Respond with ONLY a JSON array:
[{"proposal_type":"soul_edit"|"skill_edit"|"parameter_tune","target_file":"path","diff_text":"specific change","rationale":"why citing evidence","risk_rating":"LOW"|"MEDIUM"|"HIGH","supporting_evidence":["evidence1","evidence2"]}]`;

    const response = await claude(prompt);
    let proposals: Record<string, unknown>[] = [];
    try {
      const m = response.match(/\[[\s\S]*\]/);
      if (m) proposals = JSON.parse(m[0]);
    } catch { /* empty is fine */ }

    for (const p of proposals) {
      await sbPost("soul_modification_proposals", {
        proposal_type: p.proposal_type || "skill_edit",
        target_file: p.target_file || "unknown",
        diff_text: p.diff_text || "",
        rationale: p.rationale || "",
        risk_rating: p.risk_rating || "MEDIUM",
        supporting_evidence: p.supporting_evidence || [],
        status: "staged",
      });
    }

    await sbPost("reflection_events", {
      event_type: "quality_check",
      source: "edge_reflect",
      summary: `Reflection: ${events.length} events analyzed, ${proposals.length} proposals staged`,
      severity: "info",
      details: { events_analyzed: events.length, proposals_generated: proposals.length },
    });

    return new Response(
      JSON.stringify({ success: true, events_analyzed: events.length, proposals }),
      { headers: { "Content-Type": "application/json" } },
    );
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});
