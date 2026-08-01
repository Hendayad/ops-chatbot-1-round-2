# At-Risk Nudge Delivery — Channel Proposal

## Current state

`app/atrisk/nudges.py` already builds and deduplicates the nudge message correctly, but delivery defaults to `NoOpNotificationSender` — nothing actually reaches a learner yet. This is intentional (the docstring flags it as a placeholder), and matches an open question already listed in `docs/prd.md`: *"Which delivery channels (in-app only vs. email/other) are in scope for reminders at launch?"*

## Recommendation: deliver nudges inside the learner's existing chat

Our PRD's persona table already says learners get "24/7 chat support, reminders, supportive nudges" through chat — there's no separate learner-facing frontend anywhere in this repo. The dashboard we're building (F3.3) is explicitly scoped to program leads, not learners. So the chat is the only learner surface that already exists, and the cheapest one to use.

**How:** add a `LearnerChatChannel` following the same pattern as the existing `OpsSlackChannel` (`app/notifications/channels.py`). It inserts the nudge as a normal assistant message into the learner's existing `Session`/`Thread`. Swap it in as the `sender` argument to `send_at_risk_nudges()`, replacing the no-op.

**Bonus:** this also gives a natural, no-new-UI answer for F2.6 (notification preferences/opt-out, still unbuilt) — a learner just tells the assistant "stop sending me reminders" in chat, checked against a small preference table before sending.

## Channel comparison

| Channel | Build cost | Ongoing cost | Reaches inactive learners? | New tools needed |
|---|---|---|---|---|
| **In-chat (recommended)** | Low — reuses existing chat | Free | No — only seen if they open the chat | None |
| Email | Medium | Low at small scale, grows with cohort size | Yes — lands in inbox even if inactive | Email provider (SendGrid/SES) |
| SMS | Medium | Ongoing per-message cost | Yes — highest visibility | SMS provider (Twilio) + compliance |
| Push notification | High | Free after setup | Yes | Requires a mobile app (don't have one) |

## Honest tradeoff

In-chat only reaches a learner when they open the chat. The learners this feature targets are the ones showing inactivity — so there's real risk the group most in need of the nudge is also least likely to see it. Email or push is specifically good at pulling someone back in from outside the app; in-chat can't do that.

## Proposed path

Ship in-chat first — it's free, fast, and needs no new infrastructure. Revisit adding email later, specifically for the inactivity signal, only if data shows inactive learners are missing nudges. Avoids building a general multi-channel system upfront for all four risk reasons before there's evidence it's needed.
