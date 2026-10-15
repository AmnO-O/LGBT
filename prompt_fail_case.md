# LLM Rationale Prompt (for manual Gemini testing)

Reproduction of the exact prompt fed by `gen/llm_rationalize.py`.
Use this to test a specific failing case by pasting the two blocks below
into the Gemini API (System prompt + User prompt).

---

## 1. SYSTEM PROMPT (exact string from code, `RATIONALE_SYSTEM_PROMPT`)

```
You are a senior computational sociolinguist conducting pragmatic discourse analysis for YouTube video comments related to LGBTQ+ topics.

Analyze the given comment strictly grounded in the video's context (title + description).

CONTEXT-FIRST GROUNDING DIRECTIVES (CRITICAL):
1. MANDATORY: Read the video_title and video_description FIRST to identify:
   - What LGBTQ+ identities or individuals are featured in the video (e.g., lesbian 'l', gay 'g', bisexual 'b', transgender 't', queer 'q', intersex 'i', asexual 'a', non-binary 'nb', or general 'lgbtqia+').
   - Whether the comment refers to a specific person in the video ('individual') or the broader community ('group').
2. Evaluate if the comment's meaning depends on or attacks the subject shown in the video. (e.g. If the video is about a lesbian woman, a comment praising denial of communion or mocking her identity directly targets 'l'/'individual' or 'l'/'group').
3. NON-TARGET & BENIGN COMMENTS GUARD: If the comment is genuinely generic, off-topic, discussing an unrelated aspect of the video, or simply stating a neutral observation without attacking or undermining LGBTQ+ identities/persons, set target_identities: [] and target_scope: 'none' and target_reference: 'absent'. However, if the comment uses indirect criticism, moral judgment, sarcasm, slurs, or exclusionary rhetoric aimed at the LGBTQ+ topic or subjects, identify the corresponding target identity and scope.

CRITICAL INSTRUCTIONS TO PREVENT DATA LEAKAGE:
1. DO NOT mention classification label words ("no", "implicit", "explicit", "hate_speech", "neutral", "non-hate") in your 'why' or 'boundary' fields!
2. Provide an objective breakdown of the communication dynamics between the video context and comment.
3. Assess the linguistic axes:
   - direct_hostility: 'weak' (no slurs/threats), 'moderate', or 'strong' (overt slurs/violent threats)
   - indirect_subtext: 'weak' (literal/supportive), 'moderate', or 'strong' (sarcasm, dog-whistle, faux-concern, moral lecturing)
   - context_dependence: 'weak' (meaning is clear standalone), 'moderate', or 'strong' (meaning flips completely based on video title/topic)
   - counter_speech: 'weak' (not defending LGBTQ+), 'strong' (defending or supporting LGBTQ+ persons)
   - target_reference: 'present' (explicitly or implicitly mentions LGBTQ+ identities/groups), 'absent'
4. Write a concise factual explanation (1-2 sentences) of the subtext ('why') and why it might look benign or literal at first glance ('boundary').
5. In 'judge', determine the target identities and scope directly grounded in the video context before deciding the classification:
   - target_identities: list from ['l', 'g', 'b', 't', 'q', 'i', 'a', 'nb', 'lgbtqia+'] or [] if none.
   - target_scope: 'group' | 'individual' | 'none'.
   - stereotype: 0 or 1.
   - hate_speech: 'no' | 'yes_implicit' | 'yes_explicit'.

OUTPUT FORMAT:
Reply ONLY with a raw JSON object matching:
{
  "results": [
    {
      "id": "sample_id",
      "axes": {
        "direct_hostility": "weak|moderate|strong",
        "indirect_subtext": "weak|moderate|strong",
        "context_dependence": "weak|moderate|strong",
        "counter_speech": "weak|strong",
        "target_reference": "present|absent"
      },
      "why": "Objective factual breakdown of communicative tone and subtext, label-free.",
      "boundary": "Why this might look benign or literal at first glance and what subtle cue differentiates it, label-free.",
      "judge": {
        "stereotype": 0,
        "hate_speech": "no|yes_implicit|yes_explicit",
        "target_identities": ["l"],
        "target_scope": "individual|group|none",
        "confidence": 0.85
      }
    }
  ]
}
```

---

## 2. USER PROMPT (exact format from code — one failing case)

```
Analyze these 1 YouTube comments:
{
  "id": "training_EN_0005",
  "language": "English",
  "video_title": "Chechen leader Ramzan Kadyrov questioned on 'gay purge' - [CHANNEL]",
  "video_description": "Chechnya's leader Ramzan Kadyrov is questioned by the [CHANNEL]'s Sarah Rainsford on the region's human rights record. Human rights groups accuse Mr Kadyrov's security forces of grave abuses including the kidnap and torture of opponents and gay men.",
  "comment": "Of course west and US will hate him"
}
```

---

## 3. WHY THIS IS A FAIL CASE

**Expected (gold) label:** stereotype=`yes`, hate_speech=`yes_implicit`, target=`group_g`
**All models got it wrong** — `gemini-3.5-flash-lite` (batch=3/5), `gemini-3.6-flash` (factor), and `gpt-oss-120b` all judged:

- `hate_speech: "no"` (the dangerous failure: implicit hate read as benign)
- `target_identities: []` / `target_scope: 'none'`
- `target_reference: 'absent'`

**Why it should be hate:** the video title/description establish that the video's subject is the Chechen gay-purge + accusations of torturing gay men. The comment "Of course west and US will hate him" is **satirically sympathetic to Kadyrov ("US/west hates him") as an endorsement-of-attack**: it reads as approving the abuse of gay men under the guise of anti-Western commentary. This is a classic **implicit / mock-sympathy** case whose meaning *flips* based on the video context — exactly what axis `context_dependence` is for.

**The bug:** the model analyzes the *form* of the comment ("of course X will hate him" = innocuous statement) and misses the *context-anchored subtext* (endorsing a known gay-purger). It should be:
- `axes.direct_hostility: weak`, `indirect_subtext: strong`, `context_dependence: strong`, `counter_speech: weak`, `target_reference: present`
- `judge.hate_speech: "yes_implicit"`, `target_identities: ["g"]`, `target_scope: "group"`

Test this in Gemini manually (flash-lite and/or a stronger model), and compare whether the model catches the mock-sympathy subtext when `context_dependence` and `indirect_subtext` are emphasized.