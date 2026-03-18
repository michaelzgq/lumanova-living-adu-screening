# First-Wave Launch Plan

## Goal

Use the live screening app to capture the first batch of real leads from Chinese-speaking homeowners, agents, and referrals.

Do not optimize for profit yet.
Optimize for:

- real submissions
- usable contact details
- source quality
- actual follow-up conversations

## Live Entry Links

Replace the base URL only if the app URL changes.

- Main public screen:
  - `https://lumanova-living-adu-screening-fzcdyrfu9pakal7eelwwzj.streamlit.app/?view=public`
- Garage conversion:
  - `https://lumanova-living-adu-screening-fzcdyrfu9pakal7eelwwzj.streamlit.app/?view=public&entry=garage`
- Detached ADU:
  - `https://lumanova-living-adu-screening-fzcdyrfu9pakal7eelwwzj.streamlit.app/?view=public&entry=adu`
- Legalization / existing issue:
  - `https://lumanova-living-adu-screening-fzcdyrfu9pakal7eelwwzj.streamlit.app/?view=public&entry=legalization`

## Source-Tagged Links

Use tracked links from the admin `Launch Kit`, or manually append:

- `source`
- `utm_source`
- `utm_medium`
- `utm_campaign`

Examples:

- WeChat garage post:
  - `https://lumanova-living-adu-screening-fzcdyrfu9pakal7eelwwzj.streamlit.app/?view=public&entry=garage&source=wechat_garage&utm_source=wechat&utm_medium=social&utm_campaign=wave1_garage`
- Agent ADU referral:
  - `https://lumanova-living-adu-screening-fzcdyrfu9pakal7eelwwzj.streamlit.app/?view=public&entry=adu&source=agent_adu&utm_source=agent&utm_medium=referral&utm_campaign=wave1_adu`
- Legalization help post:
  - `https://lumanova-living-adu-screening-fzcdyrfu9pakal7eelwwzj.streamlit.app/?view=public&entry=legalization&source=wechat_legalization&utm_source=wechat&utm_medium=social&utm_campaign=wave1_legalization`

## Priority Channels

### 1. WeChat

Use for:

- homeowner friends and family
- SGV homeowner groups
- Chinese local business circles
- property owner chats

Best entry:

- `garage`
- `legalization`

### 2. Agent / partner forwarding

Use for:

- real estate agents
- mortgage brokers
- permit/design contacts
- project referral partners

Best entry:

- `adu`
- `garage`

### 3. Private 1:1 outreach

Use for:

- warm referrals
- homeowners already asking questions
- old conversations that never converted

Best entry:

- whichever path matches the customer best

## Posting Rules

- Do not send one generic link to everyone.
- Match the link to the customer problem.
- Use one CTA only:
  - `Free property pre-screen`
- Do not lead with design or construction pricing.
- Lead with:
  - can this property likely move forward
  - what may block it
  - whether deeper review is worth doing

## WeChat Copy

### Garage conversion

If you own a house in LA / SGV and want to know whether your garage conversion looks straightforward or likely has blockers, use this free pre-screen first.

This is for early route checking before you spend on plans or construction.

`[garage link]`

### Detached ADU

If you are thinking about adding a detached ADU or backyard unit, use this free pre-screen first to see whether the property looks closer to a standard path or needs deeper review.

`[adu link]`

### Legalization / existing issue

If the property already has old work, unclear permit history, correction comments, or an existing unit issue, use this screen first before assuming it can move like a standard project.

`[legalization link]`

## Agent / Partner Copy

Use this short intake before anyone quotes a path. It helps sort standard ADU cases from blocker-heavy or legalization cases, and gives us cleaner follow-up before deeper review.

`[matched link]`

## Daily Review Routine

### Morning

- open admin
- review `Priority review queue`
- check new Google Sheets rows
- contact `new` and `needs_review` leads first

### Midday

- update `stage`
- set `assigned_to`
- fill `next_action`
- mark obvious bad-fit or duplicate leads

### Evening

- count submissions by source
- check which entry type produced the best leads
- note which questions confused users

## KPIs For Wave 1

Track only these:

- total submissions
- contactable leads
- `% with usable email / phone / wechat`
- `A / C / B` mix
- top source
- number of real conversations started

## Wave-1 Success Threshold

Call the first wave promising if:

- 10+ real leads arrive
- 5+ are contactable
- 2+ turn into serious conversations

## Wave-1 Failure Signals

Rework the front end if:

- many people open but almost nobody submits
- many submits have fake or unusable contact info
- one source brings volume but no real projects
- users clearly do not understand which entry to choose

## What To Improve After The First 10 Leads

- simplify any confusing question
- rewrite the entry title that performs worst
- split garage vs legalization more clearly if users mix them up
- improve the first human follow-up script
