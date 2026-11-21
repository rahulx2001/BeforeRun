# Hackathon timing and preparation boundary

Source: the Cerebras x Kimi K3.1 Pro FAQ pasted by the user in this conversation on
14 November 2026. Event page: https://luma.com/cerebras-kimi-hackathon.
FAQ short link: https://shorturl.at/csaGl.

## Exact rule supplied

> Must projects be built during the 24h, or is prepared scaffolding allowed?
>
> Pre-existing scaffolding, boilerplate code, and development frameworks are permitted.
> However, the core project and its functionality should be developed during the hackathon
> and must leverage Kimi K3.1 Pro running on Cerebras as a central component of the solution.

## Preparation used in this repository

The following are treated as scaffolding: project layout, dependency installation, generic
application startup, a health endpoint, static nonfunctional interface placeholders,
lint/compilation checks, environment-variable names, and planning documents.

This is our conservative interpretation of the quoted rule, not an additional organizer ruling.
The package investigation, version comparison, evidence checks, and live model integration
remain unimplemented until the event. A complete Gatekeeper fork built beforehand would not
satisfy the quoted core-development timing requirement.

## Dates in India

| Milestone | IST |
|---|---|
| Org ID capacity-request deadline | Saturday, 21 November 2026, 08:30 |
| Hackathon kickoff | Saturday, 21 November 2026, 23:30 |
| Submission deadline | Sunday, 22 November 2026, 23:30 |
| Preview access ends | Monday, 23 November 2026, 23:30 |

The pasted FAQ has typos in the day/date wording. The event listing specifies a 24-hour
event on 21–22 November. Preview access on the following day does not extend submission time.

## Model access

- Register at https://cloud.cerebras.ai and find the Organization ID.
- Submit it to https://forms.gle/qoG8ciAiogoSEVtM8 before the stated deadline.
- The supplied FAQ says approved preview access uses the standard Cerebras API and API key.
- The newer organizer FAQ supplied in this conversation identifies the trial model as
  `moonshotai-kimi-k3.1-pro-trial`. Verify approved access with an actual request.
- The submitted project must use the OpenClaw harness and Kimi on Cerebras centrally.
- The FAQ lists 100 requests/minute and 100,000 tokens/minute during the event, subject to
  demand. Do not assume uninterrupted capacity or enable thinking with undocumented settings.

## Submission requirements supplied

- Demo video: no longer than 60 seconds.
- Demonstrate how Cerebras inference speed improves the experience.
- A fair, measured GPU-provider comparison is recommended, not mandatory.
- Include project name, team members, a 2–4 sentence description, and demo video.
- A GitHub repository is recommended.
- The required official submission is an X demo post tagging @Cerebras and @Kimi_Moonshot
  with #KimiOnCerebras. Discord is the announcements/support location.
- Reddit is optional, with the “Kimi K3.1 Pro Hackathon” post flair.
- Paid promotion/amplification is excluded from the organic-reach judging criteria.
- Exclude credentials and personal information from recordings.

No account registration, capacity request, external repository publication, or submission
has been performed by this local preparation.

