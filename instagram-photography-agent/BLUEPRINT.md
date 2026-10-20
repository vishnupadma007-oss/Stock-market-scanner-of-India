# Instagram Growth Agent for a Photographer / Videographer: Blueprint

Status: **planning only**. Nothing is built yet. Build starts once the credentials in §4 are available.

---

## 1. The one rule that decides everything: no password logins, no bots

The agent must **never** log in with your friend's Instagram username and password, and it must never
auto-follow, auto-like, mass-comment or cold-DM people. Tools that do this (instagrapi, Selenium,
"growth bots") break Instagram's Terms of Use. They get accounts shadow-banned, action-blocked or
permanently disabled, and for a photographer whose portfolio *is* the account, that is the worst outcome.

The agent uses only the **official Instagram Graph API** (Meta for Developers). It is slower to set up,
but it is the only approach that is safe to run for years.

| The official API **can** | The official API **cannot** |
|---|---|
| Publish photos, carousels (up to 10), Reels and Stories | Follow, unfollow or like other accounts |
| Schedule posts (the agent's own scheduler calls the API at the right time) | Send cold DMs to people who haven't messaged first |
| Read and reply to comments, hide spam | Read other people's private data |
| Reply to DMs within 24 h of the user's message (Messaging API) | Buy or fake engagement |
| Read insights: reach, saves, shares, profile visits, follower demographics | |
| Hashtag search (30 unique hashtags per 7 days) | |
| "Business Discovery": public stats of other business accounts (competitor research) | |

Growth comes from **better content, consistency, local SEO and fast replies to leads**, which is where an
AI agent helps most.

---

## 2. What the agent does (the "world-class" part)

Think of it as an AI social media manager plus a sales assistant, specialised in photography and videography.

### 2.1 Content intelligence
- **Photo/video understanding:** Claude's vision looks at each uploaded shot (lighting, mood, subject,
  genre: wedding, pre-wedding, portrait, product, event, travel) and picks the best frames from a shoot.
- **Captions in the brand voice:** hook in the first line, a story behind the shot, a call to action
  ("DM 'BOOK' for 2026 wedding dates"), an optional camera/lens/settings line (photographers love these),
  and the language mix the audience uses (e.g. English + Hindi/Telugu/Tamil).
- **Hashtag and keyword strategy:** a mix of niche, local and broad tags (e.g. `#hyderabadweddingphotographer`,
  `#candidphotography`, `#pre_wedding_shoot`), rotated, with tags that underperform retired automatically.
  Instagram search now ranks **keywords in captions and alt text** heavily, so the agent writes both.
- **Alt text and location tags** on every post for search and accessibility.

### 2.2 Content plan built on photography pillars
A weekly calendar the agent proposes and your friend approves:

| Pillar | Share | Example |
|---|---|---|
| Portfolio / hero shots | 35% | Best frames from latest wedding (carousel) |
| Behind the scenes (Reels) | 25% | Setting up lights, drone shot, "how I got this shot" |
| Before/after edits | 15% | Raw vs final colour grade, slider-style Reel |
| Client stories & testimonials | 15% | Couple's quote + 5 photos, tag the couple and vendors |
| Education / tips | 10% | "3 poses for couples who feel awkward" (highly saved and shared) |

Cadence guideline: 4–5 feed posts and 2–3 Reels a week, Stories daily. The agent learns the best
posting times from the account's own insights, not generic advice.

### 2.3 Engagement and lead capture (where the business money is)
- Replies to comments within minutes in your friend's voice; hides spam and scam comments
  ("promote it on @...").
- **DM inbox triage:** detects booking enquiries ("what are your wedding packages?"), answers FAQs
  (packages, availability, travel), collects date, city, event type and budget, then sends a summary to
  your friend on WhatsApp, Telegram or email and logs the lead in a sheet or CRM.
- Suggests **collaborations**: tag vendors (makeup artists, decorators, venues) and use the Collab-post
  feature so posts reach their audiences too.

### 2.4 Analytics and learning loop
- A weekly report: follower growth, reach, saves, shares, profile visits, website clicks, DMs and leads.
- Shows what worked (e.g. "Reels with before/after got 3.2× reach") and changes next week's plan to match.
- Competitor benchmarking via Business Discovery: 5–10 top photographers in the same city/niche.

### 2.5 Human in the loop (non-negotiable for v1)
Nothing is published and no DM with prices is sent without one-tap approval from your friend
(Telegram or WhatsApp button: ✅ Approve / ✏️ Edit / ❌ Skip). Once trust is built, low-risk actions like
replying "Thank you! ❤️" to compliments can be set to auto.

---

## 3. Architecture

```
        Friend uploads shoot ──► Google Drive / Dropbox folder (or Telegram bot)
                                         │
                                         ▼
 ┌─────────────────────── Agent service (Python, Claude Agent SDK / Claude API tool use) ──────────────┐
 │  Orchestrator (Claude)                                                                              │
 │   ├─ tool: analyse_media        (Claude vision: pick best frames, describe shot)                    │
 │   ├─ tool: write_caption        (brand voice, CTA, alt text, keywords)                              │
 │   ├─ tool: hashtag_research     (Graph API hashtag search + performance history)                    │
 │   ├─ tool: schedule_post        (writes to DB, scheduler publishes via Graph API)                   │
 │   ├─ tool: reply_comment / reply_dm   (Graph API + Messaging API, approval-gated)                   │
 │   ├─ tool: get_insights / competitor_stats                                                         │
 │   └─ tool: notify_owner         (Telegram/WhatsApp approval buttons, email reports)                 │
 └────────────────────────────────────────────────────────────────────────────────────────────────────┘
          │                    │                        │                          │
     Postgres DB         Media storage           Scheduler (cron)            Meta webhooks
  (posts, leads,     (public HTTPS URLs; the    (publish queue, token    (new comments / DMs arrive
   metrics, brand    Graph API pulls media      refresh, weekly report)   in real time)
   voice memory)     from a URL)
```

**Models:** a Sonnet-class Claude model for everyday captions, replies and triage (fast, cheap);
an Opus-class model for the weekly strategy review and monthly content plan. Use the latest model IDs
at build time.

**Brand-voice memory:** store 20–30 of your friend's best past captions plus a short style guide
(tone, emoji use, languages, words to avoid). Every generation is grounded in it, so posts sound like him,
not like generic AI.

**Agent skills:** directories like skills.sh list reusable agent skills (social media copywriting, SEO,
analytics). Useful ones get added as skills for the agent at build time. Each one is reviewed before
use, because a skill is code and instructions that run with the agent's credentials.

---

## 4. What to collect from your friend (checklist)

Never accept his Instagram password. Collect these instead:

1. **Instagram account switched to Professional** (Creator or Business), category "Photographer".
2. **A Facebook Page linked** to the Instagram account (needed for some Graph API features and the Messaging API).
3. **A Meta Developer app** (developers.facebook.com) with the *Instagram* product added. Your friend
   should be an admin of the app, or add you as a developer.
4. From that app:
   - App ID and App Secret
   - Instagram **User ID**
   - A **long-lived access token** (valid 60 days; the agent refreshes it automatically)
   - Permissions: `instagram_business_basic`, `instagram_business_content_publish`,
     `instagram_business_manage_comments`, `instagram_business_manage_messages`, `instagram_business_manage_insights`
     (exact names depend on whether the app uses "Instagram Login" or "Facebook Login"; we confirm at build time).
   - Because the app is only used on his **own** account, where he has a role on the app, it can usually run
     without Meta's full App Review. App Review is only needed if this later becomes a product for other photographers.
5. **Anthropic API key** (console.anthropic.com) for Claude, with a monthly spend limit set.
6. **Business info for the FAQ bot:** packages, starting prices, cities covered, booking process,
   website/WhatsApp link, 20–30 favourite past captions.
7. **Approval channel:** Telegram (easiest, free bot API) or WhatsApp Business.

Share secrets through a password manager share (Bitwarden or 1Password), never in chat or email.

---

## 5. Where to host it

The agent is a small always-on web service (for Meta webhooks) plus a scheduler and a database.

| Option | Good for | Approx. cost/month |
|---|---|---|
| **Railway** or **Render** (recommended to start) | Easiest: deploy from GitHub, built-in cron, managed Postgres, HTTPS webhooks out of the box | $5–20 |
| **Google Cloud Run + Cloud Scheduler + Cloud SQL/Supabase** | Scales to zero, cheap, very reliable, good if more clients come later | $5–25 |
| **AWS Lambda + EventBridge + S3** | If already on AWS | $5–20 |
| A VPS (Hetzner, DigitalOcean, Hostinger VPS) + Docker | Cheapest fixed cost, but you maintain the server | $5–8 |

Recommended stack for v1:
- **Compute:** Railway or Render (Python FastAPI service + cron job)
- **Database and file storage:** Supabase (Postgres + Storage, which gives the public media URLs the Graph API needs)
- **Secrets:** the host's environment variables / secret manager, never committed to GitHub
- **Monitoring:** host logs, plus a Telegram alert if a publish fails or the token is close to expiry

Expected running cost: about **$10–20 hosting + $10–40 Claude API usage per month** for one account
(depends on volume, mostly vision on photos). That is well below what a social media manager costs.

---

## 6. Build roadmap (once credentials arrive)

| Phase | Time | Delivers |
|---|---|---|
| 0. Setup | 1–2 days | Meta app, token flow, hosting, DB, Telegram approval bot |
| 1. Publisher | ~1 week | Upload shoot → AI picks frames → caption + hashtags + alt text → approve → scheduled post/carousel/Reel |
| 2. Engagement | ~1 week | Webhooks for comments and DMs, smart replies, booking-lead capture and owner alerts |
| 3. Analytics | ~1 week | Insights collection, weekly report, best-time learning, competitor benchmark |
| 4. Strategist | ongoing | Monthly content plan, trend/audio suggestions for Reels, A/B testing captions and hooks |

---

## 7. Safety and quality guardrails

- Rate limits respected (content publishing is capped at 100 API-published posts per 24 h; we aim for 1–2/day).
- Only original content from your friend; client photos posted only with client consent; tag clients and vendors.
- No fake reviews, no engagement pods, no bought followers.
- Price quotes and anything contractual always go to your friend, never auto-sent.
- Audit log of every action the agent takes; one-click "pause agent" switch.
- Token and API keys rotated if ever exposed.

## 8. KPIs to judge success (after 90 days)

- Reach and profile visits per week (trend)
- Saves + shares per post (Instagram's strongest quality signals)
- Follower growth **from the target city/niche** (not just total)
- Number of qualified booking enquiries per month and response time (target: under 5 minutes)
- Bookings that came from Instagram (the number that actually matters)
