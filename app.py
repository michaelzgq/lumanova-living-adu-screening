from __future__ import annotations

import hmac
import re
from urllib.parse import urlencode, urlparse
from pathlib import Path
from typing import Any, Optional

import streamlit as st

from app.config import debug_setting_state, get_bool_setting, get_setting
from app.copilot import generate_copilot_brief
from app.delivery import (
    apply_delivery_result,
    deliver_lead,
    webhook_configured,
    webhook_target_label,
)
from app.knowledge import get_playbook_rows, load_markdown, match_policy_notes
from app.models import (
    LeadRecord,
    ScreeningAnswers,
    backfill_lead_defaults,
    lead_needs_attention,
    lead_priority_key,
    suggested_next_action_for_lead,
    utc_now_iso,
)
from app.remote_leads import fetch_remote_leads, merge_local_and_remote_leads, remote_lead_source_configured
from app.rules import (
    JURISDICTION_LABELS,
    PROJECT_LABELS,
    STRUCTURE_LABELS,
    compute_screening,
    suggest_jurisdiction,
    suggest_project_type,
)
from app.source_context import resolve_source_context
from app.storage import LeadRepository, export_leads_csv


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "leads.json"
PLAYBOOK_PATH = BASE_DIR / "knowledge" / "jurisdiction_playbook.yaml"
NOTES_PATH = BASE_DIR / "knowledge" / "policy_notes.yaml"
WORKFLOW_PATH = BASE_DIR / "knowledge" / "notebooklm_workflow.md"
BUSINESS_LOOP_PATH = BASE_DIR / "knowledge" / "business_closure_loop.md"
GOOGLE_SHEETS_SETUP_PATH = BASE_DIR / "knowledge" / "google_sheets_setup.md"


QUESTION_FLOW: list[dict[str, Any]] = [
    {
        "id": "property_address",
        "prompt": "What is the property address?",
        "help": "Use the real street address if possible. The first version uses this to suggest the likely jurisdiction.",
        "type": "text",
        "placeholder": "1234 Example Ave, Pasadena, CA 91101",
    },
    {
        "id": "brief_goal",
        "prompt": "What are you trying to do?",
        "help": "Describe the goal in one sentence. Example: I want to convert my detached garage into a rental ADU.",
        "type": "textarea",
        "placeholder": "I want to convert my detached garage into a legal rental unit.",
    },
    {
        "id": "jurisdiction",
        "prompt": "Which jurisdiction governs this property?",
        "help": "The app will suggest one from the address. You can override it before continuing.",
        "type": "select",
        "options": list(JURISDICTION_LABELS.items()),
    },
    {
        "id": "owner_on_title",
        "prompt": "Are you the property owner on title?",
        "type": "radio",
        "options": ["Yes", "No", "Not sure"],
    },
    {
        "id": "project_type",
        "prompt": "Which path sounds closest to your project?",
        "help": "This is a working classification only. It can change after records review.",
        "type": "select",
        "options": list(PROJECT_LABELS.items()),
    },
    {
        "id": "structure_type",
        "prompt": "What structure are you talking about?",
        "type": "select",
        "options": list(STRUCTURE_LABELS.items()),
    },
    {
        "id": "hillside",
        "prompt": "Is the property in a hillside area or special slope condition?",
        "type": "radio",
        "options": ["Yes", "No", "Not sure"],
    },
    {
        "id": "basement",
        "prompt": "Is any part of the intended unit in a basement or below grade?",
        "type": "radio",
        "options": ["Yes", "No", "Not sure"],
    },
    {
        "id": "addition_without_permit",
        "prompt": "Has any addition been built without permits?",
        "type": "radio",
        "options": ["Yes", "No", "Not sure"],
    },
    {
        "id": "unpermitted_work",
        "prompt": "Is there any existing unpermitted construction on site?",
        "type": "radio",
        "options": ["Yes", "No", "Not sure"],
    },
    {
        "id": "prior_violation",
        "prompt": "Have you received a correction notice, violation, or code enforcement letter?",
        "type": "radio",
        "options": ["Yes", "No", "Not sure"],
    },
    {
        "id": "prior_plans",
        "prompt": "Do you have an old plan set, permit number, or active correction comments already?",
        "type": "radio",
        "options": ["Yes", "No", "Not sure"],
    },
    {
        "id": "separate_utility_request",
        "prompt": "Do you want a separate address or separate utilities?",
        "type": "radio",
        "options": ["Yes", "No", "Not sure"],
    },
]

LANGUAGE_OPTIONS = {
    "en": "English",
    "zh": "中文",
}

CONTACT_PREFERENCE_OPTIONS = ["Phone", "Email", "Text", "WeChat", "No preference"]
STAGE_OPTIONS = [
    "new",
    "needs_review",
    "contacted",
    "qualified",
    "screening_booked",
    "proposal_sent",
    "closed_won",
    "closed_lost",
    "nurture",
    "archived",
]
DISPOSITION_OPTIONS = [
    "",
    "duplicate",
    "spam",
    "no_response",
    "bad_fit",
    "budget_mismatch",
    "data_incomplete",
    "future_nurture",
    "high_risk_external",
]

PUBLIC_ENTRY_VARIANTS: dict[str, dict[str, Any]] = {
    "default": {
        "project_type": "",
        "selector_title": {
            "en": "General ADU / property check",
            "zh": "通用 ADU / 物业预筛",
        },
        "selector_desc": {
            "en": "Use this if you are still not sure which path fits best.",
            "zh": "如果你还不确定具体属于哪条路径，可以先用这个。",
        },
        "hero_eyebrow": {
            "en": "Los Angeles • Garage conversion • Detached ADU • Legalization review",
            "zh": "洛杉矶 • 车库改造 • 独立 ADU • 合法化评估",
        },
        "hero_title": {
            "en": "Lumanova Living ADU Pre-Screen",
            "zh": "Lumanova Living ADU 预筛",
        },
        "hero_body": {
            "en": "Use this guided screen to get an early read on whether your property looks relatively straightforward, needs deeper review, or may involve existing issues before you spend on design or construction.",
            "zh": "用这个引导式预筛，先判断你的物业看起来是相对直接、需要更深审核，还是涉及现有问题，再决定是否值得继续花设计费或施工费。",
        },
        "intro_title": {
            "en": "Start with a fast property screen, not a construction quote.",
            "zh": "先做物业预筛，不要先拿装修报价。",
        },
        "intro_body": {
            "en": "This free intake is built for owners and serious decision-makers who want an early read on likely complexity, possible review factors, and next steps before paying for plans or fielding multiple contractor calls.",
            "zh": "这个免费入口适合真正想先判断项目复杂度、潜在问题和下一步动作的业主或决策人，而不是泛泛咨询装修的人。",
        },
        "sidebar_title": {
            "en": "What we'll ask",
            "zh": "我们会先问什么",
        },
        "sidebar_points": {
            "en": [
                "The property address and likely city or county path",
                "Whether this sounds more like a new ADU, garage conversion, or legalization issue",
                "Whether there are known complications like hillside, basement space, or prior corrections",
                "How the team should contact you if review makes sense",
            ],
            "zh": [
                "物业地址，以及大概率属于哪个 city / county 路径",
                "更像新建 ADU、车库改造，还是合法化问题",
                "是否有坡地、地下室、整改记录这类已知复杂因素",
                "如果值得继续审核，团队该如何联系你",
            ],
        },
    },
    "garage": {
        "project_type": "garage_conversion",
        "selector_title": {
            "en": "Garage conversion",
            "zh": "车库改造",
        },
        "selector_desc": {
            "en": "For attached or detached garage conversion questions.",
            "zh": "适合独立或连体车库改造问题。",
        },
        "hero_eyebrow": {
            "en": "Garage conversion • Los Angeles / SGV • Early property check",
            "zh": "车库改造 • 洛杉矶 / SGV • 早期物业判断",
        },
        "hero_title": {
            "en": "Check your garage conversion path before paying for plans.",
            "zh": "先判断车库改造路径，再决定是否花设计费。",
        },
        "hero_body": {
            "en": "This version is tuned for owners asking whether an existing garage looks closer to a workable path, a blocker-heavy review, or an existing-condition problem.",
            "zh": "这个版本更适合想先判断现有车库看起来更像可推进路径、卡点较多案件，还是现有问题案件的业主。",
        },
        "intro_title": {
            "en": "Garage conversion is not always a standard path.",
            "zh": "车库改造并不一定都是标准路径。",
        },
        "intro_body": {
            "en": "Use this short screen to surface common garage-conversion review factors before you spend on plans, permits, or contractor calls.",
            "zh": "先用这个短预筛把车库改造里常见的审核因素挑出来，再决定是否值得继续花计划、permit 或 contractor 沟通成本。",
        },
        "sidebar_title": {
            "en": "Best for garage-conversion owners",
            "zh": "最适合车库改造业主",
        },
        "sidebar_points": {
            "en": [
                "Detached or attached garage conversion questions",
                "Owners worried about old additions, corrections, or unclear records",
                "Projects where the first question is feasibility, not design style",
                "Early review before chasing quotes",
            ],
            "zh": [
                "想做独立或连体车库改造的业主",
                "担心旧加建、整改或 records 不清楚的人",
                "第一步更关心 feasibility，而不是设计风格的人",
                "想先筛路径、再问报价的人",
            ],
        },
    },
    "adu": {
        "project_type": "detached_adu",
        "selector_title": {
            "en": "Detached ADU",
            "zh": "独立 ADU",
        },
        "selector_desc": {
            "en": "For new detached ADU and backyard unit exploration.",
            "zh": "适合新建独立 ADU 或 backyard unit 预筛。",
        },
        "hero_eyebrow": {
            "en": "Detached ADU • Los Angeles / SGV • Early feasibility screen",
            "zh": "独立 ADU • 洛杉矶 / SGV • 早期 feasibility 预筛",
        },
        "hero_title": {
            "en": "Get an early ADU property read before you move into design.",
            "zh": "先判断 ADU 物业情况，再决定是否进入设计。",
        },
        "hero_body": {
            "en": "This page is built for owners exploring a new detached ADU and wanting an early read on complexity, routing, and likely next review steps.",
            "zh": "这个页面适合正在评估新建独立 ADU、想先判断复杂度、路径和下一步审核动作的业主。",
        },
        "intro_title": {
            "en": "Start with feasibility, not floor-plan shopping.",
            "zh": "先看 feasibility，不要先纠结户型图。",
        },
        "intro_body": {
            "en": "Use this intake to see whether your property looks relatively clean or whether city routing and existing conditions may need more review first.",
            "zh": "先用这个入口判断你的物业看起来是否相对干净，还是 city 路由和现有条件本身就需要先做更深核对。",
        },
        "sidebar_title": {
            "en": "Best for detached ADU owners",
            "zh": "最适合独立 ADU 业主",
        },
        "sidebar_points": {
            "en": [
                "Owners asking if their lot looks worth evaluating for a detached ADU",
                "Early feasibility questions before design work",
                "Properties with uncertain city path or possible blocker signals",
                "Real projects, not generic remodel research",
            ],
            "zh": [
                "想先判断自家 lot 是否值得评估独立 ADU 的业主",
                "在设计前先看 feasibility 的项目",
                "city 路径不清楚或可能带 blocker 的物业",
                "真实项目，不是泛装修研究",
            ],
        },
    },
    "legalization": {
        "project_type": "unpermitted_unit",
        "selector_title": {
            "en": "Legalization / existing issue",
            "zh": "合法化 / 现有问题",
        },
        "selector_desc": {
            "en": "For correction notices, old work, or unclear permit history.",
            "zh": "适合整改通知、旧施工或 permit history 不清楚的情况。",
        },
        "hero_eyebrow": {
            "en": "Existing issues • Legalization review • Los Angeles / SGV",
            "zh": "现有问题 • 合法化核对 • 洛杉矶 / SGV",
        },
        "hero_title": {
            "en": "Check whether this looks like a legalization or rescue review.",
            "zh": "先判断这更像合法化 review，还是救援型案件。",
        },
        "hero_body": {
            "en": "This page is for owners dealing with an existing unit, unpermitted work, or correction history who need an early read before anyone promises a path.",
            "zh": "这个页面适合已经有现有单元、无 permit 施工或整改历史的业主，在任何人承诺路径前先做早期判断。",
        },
        "intro_title": {
            "en": "Do not treat existing issues like a clean new project.",
            "zh": "现有问题案件，不要当成干净的新项目来处理。",
        },
        "intro_body": {
            "en": "Use this screen if you are trying to understand whether old work, corrections, or unclear records may require a rescue-style review first.",
            "zh": "如果你要先判断旧施工、整改记录或 records 不清楚是否会让项目先走救援型 review，这个入口最合适。",
        },
        "sidebar_title": {
            "en": "Best for existing-condition cases",
            "zh": "最适合现有问题案件",
        },
        "sidebar_points": {
            "en": [
                "Existing unit or garage apartment already on site",
                "Prior correction notices, violations, or unclear permit history",
                "Owners trying to understand whether legalization may be possible",
                "Cases that should not be sold like a standard fast-track path",
            ],
            "zh": [
                "现场已经有现有单元或 garage apartment",
                "有整改、violation 或不清楚的 permit history",
                "想先判断是否还有合法化可能性的业主",
                "不适合按标准快车道去销售的案件",
            ],
        },
    },
}

TEXT: dict[str, dict[str, str]] = {
    "en": {
        "language_label": "Language",
        "hero_admin_title": "Lumanova Living ADU Screening Console",
        "hero_admin_body": "Use this admin workspace to review public intake, triage leads into the right next step, and keep your playbook, workflow, and routing logic aligned.",
        "public_main_title": "Lumanova Living Property Screen",
        "public_main_subtitle": "Choose the closest project type, then complete the intake so the team can review the property before anyone quotes a path.",
        "entry_selector_label": "Choose the closest project type",
        "public_value_title": "What this free screen helps with",
        "public_value_1_title": "Early path reading",
        "public_value_1_body": "See whether your property looks relatively straightforward, likely needs more review, or may involve existing issues.",
        "public_value_2_title": "Blocker visibility",
        "public_value_2_body": "Surface common review factors like hillside conditions, basement space, prior corrections, or unpermitted work before you spend on design.",
        "public_value_3_title": "Cleaner follow-up",
        "public_value_3_body": "Give the review team enough context to decide whether to call, what to review first, and whether deeper review makes sense.",
        "public_process_title": "How it works",
        "public_process_1": "Answer a short intake about the address, project type, and any known project complications.",
        "public_process_2": "The system produces an early project read so the review team can see whether it looks standard, complex, or rescue-oriented.",
        "public_process_3": "A team member can review the submission, check records, and decide whether to contact you about next steps.",
        "public_fit_title": "Best fit for this screen",
        "public_fit_1": "Homeowners exploring a detached ADU or garage conversion",
        "public_fit_2": "Owners dealing with corrections, permit friction, or unclear records",
        "public_fit_3": "Serious project inquiries that need an early route, not a generic remodel quote",
        "public_screen_time": "Typical completion time: about 60 to 90 seconds.",
        "start_over": "Start over",
        "reset_screening": "Reset current screening",
        "load_example": "Load example scenario",
        "prelim_notice": "This tool gives a preliminary routing result only. It is not a legal opinion, permit approval, or final design strategy.",
        "public_notice": "This online screen gives a preliminary routing result only. A team member still needs to review records and project details.",
        "tab_prescreen": "Pre-Screen",
        "tab_inbox": "Lead Inbox",
        "tab_loop": "Knowledge Loop",
        "view_public": "Public screening view",
        "view_admin": "Admin view",
        "public_thank_you_title": "Thanks, your request has been captured.",
        "public_thank_you_body": "This is still a preliminary screen. A team member should review the address, records, and project details before promising any path.",
        "public_expected_contact": "Expected follow-up",
        "public_expected_contact_body": "If this is a real project inquiry, someone should contact you using your preferred method after review.",
        "public_next_step_title": "What happens next",
        "public_safe_result": "Initial project reading",
        "public_review_level": "Review level",
        "public_likely_next_step": "Likely next step",
        "public_possible_review_factors": "Possible review factors",
        "public_route_standard": "Looks closer to a standard ADU or garage-conversion review",
        "public_route_blocker": "Looks like this property may need a deeper review before anyone quotes a path",
        "public_route_rescue": "Looks like an existing-condition or legalization issue that may need a more careful review",
        "public_review_standard": "Standard review",
        "public_review_elevated": "Additional review",
        "public_review_priority": "Priority manual review",
        "public_service_standard": "Property record and path review",
        "public_service_blocker": "Blocker and permit-history review",
        "public_service_rescue": "Deeper records and existing-conditions review",
        "external_sync": "External sync",
        "external_sync_status": "External sync status",
        "external_sync_at": "External sync time",
        "external_sync_error": "External sync error",
        "webhook_ready": "Webhook is configured.",
        "webhook_missing": "Webhook is not configured yet. Leads are still saved locally only.",
        "admin_password": "Admin password",
        "unlock_admin": "Unlock admin view",
        "admin_locked": "Admin view is locked.",
        "admin_access_note": "Enter the admin password to view leads, edit intake data, and manage follow-up.",
        "admin_password_invalid": "Admin password is incorrect.",
        "logout_admin": "Log out",
        "admin_unprotected": "Admin view is currently not password-protected.",
        "back": "Back",
        "continue": "Continue",
        "field_required": "This field is required.",
        "progress": "Progress: {answered}/{total} screening fields completed",
        "captured_so_far": "Captured So Far",
        "your_intake_summary": "Your intake summary",
        "no_answers": "No answers captured yet.",
        "preliminary_result": "Preliminary Screening Result",
        "recommended_path": "Recommended Path",
        "risk_tier": "Risk Tier",
        "primary_service": "Primary Service",
        "current_reading": "Current Reading",
        "jurisdiction": "Jurisdiction",
        "project": "Project",
        "main_blockers": "Main blocker signals",
        "no_blockers": "No blocker signals were triggered in the first-pass intake.",
        "next_steps": "Next Steps",
        "why_routed": "Why the app routed this way",
        "knowledge_notes": "Knowledge Notes Used In This Result",
        "source": "Source",
        "lead_capture": "Lead Capture",
        "lead_capture_caption": "Leave your details so a team member can review this screen and decide whether follow-up or deeper screening makes sense.",
        "contact_preference": "Preferred follow-up method",
        "best_contact_time": "Best time to reach you",
        "best_contact_placeholder": "Example: Weekdays after 4pm",
        "consent_to_contact": "I agree to be contacted about this inquiry.",
        "consent_required": "Consent to contact is required before submitting the lead.",
        "full_name": "Full name",
        "email": "Email",
        "phone": "Phone",
        "wechat_id": "WeChat ID",
        "save_lead": "Submit pre-screen + show next step",
        "lead_required": "Full name is required.",
        "lead_contact_required": "Add at least one contact method: email, phone, or WeChat.",
        "email_invalid": "Enter a valid email address.",
        "email_required_for_preference": "Email is required when email is the preferred follow-up method.",
        "phone_invalid": "Enter a valid phone number.",
        "phone_required_for_preference": "Phone is required when phone or text is the preferred follow-up method.",
        "wechat_required_for_preference": "WeChat ID is required when WeChat is the preferred follow-up method.",
        "leads": "Leads",
        "funnel_snapshot": "Funnel snapshot",
        "source_overview": "Source overview",
        "top_sources": "Top sources",
        "download_csv": "Download leads CSV",
        "no_leads": "No leads saved yet. Complete the intake flow once to populate the inbox.",
        "select_lead": "Select lead",
        "search_leads": "Search leads",
        "search_placeholder": "Search by name, email, phone, or address",
        "filter_stage": "Filter by stage",
        "filter_path": "Filter by path",
        "filter_source": "Filter by source",
        "all_stages": "All stages",
        "all_paths": "All paths",
        "all_sources": "All sources",
        "priority_queue": "Priority review queue",
        "queue_empty": "No leads currently match the priority queue.",
        "lead_stage": "Lead stage",
        "assigned_to": "Assigned to",
        "next_action": "Next action",
        "last_updated": "Last updated",
        "source_info": "Source tracking",
        "source_tag": "Source tag",
        "utm_source": "UTM source",
        "utm_medium": "UTM medium",
        "utm_campaign": "UTM campaign",
        "internal_notes": "Internal notes",
        "disposition_reason": "Disposition reason",
        "save_lead_updates": "Save lead updates",
        "lead_updated": "Lead updated.",
        "edit_lead_intake": "Edit customer intake",
        "save_customer_changes": "Save customer changes",
        "customer_data_updated": "Customer intake updated and result recalculated.",
        "delete_lead": "Delete lead",
        "delete_warning": "This removes the saved lead from local storage.",
        "delete_confirm": "I understand this lead will be deleted.",
        "delete_lead_button": "Delete this lead",
        "lead_deleted": "Lead deleted.",
        "delete_sync_failed": "Delete was blocked because external sync failed. Fix the webhook or disable it before deleting.",
        "duplicate_lead_updated": "An existing lead matched this contact. The saved record was updated instead of creating a duplicate.",
        "saved_at": "Saved at",
        "name": "Name",
        "address": "Address",
        "goal": "Goal",
        "path": "Path",
        "recommended_service_short": "Recommended Service",
        "not_provided": "Not provided",
        "none": "None",
        "what_we_ask": "What we'll ask",
        "public_sidebar_caption": "This is an early route check, not a final permit or legal opinion.",
        "early_signal": "Early property signal",
        "early_signal_caption": "This updates as the intake becomes clearer. Final review still depends on records and manual follow-up.",
        "needs_reply_today": "Needs reply >24h",
        "quick_actions": "Quick actions",
        "mark_contacted": "Mark contacted",
        "mark_qualified": "Mark qualified",
        "move_to_nurture": "Move to nurture",
        "mark_closed_lost": "Mark closed lost",
        "quick_action_saved": "Quick action applied.",
        "ai_copilot": "AI Copilot",
        "ai_priority": "Priority read",
        "ai_lead_score": "Lead score",
        "ai_lead_temperature": "Lead temperature",
        "ai_recommended_owner": "Recommended owner",
        "ai_summary": "Lead summary",
        "ai_score_reasons": "Why the score looks like this",
        "ai_call_objectives": "Call objectives",
        "ai_missing_information": "Missing or unclear information",
        "ai_document_requests": "Suggested document requests",
        "ai_crm_handoff_note": "CRM / handoff note",
        "ai_outreach_draft": "Draft outreach message",
        "business_loop_doc": "Business closure loop",
        "workflow_doc": "NotebookLM workflow",
        "stage_guide": "Stage guide",
        "google_sheets_setup": "Google Sheets setup",
        "stage_guide_note": "Use these definitions so the team applies stage updates consistently.",
        "lead_blockers": "Blocker signals",
        "lead_rationale": "Why this lead was routed here",
        "jurisdiction_seeds": "Jurisdiction Playbook Seeds",
        "best_fit_pages": "Best-fit front-door pages",
        "workflow_note": "NotebookLM notes stay internal. The front-end intake uses cleaned rules from your playbook.",
        "tab_launch": "Launch Kit",
        "launch_kit_title": "Campaign launch kit",
        "launch_kit_caption": "Generate shareable public links for WeChat, agents, social posts, or website embeds.",
        "public_base_url": "Public base URL",
        "campaign_source": "Source tag",
        "campaign_medium": "UTM medium",
        "campaign_name": "Campaign name",
        "embed_mode": "Embed / widget mode",
        "channel_templates": "Generated links",
        "default_path": "General property screen",
        "share_copy": "Suggested share copy",
        "wechat_share_copy": "WeChat share copy",
        "agent_share_copy": "Agent / partner share copy",
        "social_share_copy": "Short social copy",
    },
    "zh": {
        "language_label": "语言",
        "hero_admin_title": "Lumanova Living ADU 管理后台",
        "hero_admin_body": "这个后台用于查看前台线索、做人工分诊、维护团队流程，并保持 playbook、路由逻辑和跟进动作一致。",
        "public_main_title": "Lumanova Living 物业预筛",
        "public_main_subtitle": "先选择最接近的项目类型，再填写预筛，让团队在任何人报价前先判断这个物业该怎么走。",
        "entry_selector_label": "选择最接近的项目类型",
        "public_value_title": "这个免费预筛能帮你什么",
        "public_value_1_title": "先看路径",
        "public_value_1_body": "先判断你的物业看起来是相对直接、需要更深审核，还是已经涉及现有问题。",
        "public_value_2_title": "先看潜在障碍",
        "public_value_2_body": "在你花设计费之前，先暴露坡地、地下室、旧整改记录或无 permit 施工这类常见审核因素。",
        "public_value_3_title": "让后续联系更有效",
        "public_value_3_body": "提前把关键背景给到审核团队，让他们知道该联系、先看什么，以及是否需要更深审核。",
        "public_process_title": "使用流程",
        "public_process_1": "先填写地址、项目类型和你已知的项目情况。",
        "public_process_2": "系统会先给出一个早期判断，帮助团队分辨项目更像标准、复杂或救援场景。",
        "public_process_3": "团队再决定是否联系你、核对 records，或建议进入下一步服务。",
        "public_fit_title": "最适合使用这个预筛的人",
        "public_fit_1": "正在评估独立 ADU 或车库改造的业主",
        "public_fit_2": "已经碰到审批摩擦、整改记录或 records 不清楚的业主",
        "public_fit_3": "想先判断路径，而不是先拿泛装修报价的真实项目咨询",
        "public_screen_time": "通常 60 到 90 秒可以填完。",
        "start_over": "重新开始",
        "reset_screening": "重置当前预筛",
        "load_example": "加载示例数据",
        "prelim_notice": "这个工具只给初步分流结果，不构成法律意见、permit 审批结论或最终设计策略。",
        "public_notice": "这个在线预筛只给初步分流结果。最终仍需要团队人工核对地址、records 和项目细节。",
        "tab_prescreen": "预筛",
        "tab_inbox": "线索列表",
        "tab_loop": "知识库闭环",
        "view_public": "客户预筛视图",
        "view_admin": "后台管理视图",
        "public_thank_you_title": "感谢提交，你的咨询已经记录。",
        "public_thank_you_body": "这仍然只是初步预筛。真正承诺路径之前，团队还需要核对地址、records 和项目细节。",
        "public_expected_contact": "后续联系",
        "public_expected_contact_body": "如果这是一个真实项目咨询，团队在审核后会按你偏好的方式联系你。",
        "public_next_step_title": "接下来会发生什么",
        "public_safe_result": "当前初步判断",
        "public_review_level": "审核级别",
        "public_likely_next_step": "可能的下一步",
        "public_possible_review_factors": "可能需要额外核对的因素",
        "public_route_standard": "目前看更接近标准 ADU / 车库改造审核",
        "public_route_blocker": "这个物业看起来可能需要先做更深的核对，不能直接判断路径",
        "public_route_rescue": "这个情况更像现有问题或合法化案件，通常需要更谨慎的人工审核",
        "public_review_standard": "标准审核",
        "public_review_elevated": "需要额外审核",
        "public_review_priority": "优先人工审核",
        "public_service_standard": "产权记录与路径核对",
        "public_service_blocker": "卡点与 permit 历史核对",
        "public_service_rescue": "深度 records 与现状核对",
        "external_sync": "外部同步",
        "external_sync_status": "外部同步状态",
        "external_sync_at": "外部同步时间",
        "external_sync_error": "外部同步错误",
        "webhook_ready": "Webhook 已配置。",
        "webhook_missing": "Webhook 还没有配置，线索目前只保存在本地。",
        "admin_password": "后台密码",
        "unlock_admin": "进入后台",
        "admin_locked": "后台视图已锁定。",
        "admin_access_note": "输入后台密码后，才能查看 leads、修改客户输入和管理跟进。",
        "admin_password_invalid": "后台密码不正确。",
        "logout_admin": "退出后台",
        "admin_unprotected": "后台当前没有设置密码保护。",
        "back": "返回上一步",
        "continue": "继续",
        "field_required": "这个字段必填。",
        "progress": "进度：已完成 {answered}/{total} 个预筛字段",
        "captured_so_far": "当前已采集信息",
        "your_intake_summary": "你填写的信息",
        "no_answers": "暂时还没有采集到答案。",
        "preliminary_result": "初步预筛结果",
        "recommended_path": "建议路径",
        "risk_tier": "风险等级",
        "primary_service": "建议服务",
        "current_reading": "当前判断",
        "jurisdiction": "管辖机构",
        "project": "项目类型",
        "main_blockers": "主要阻碍信号",
        "no_blockers": "第一轮预筛里暂时没有触发明显 blocker。",
        "next_steps": "下一步",
        "why_routed": "为什么系统这样分流",
        "knowledge_notes": "本结果引用的知识笔记",
        "source": "来源",
        "lead_capture": "线索信息",
        "lead_capture_caption": "留下联系方式后，团队可以审核这次预筛，并决定是否联系你或建议更深的 screening。",
        "contact_preference": "希望我们如何联系你",
        "best_contact_time": "方便联系的时间",
        "best_contact_placeholder": "例如：工作日晚上 4 点后",
        "consent_to_contact": "我同意你们就这次咨询联系我。",
        "consent_required": "提交前必须同意联系条款。",
        "full_name": "姓名",
        "email": "邮箱",
        "phone": "电话",
        "wechat_id": "微信号",
        "save_lead": "提交预筛并查看下一步",
        "lead_required": "姓名必填。",
        "lead_contact_required": "至少填写一种联系方式：邮箱、电话或微信号。",
        "email_invalid": "请输入有效的邮箱地址。",
        "email_required_for_preference": "如果偏好邮箱联系，必须填写邮箱。",
        "phone_invalid": "请输入有效的电话号码。",
        "phone_required_for_preference": "如果偏好电话或短信联系，必须填写电话。",
        "wechat_required_for_preference": "如果偏好微信联系，必须填写微信号。",
        "leads": "线索数",
        "funnel_snapshot": "漏斗概览",
        "source_overview": "来源概览",
        "top_sources": "主要来源",
        "download_csv": "下载 leads CSV",
        "no_leads": "还没有保存任何线索。先完整跑一遍预筛流程。",
        "select_lead": "选择线索",
        "search_leads": "搜索线索",
        "search_placeholder": "按姓名、邮箱、电话或地址搜索",
        "filter_stage": "按阶段筛选",
        "filter_path": "按路径筛选",
        "filter_source": "按来源筛选",
        "all_stages": "全部阶段",
        "all_paths": "全部路径",
        "all_sources": "全部来源",
        "priority_queue": "优先处理队列",
        "queue_empty": "当前没有命中优先处理队列的线索。",
        "lead_stage": "线索阶段",
        "assigned_to": "负责人",
        "next_action": "下一步动作",
        "last_updated": "最后更新",
        "source_info": "来源追踪",
        "source_tag": "来源标签",
        "utm_source": "UTM source",
        "utm_medium": "UTM medium",
        "utm_campaign": "UTM campaign",
        "internal_notes": "内部备注",
        "disposition_reason": "处置原因",
        "save_lead_updates": "保存线索更新",
        "lead_updated": "线索已更新。",
        "edit_lead_intake": "编辑客户输入数据",
        "save_customer_changes": "保存客户输入修改",
        "customer_data_updated": "客户输入已更新，系统结果已重新计算。",
        "delete_lead": "删除线索",
        "delete_warning": "这会把该线索从本地存储中移除。",
        "delete_confirm": "我确认要删除这条线索。",
        "delete_lead_button": "删除这条线索",
        "lead_deleted": "线索已删除。",
        "delete_sync_failed": "删除已被阻止，因为外部同步失败。请先修复 webhook 或关闭它，再删除。",
        "duplicate_lead_updated": "系统识别到这是一条重复线索，已更新原有记录，没有新建重复数据。",
        "saved_at": "保存时间",
        "name": "姓名",
        "address": "地址",
        "goal": "目标",
        "path": "路径",
        "recommended_service_short": "建议服务",
        "not_provided": "未填写",
        "none": "无",
        "what_we_ask": "我们会先问什么",
        "public_sidebar_caption": "这是早期路径判断，不是最终 permit、法律或工程结论。",
        "early_signal": "早期判断信号",
        "early_signal_caption": "随着你填写的信息变多，这个判断会更新。最终仍取决于 records 和人工审核。",
        "needs_reply_today": "超过 24 小时待回复",
        "quick_actions": "快捷动作",
        "mark_contacted": "标记已联系",
        "mark_qualified": "标记有效",
        "move_to_nurture": "转入培育",
        "mark_closed_lost": "标记未成交",
        "quick_action_saved": "快捷动作已保存。",
        "ai_copilot": "AI 辅助",
        "ai_priority": "优先级判断",
        "ai_lead_score": "线索分数",
        "ai_lead_temperature": "线索温度",
        "ai_recommended_owner": "建议负责人",
        "ai_summary": "线索摘要",
        "ai_score_reasons": "为什么会是这个分数",
        "ai_call_objectives": "联系目标",
        "ai_missing_information": "缺失或待确认信息",
        "ai_document_requests": "建议先要的资料",
        "ai_crm_handoff_note": "CRM / 交接备注",
        "ai_outreach_draft": "建议外联话术",
        "business_loop_doc": "业务闭环",
        "workflow_doc": "NotebookLM 工作流",
        "stage_guide": "阶段说明",
        "google_sheets_setup": "Google Sheets 接入",
        "stage_guide_note": "团队更新 stage 时，统一按下面定义执行。",
        "lead_blockers": "阻碍信号",
        "lead_rationale": "为什么这个 lead 会被分到这里",
        "jurisdiction_seeds": "管辖 Playbook 种子库",
        "best_fit_pages": "最适合的前台入口页",
        "workflow_note": "NotebookLM 只做内部知识整理；前台预筛只使用你清洗后的规则。",
        "tab_launch": "发布工具",
        "launch_kit_title": "投放发布工具",
        "launch_kit_caption": "生成可直接发微信、agent、社群或网站嵌入的小程序式入口链接。",
        "public_base_url": "对外公开链接",
        "campaign_source": "来源标签",
        "campaign_medium": "UTM medium",
        "campaign_name": "活动名称",
        "embed_mode": "嵌入 / 小组件模式",
        "channel_templates": "生成的链接",
        "default_path": "通用物业预筛",
        "share_copy": "建议分享文案",
        "wechat_share_copy": "微信分享文案",
        "agent_share_copy": "Agent / 合作文案",
        "social_share_copy": "短内容文案",
    },
}

YES_NO_LABELS = {
    "en": {"Yes": "Yes", "No": "No", "Not sure": "Not sure"},
    "zh": {"Yes": "是", "No": "否", "Not sure": "不确定"},
}

CONTACT_PREFERENCE_LABELS = {
    "en": {"Phone": "Phone", "Email": "Email", "Text": "Text", "WeChat": "WeChat", "No preference": "No preference"},
    "zh": {"Phone": "电话", "Email": "邮箱", "Text": "短信", "WeChat": "微信", "No preference": "无特别偏好"},
}

STAGE_LABELS = {
    "en": {
        "new": "New",
        "needs_review": "Needs review",
        "contacted": "Contacted",
        "qualified": "Qualified",
        "screening_booked": "Screening booked",
        "proposal_sent": "Proposal sent",
        "closed_won": "Closed won",
        "closed_lost": "Closed lost",
        "nurture": "Nurture",
        "archived": "Archived",
    },
    "zh": {
        "new": "新线索",
        "needs_review": "待审核",
        "contacted": "已联系",
        "qualified": "已确认有效",
        "screening_booked": "已预约 screening",
        "proposal_sent": "已发送报价",
        "closed_won": "已成交",
        "closed_lost": "未成交",
        "nurture": "后续培育",
        "archived": "已归档",
    },
}

STAGE_HELP = {
    "en": {
        "new": "Fresh lead from the public screen. Needs first review.",
        "needs_review": "Input is incomplete, conflicting, or too complex for direct sales follow-up.",
        "contacted": "A team member has already made first contact.",
        "qualified": "Real project, enough signal, worth pushing into a paid next step.",
        "screening_booked": "Customer agreed to the paid screening / consultation step.",
        "proposal_sent": "A proposal, quote, or service recommendation has been sent.",
        "closed_won": "Customer signed or paid and is now in delivery.",
        "closed_lost": "The lead is no longer moving forward.",
        "nurture": "Not ready now, but still worth future follow-up.",
        "archived": "Spam, duplicate, or permanently inactive lead.",
    },
    "zh": {
        "new": "刚从前台进来的新线索，需要先做首次查看。",
        "needs_review": "输入信息不完整、有冲突，或复杂到不能直接推进销售跟进。",
        "contacted": "团队已经完成第一次联系。",
        "qualified": "是真实项目，信息足够，值得推进到付费下一步。",
        "screening_booked": "客户已确认进入付费 screening / consultation。",
        "proposal_sent": "已经发出报价、方案或服务建议。",
        "closed_won": "客户已付款或签约，进入交付。",
        "closed_lost": "这条线索当前已不再推进。",
        "nurture": "现在还没准备好，但后续仍值得再次触达。",
        "archived": "垃圾线索、重复线索或永久不再跟进的线索。",
    },
}

DISPOSITION_LABELS = {
    "en": {
        "": "None",
        "duplicate": "Duplicate",
        "spam": "Spam",
        "no_response": "No response",
        "bad_fit": "Bad fit",
        "budget_mismatch": "Budget mismatch",
        "data_incomplete": "Data incomplete",
        "future_nurture": "Future nurture",
        "high_risk_external": "High-risk external review",
    },
    "zh": {
        "": "无",
        "duplicate": "重复线索",
        "spam": "垃圾线索",
        "no_response": "无回应",
        "bad_fit": "不匹配",
        "budget_mismatch": "预算不匹配",
        "data_incomplete": "资料不完整",
        "future_nurture": "未来培育",
        "high_risk_external": "需外部专业判断",
    },
}

JURISDICTION_LABELS_ZH = {
    "city_of_los_angeles": "洛杉矶市（LADBS / LA City Planning / LAHD）",
    "unincorporated_la_county": "洛杉矶县非建制地区（EPIC-LA / district offices）",
    "contract_city": "由洛杉矶县系统服务的 contract city",
    "pasadena": "Pasadena",
    "arcadia": "Arcadia",
    "monterey_park": "Monterey Park",
    "sgv_other": "其他 SGV 城市 / 需要人工确认",
    "unknown": "管辖机构未确认，需要人工核对",
}

PROJECT_LABELS_ZH = {
    "detached_adu": "新建独立 ADU 路径",
    "garage_conversion": "现有车库改造路径",
    "jadu": "JADU 路径",
    "unpermitted_unit": "违建单元救援 / 合法化路径",
    "unknown": "项目类型需要人工确认",
}

STRUCTURE_LABELS_ZH = {
    "detached_garage": "独立车库",
    "attached_garage": "连体车库",
    "existing_unit": "现有居住单元",
    "house_interior_space": "主屋内部空间",
    "not_sure": "暂不确定",
}

BLOCKER_LABELS_ZH = {
    "owner_not_ready": "还不能确认填写人是否为产权人，所以决策权限不清楚。",
    "hillside": "hillside 或特殊坡地条件，通常会让项目脱离最简单的标准路径。",
    "basement": "地下室或低于地面的居住空间，不属于标准车库改造路径。",
    "addition_without_permit": "有无 permit 的加建，通常会让快车道审核和记录核对变复杂。",
    "unpermitted_work": "现场存在无 permit 施工，通常要先做更深的 records review，不能直接信任标准路径。",
    "prior_violation": "已有 correction、violation 或 code enforcement，会明显抬高风险和处理时间。",
    "prior_plans": "已经有旧 plan set 或 correction comments，说明这更像 blocker diagnosis，而不是全新标准项目。",
    "jurisdiction_unknown": "还没有确认具体由哪个 city / county 管，当前分流不完整。",
}

ROUTE_LABELS = {
    "en": {
        "A": "A · Standard path",
        "B": "B · Rescue / legalization",
        "C": "C · Blocker diagnosis",
    },
    "zh": {
        "A": "A · 标准路径",
        "B": "B · 救援 / 合法化",
        "C": "C · 卡点诊断",
    },
}

RISK_LABELS = {
    "en": {"Green": "Green", "Yellow": "Yellow", "Orange": "Orange", "Red": "Red"},
    "zh": {"Green": "绿色", "Yellow": "黄色", "Orange": "橙色", "Red": "红色"},
}

SERVICE_LABELS = {
    "en": {
        "A": "Paid Property Record + Jurisdiction Screening ($295-$595)",
        "B": "Deep Records Review / Rescue Strategy ($1,500+ depending on complexity)",
        "C": "Paid Screening + Blocker Diagnosis ($295-$595 to start)",
    },
    "zh": {
        "A": "付费产权与管辖预筛（$295-$595）",
        "B": "深度 records review / 救援策略（$1,500+，视复杂度而定）",
        "C": "付费预筛 + blocker 诊断（$295-$595 起）",
    },
}

KEYWORD_LABELS = {
    "en": {
        "garage_conversion": "garage conversion",
        "detached_adu": "detached ADU",
        "jadu": "JADU",
        "unpermitted_unit": "legalization",
        "hillside": "hillside",
        "basement": "basement",
        "rent": "rental",
        "permit_blocker": "permit blocker",
    },
    "zh": {
        "garage_conversion": "车库改造",
        "detached_adu": "独立 ADU",
        "jadu": "JADU",
        "unpermitted_unit": "合法化",
        "hillside": "坡地",
        "basement": "地下室",
        "rent": "出租",
        "permit_blocker": "permit 卡点",
    },
}

QUESTION_TEXT = {
    "property_address": {
        "prompt": {"en": "What is the property address?", "zh": "物业地址是什么？"},
        "help": {
            "en": "Use the real street address if possible. The first version uses this to suggest the likely jurisdiction.",
            "zh": "尽量填写真实街道地址。第一版会根据地址猜测可能的 jurisdiction。",
        },
        "placeholder": {"en": "1234 Example Ave, Pasadena, CA 91101", "zh": "例如：1234 Example Ave, Pasadena, CA 91101"},
    },
    "brief_goal": {
        "prompt": {"en": "What are you trying to do?", "zh": "你想做什么？"},
        "help": {
            "en": "Describe the goal in one sentence. Example: I want to convert my detached garage into a rental ADU.",
            "zh": "用一句话描述目标。例如：我想把独立车库改成可出租的 ADU。",
        },
        "placeholder": {
            "en": "I want to convert my detached garage into a legal rental unit.",
            "zh": "例如：我想把现有车库合法改造成可出租单元。",
        },
    },
    "jurisdiction": {
        "prompt": {"en": "Which jurisdiction governs this property?", "zh": "这个物业归哪个 jurisdiction 管？"},
        "help": {
            "en": "The app will suggest one from the address. You can override it before continuing.",
            "zh": "系统会根据地址先猜一个，你可以手动修改后再继续。",
        },
    },
    "owner_on_title": {"prompt": {"en": "Are you the property owner on title?", "zh": "你是产权人本人吗？"}},
    "project_type": {
        "prompt": {"en": "Which path sounds closest to your project?", "zh": "以下哪条路径最接近你的项目？"},
        "help": {
            "en": "This is a working classification only. It can change after records review.",
            "zh": "这只是当前的工作分类，后续 records review 后可能会调整。",
        },
    },
    "structure_type": {"prompt": {"en": "What structure are you talking about?", "zh": "你现在说的是哪种结构？"}},
    "hillside": {"prompt": {"en": "Is the property in a hillside area or special slope condition?", "zh": "这个物业是否位于 hillside 或特殊坡地条件中？"}},
    "basement": {"prompt": {"en": "Is any part of the intended unit in a basement or below grade?", "zh": "目标单元里是否有任何部分位于地下室或低于地面？"}},
    "addition_without_permit": {"prompt": {"en": "Has any addition been built without permits?", "zh": "现场是否有无 permit 的加建？"}},
    "unpermitted_work": {"prompt": {"en": "Is there any existing unpermitted construction on site?", "zh": "现场是否已经存在无 permit 施工？"}},
    "prior_violation": {"prompt": {"en": "Have you received a correction notice, violation, or code enforcement letter?", "zh": "你是否收到过 correction notice、violation 或 code enforcement letter？"}},
    "prior_plans": {"prompt": {"en": "Do you have an old plan set, permit number, or active correction comments already?", "zh": "你是否已经有旧 plan set、permit number 或 active correction comments？"}},
    "separate_utility_request": {"prompt": {"en": "Do you want a separate address or separate utilities?", "zh": "你是否希望申请独立地址或独立水电？"}},
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink-strong: #12343b;
            --ink: #264047;
            --ink-soft: #4a656b;
            --surface: rgba(255, 255, 255, 0.96);
            --surface-muted: rgba(250, 247, 240, 0.98);
            --border: rgba(13, 66, 74, 0.12);
            --shadow: 0 10px 30px rgba(12, 42, 46, 0.08);
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(198, 220, 229, 0.45), transparent 24%),
                linear-gradient(180deg, #f8f4ec 0%, #f3ede3 45%, #f8f6f2 100%);
            color: var(--ink);
        }
        [data-testid="stAppViewContainer"] {
            color: var(--ink);
        }
        [data-testid="stHeader"] {
            background: rgba(248, 244, 236, 0.82);
            backdrop-filter: blur(10px);
        }
        [data-testid="stMarkdownContainer"],
        [data-testid="stMarkdownContainer"] * ,
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] * ,
        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"],
        label[data-testid="stWidgetLabel"],
        .stRadio label,
        .stSubheader,
        h1, h2, h3, h4, h5, h6,
        p, li {
            color: var(--ink) !important;
        }
        div[data-testid="stForm"] {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1rem 1rem 0.4rem 1rem;
            box-shadow: var(--shadow);
        }
        [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stMetric"] {
            background: var(--surface-muted);
            border: 1px solid var(--border);
            border-radius: 18px;
            box-shadow: var(--shadow);
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.35rem 0.9rem 0.7rem 0.9rem;
        }
        [data-testid="stMetric"] {
            padding: 0.75rem 0.95rem;
        }
        .stTextInput input,
        .stTextArea textarea,
        div[data-baseweb="select"] > div,
        div[data-baseweb="base-input"] > div {
            background: var(--surface) !important;
            color: var(--ink-strong) !important;
            border-color: rgba(18, 52, 59, 0.16) !important;
        }
        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder {
            color: #70858a !important;
        }
        .stRadio [role="radiogroup"] {
            gap: 0.45rem;
            padding-top: 0.15rem;
        }
        .stRadio [role="radiogroup"] label {
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid rgba(18, 52, 59, 0.12);
            border-radius: 999px;
            padding: 0.2rem 0.7rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(255, 255, 255, 0.72);
            border-radius: 999px;
            color: var(--ink) !important;
            padding: 0.35rem 0.95rem;
        }
        .stTabs [aria-selected="true"] {
            background: #12343b;
        }
        .stTabs [aria-selected="true"] p {
            color: #f8fbfc !important;
        }
        .hero-card, .result-card, .workflow-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1.1rem 1.2rem;
            box-shadow: var(--shadow);
        }
        .public-top-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(248,244,236,0.98) 100%);
            border: 1px solid rgba(18, 52, 59, 0.12);
            border-radius: 24px;
            padding: 1.25rem 1.35rem 1rem 1.35rem;
            box-shadow: 0 18px 40px rgba(12, 42, 46, 0.10);
            margin-bottom: 1rem;
        }
        .entry-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.85rem;
            margin-top: 1rem;
        }
        .entry-card {
            display: block;
            text-decoration: none !important;
            background: rgba(255,255,255,0.88);
            border: 1px solid rgba(18, 52, 59, 0.10);
            border-radius: 18px;
            padding: 0.95rem 1rem;
            color: var(--ink) !important;
            box-shadow: 0 8px 20px rgba(12, 42, 46, 0.05);
            transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
        }
        .entry-card:hover {
            transform: translateY(-1px);
            box-shadow: 0 14px 24px rgba(12, 42, 46, 0.08);
            border-color: rgba(18, 52, 59, 0.20);
        }
        .entry-card.active {
            background: #12343b;
            border-color: #12343b;
            box-shadow: 0 14px 28px rgba(18, 52, 59, 0.18);
        }
        .entry-card.active .entry-card-title,
        .entry-card.active .entry-card-desc {
            color: #f8fbfc !important;
        }
        .entry-card-title {
            font-size: 1rem;
            font-weight: 700;
            color: var(--ink-strong) !important;
            margin-bottom: 0.3rem;
        }
        .entry-card-desc {
            font-size: 0.9rem;
            line-height: 1.45;
            color: var(--ink-soft) !important;
        }
        @media (max-width: 900px) {
            .entry-grid {
                grid-template-columns: 1fr;
            }
        }
        .hero-title {
            font-size: 2.1rem;
            line-height: 1.05;
            font-weight: 700;
            color: var(--ink-strong);
            margin-bottom: 0.5rem;
        }
        .pill {
            display: inline-block;
            margin-right: 0.5rem;
            margin-bottom: 0.4rem;
            padding: 0.25rem 0.65rem;
            border-radius: 999px;
            background: #eef4f1;
            color: #1d4b45 !important;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .risk-Green {color: #137547 !important; font-weight: 700;}
        .risk-Yellow {color: #9a6b00 !important; font-weight: 700;}
        .risk-Orange {color: #c15b00 !important; font-weight: 700;}
        .risk-Red {color: #b42318 !important; font-weight: 700;}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_repository() -> LeadRepository:
    return LeadRepository(DATA_PATH)


def normalize_existing_leads(repository: LeadRepository) -> None:
    for lead in repository.list_leads():
        if backfill_lead_defaults(lead):
            repository.update_lead(lead)


def initialize_state() -> None:
    st.session_state.setdefault("answers", {})
    st.session_state.setdefault("step_index", 0)
    st.session_state.setdefault("lead_saved", False)
    st.session_state.setdefault("show_result", False)
    st.session_state.setdefault("admin_authenticated", False)
    st.session_state.setdefault(
        "contact",
        {
            "full_name": "",
            "email": "",
            "phone": "",
            "wechat_id": "",
            "contact_preference": "No preference",
            "best_contact_time": "",
            "consent_to_contact": "No",
        },
    )
    st.session_state.setdefault("language", "en")
    st.session_state.setdefault("source_context", {"source_tag": "", "utm_source": "", "utm_medium": "", "utm_campaign": ""})


def reset_flow() -> None:
    st.session_state["answers"] = {}
    st.session_state["step_index"] = 0
    st.session_state["lead_saved"] = False
    st.session_state["show_result"] = False
    st.session_state["contact"] = {
        "full_name": "",
        "email": "",
        "phone": "",
        "wechat_id": "",
        "contact_preference": "No preference",
        "best_contact_time": "",
        "consent_to_contact": "No",
    }


def answers_object() -> ScreeningAnswers:
    payload = dict(st.session_state.get("answers", {}))
    payload.update(st.session_state.get("contact", {}))
    payload.update(st.session_state.get("source_context", {}))
    return ScreeningAnswers.from_dict(payload)


def current_question() -> Optional[dict[str, Any]]:
    index = st.session_state["step_index"]
    if index >= len(QUESTION_FLOW):
        return None
    return QUESTION_FLOW[index]


def current_language() -> str:
    return st.session_state.get("language", "en")


def t(key: str) -> str:
    language = current_language()
    return TEXT.get(language, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def localized_mapping_label(question_id: str, value: str, language: str) -> str:
    if value in YES_NO_LABELS["en"]:
        return YES_NO_LABELS[language].get(value, value)
    if question_id == "contact_preference":
        return CONTACT_PREFERENCE_LABELS[language].get(value, value)
    if question_id == "jurisdiction":
        mapping = JURISDICTION_LABELS if language == "en" else JURISDICTION_LABELS_ZH
        return mapping.get(value, value)
    if question_id == "project_type":
        mapping = PROJECT_LABELS if language == "en" else PROJECT_LABELS_ZH
        return mapping.get(value, value)
    if question_id == "structure_type":
        mapping = STRUCTURE_LABELS if language == "en" else STRUCTURE_LABELS_ZH
        return mapping.get(value, value)
    return value


def question_copy(question_id: str, field: str, default: str = "") -> str:
    overrides = QUESTION_TEXT.get(question_id, {})
    translated = overrides.get(field, {})
    return translated.get(current_language(), default)


def answer_label(question: dict[str, Any], value: str) -> str:
    return localized_mapping_label(question["id"], value, current_language())


def option_index(options: list[str], value: str) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0


def admin_password_configured() -> bool:
    return bool(get_setting("ADU_ADMIN_PASSWORD", ""))


def admin_access_granted() -> bool:
    if not admin_password_configured():
        return True
    return bool(st.session_state.get("admin_authenticated", False))


def is_valid_admin_password(raw_value: str) -> bool:
    configured = get_setting("ADU_ADMIN_PASSWORD", "")
    if not configured:
        return True
    return hmac.compare_digest(raw_value, configured)


def looks_like_email(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value.strip()))


def normalize_phone_digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def looks_like_phone(value: str) -> bool:
    digits = normalize_phone_digits(value)
    return 10 <= len(digits) <= 15


def validate_contact_inputs(
    *,
    full_name: str,
    email: str,
    phone: str,
    wechat_id: str,
    contact_preference: str,
    require_consent: bool = False,
    consent_to_contact: bool = False,
) -> str | None:
    if not full_name.strip():
        return t("lead_required")
    if not email.strip() and not phone.strip() and not wechat_id.strip():
        return t("lead_contact_required")
    if email.strip() and not looks_like_email(email):
        return t("email_invalid")
    if phone.strip() and not looks_like_phone(phone):
        return t("phone_invalid")
    if contact_preference == "Email" and not email.strip():
        return t("email_required_for_preference")
    if contact_preference in {"Phone", "Text"} and not phone.strip():
        return t("phone_required_for_preference")
    if contact_preference == "WeChat" and not wechat_id.strip():
        return t("wechat_required_for_preference")
    if require_consent and not consent_to_contact:
        return t("consent_required")
    return None


def route_label(route: str) -> str:
    return ROUTE_LABELS[current_language()].get(route, route)


def risk_label(risk_tier: str) -> str:
    return RISK_LABELS[current_language()].get(risk_tier, risk_tier)


def keyword_label(keyword: str) -> str:
    return KEYWORD_LABELS[current_language()].get(keyword, keyword.replace("_", " "))


def service_label(route: str, fallback: str) -> str:
    return SERVICE_LABELS[current_language()].get(route, fallback)


def stage_label(stage: str) -> str:
    return STAGE_LABELS[current_language()].get(stage, stage)


def disposition_label(reason: str) -> str:
    return DISPOSITION_LABELS[current_language()].get(reason, reason or t("none"))


def normalize_public_entry_key(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    return normalized if normalized in PUBLIC_ENTRY_VARIANTS else "default"


def current_public_entry() -> str:
    query_params = st.query_params
    requested = str(query_params.get("entry", "")).strip()
    if requested:
        return normalize_public_entry_key(requested)

    configured_default = get_setting("ADU_DEFAULT_PUBLIC_ENTRY", "default")
    return normalize_public_entry_key(configured_default)


def current_public_variant() -> dict[str, Any]:
    return PUBLIC_ENTRY_VARIANTS[current_public_entry()]


def public_variant_text(key: str) -> Any:
    value = current_public_variant().get(key)
    if isinstance(value, dict):
        return value.get(current_language())
    return value


def public_entry_href(entry_key: str) -> str:
    query_params = st.query_params
    params: dict[str, str] = {}
    params["view"] = "public"
    params["entry"] = entry_key

    if is_embed_mode():
        params["embed"] = "1"

    for key in ("source", "utm_source", "utm_medium", "utm_campaign"):
        value = str(query_params.get(key, "")).strip()
        if value:
            params[key] = value

    query_string = "&".join(f"{key}={value}" for key, value in params.items())
    return f"?{query_string}"


def normalize_public_base_url(base_url: str) -> str:
    cleaned = base_url.strip()
    if not cleaned:
        return suggested_public_base_url()

    parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
    host = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""

    if not host:
        return suggested_public_base_url()

    is_local = host.startswith("localhost") or host.startswith("127.0.0.1")
    scheme = parsed.scheme or ("http" if is_local else "https")
    if not is_local and host.endswith("streamlit.app"):
        scheme = "https"
    if not is_local and scheme == "http":
        scheme = "https"

    normalized_path = path.rstrip("/")
    return f"{scheme}://{host}{normalized_path}"


def build_public_url(base_url: str, entry_key: str, *, source: str = "", medium: str = "", campaign: str = "", embed: bool = False) -> str:
    params: dict[str, str] = {"view": "public"}
    if entry_key != "default":
        params["entry"] = entry_key
    if source:
        params["source"] = source
        params["utm_source"] = source
    if medium:
        params["utm_medium"] = medium
    if campaign:
        params["utm_campaign"] = campaign
    if embed:
        params["embed"] = "1"
    query_string = urlencode(params)
    normalized_base = normalize_public_base_url(base_url).rstrip("/")
    return f"{normalized_base}/?{query_string}"


def hero_copy(view_mode: str) -> tuple[str, str]:
    if view_mode == "admin":
        return t("hero_admin_title"), t("hero_admin_body")
    return str(public_variant_text("hero_title")), str(public_variant_text("hero_body"))


def hero_eyebrow(view_mode: str) -> str:
    if view_mode == "admin":
        return str(PUBLIC_ENTRY_VARIANTS["default"]["hero_eyebrow"][current_language()])
    return str(public_variant_text("hero_eyebrow"))


def localized_public_result_view(result: Any) -> dict[str, str | list[str]]:
    detailed = localized_result_view(result)
    route_summary = {
        "A": t("public_route_standard"),
        "C": t("public_route_blocker"),
        "B": t("public_route_rescue"),
    }.get(result.recommended_path, detailed["summary"])

    review_level = {
        "Green": t("public_review_standard"),
        "Yellow": t("public_review_elevated"),
        "Orange": t("public_review_elevated"),
        "Red": t("public_review_priority"),
    }.get(result.risk_tier, risk_label(result.risk_tier))

    likely_next_step = {
        "A": t("public_service_standard"),
        "C": t("public_service_blocker"),
        "B": t("public_service_rescue"),
    }.get(result.recommended_path, detailed["service"])

    return {
        "summary": str(route_summary),
        "review_level": str(review_level),
        "likely_next_step": str(likely_next_step),
        "blockers": detailed["blockers"],
        "steps": detailed["steps"],
    }


def current_view_mode() -> str:
    if get_bool_setting("ADU_FORCE_PUBLIC_ONLY", False):
        return "public"
    query_params = st.query_params
    requested = str(query_params.get("view", "public")).strip().casefold()
    return "admin" if requested == "admin" else "public"


def is_embed_mode() -> bool:
    query_params = st.query_params
    requested = str(query_params.get("embed", "")).strip().casefold()
    return requested in {"1", "true", "yes", "widget"}


def sync_source_context_from_query_params() -> None:
    query_params = st.query_params
    headers = getattr(st.context, "headers", {})
    st.session_state["source_context"] = resolve_source_context(query_params, headers)


def result_key(knowledge_ids: list[str], mapping: dict[str, str], fallback_label: str) -> str:
    for item in knowledge_ids:
        if item in mapping:
            return item
    reverse_mapping = {value: key for key, value in mapping.items()}
    return reverse_mapping.get(fallback_label, "")


def localized_result_view(result: Any) -> dict[str, Any]:
    language = current_language()
    jurisdiction_key = result_key(result.knowledge_ids, JURISDICTION_LABELS, result.jurisdiction_label)
    project_key = result_key(result.knowledge_ids, PROJECT_LABELS, result.project_label)
    blockers = result.blocker_tags or []

    jurisdiction_label = (
        JURISDICTION_LABELS.get(jurisdiction_key, result.jurisdiction_label)
        if language == "en"
        else JURISDICTION_LABELS_ZH.get(jurisdiction_key, result.jurisdiction_label)
    )
    project_label = (
        PROJECT_LABELS.get(project_key, result.project_label)
        if language == "en"
        else PROJECT_LABELS_ZH.get(project_key, result.project_label)
    )
    blocker_labels = [
        tag if not tag else (
            {
                "en": {
                    "owner_not_ready": "Lead is not confirmed as the owner on title, so decision-making authority is unclear.",
                    "hillside": "Hillside or special slope review usually removes a project from the simplest standard path.",
                    "basement": "Below-grade or basement living space is not a standard garage-conversion case.",
                    "addition_without_permit": "Unpermitted additions usually complicate fast-track review and records alignment.",
                    "unpermitted_work": "Existing unpermitted work typically requires deeper records review before any standard path can be trusted.",
                    "prior_violation": "Prior correction notices, violations, or code enforcement materially raise risk and handling time.",
                    "prior_plans": "Existing plan sets or correction notices indicate this is already in a blocker-diagnosis scenario.",
                    "jurisdiction_unknown": "The governing city / county path is not confirmed yet, so routing is incomplete.",
                },
                "zh": BLOCKER_LABELS_ZH,
            }[language].get(tag, tag)
        )
        for tag in blockers
    ]

    rationale_base = {
        "en": [
            "This first version only gives a preliminary routing result, not a final permit or legal opinion.",
            "Routing is based on jurisdiction, project intent, and blocker signals collected during intake.",
        ],
        "zh": [
            "这个第一版只给初步分流结果，不是最终 permit 结论，也不是法律意见。",
            "当前分流依据是 intake 收集到的 jurisdiction、项目意图和 blocker 信号。",
        ],
    }[language]

    if jurisdiction_key:
        rationale_jurisdiction = {
            "en": f"Address intake routed the property to: {jurisdiction_label}.",
            "zh": f"系统根据地址先把这个物业分到：{jurisdiction_label}。",
        }[language]
    else:
        rationale_jurisdiction = {
            "en": "Jurisdiction could not be confidently confirmed from the address alone.",
            "zh": "仅凭地址还不能可靠确认 jurisdiction。",
        }[language]

    rationale_project = {
        "en": f"Project intent currently looks closest to: {project_label}.",
        "zh": f"当前项目意图最接近：{project_label}。",
    }[language]

    route_specific = {
        "A": {
            "en": {
                "summary": "This lead looks closest to a standard ADU / garage-conversion path, but still needs paid screening before design spend.",
                "rationale": "This appears closest to a standard path, assuming records and existing conditions stay clean.",
                "steps": [
                    "Confirm jurisdiction and property record details.",
                    "Check whether the project fits the intended standard path for that city or county.",
                    "Move into paid screening before spending on design or construction.",
                ],
            },
            "zh": {
                "summary": "这个 lead 目前最接近标准 ADU / 车库改造路径，但在花设计费之前仍然要先做付费 screening。",
                "rationale": "在 records 和 existing conditions 都干净的前提下，这个项目目前最接近标准路径。",
                "steps": [
                    "先确认 jurisdiction 和 property record 细节。",
                    "核对这个项目是否符合对应 city / county 的标准路径。",
                    "在花设计费或施工费之前先进入付费 screening。",
                ],
            },
        },
        "C": {
            "en": {
                "summary": "This lead likely needs blocker diagnosis first. The goal is to learn what is blocking approval before moving into design.",
                "rationale": "Existing blockers suggest this should be handled as a blocker-diagnosis case before anyone promises a standard path.",
                "steps": [
                    "Pull records and permit history.",
                    "Map blocker items against the selected jurisdiction.",
                    "Decide whether the project stays in a standard path or escalates into rescue review.",
                ],
            },
            "zh": {
                "summary": "这个 lead 大概率要先做 blocker diagnosis。核心目标是在进入设计前先弄清楚到底什么在卡审批。",
                "rationale": "现有 blocker 说明这个项目应该先做卡点诊断，不能直接承诺它还属于标准路径。",
                "steps": [
                    "先拉 records 和 permit history。",
                    "把 blocker 一项项对照当前 jurisdiction 去核对。",
                    "决定这个项目还能否留在标准路径，还是要升级成救援型 review。",
                ],
            },
        },
        "B": {
            "en": {
                "summary": "This lead looks like a rescue or legalization case. It should be handled as a higher-friction strategy review, not as a standard intake.",
                "rationale": "The combination of project type and blocker signals points to a rescue / legalization workflow, not a simple standard path.",
                "steps": [
                    "Perform deep records review and existing-conditions triage.",
                    "Separate legalization strategy from new-construction strategy.",
                    "Avoid design or construction commitments until the rescue path is clarified.",
                ],
            },
            "zh": {
                "summary": "这个 lead 看起来更像救援或合法化案件，不适合按普通 intake 处理，而是要按更高摩擦的策略 review 去处理。",
                "rationale": "项目类型加上 blocker 组合，已经更像救援 / 合法化流程，而不是简单标准路径。",
                "steps": [
                    "先做深度 records review 和 existing conditions 分诊。",
                    "把合法化策略和新建策略拆开处理。",
                    "在救援路径没确认之前，不要急着承诺设计或施工。",
                ],
            },
        },
    }[result.recommended_path][language]

    rationale = rationale_base + [rationale_jurisdiction, rationale_project, route_specific["rationale"]]
    return {
        "route": route_label(result.recommended_path),
        "risk": risk_label(result.risk_tier),
        "service": service_label(result.recommended_path, result.recommended_service),
        "summary": route_specific["summary"],
        "jurisdiction": jurisdiction_label,
        "project": project_label,
        "blockers": blocker_labels,
        "rationale": rationale,
        "steps": route_specific["steps"],
    }


def suggested_value(question_id: str) -> str:
    answers = st.session_state.get("answers", {})
    if answers.get(question_id):
        return answers.get(question_id, "")
    if question_id == "jurisdiction":
        return suggest_jurisdiction(answers.get("property_address", ""))
    if question_id == "project_type":
        project_hint = str(current_public_variant().get("project_type", "") or "")
        if current_view_mode() == "public" and project_hint:
            return project_hint
        return suggest_project_type(answers.get("brief_goal", ""))
    return ""


def save_answer(question_id: str, value: str) -> None:
    st.session_state["answers"][question_id] = value
    st.session_state["step_index"] += 1


def go_back_one_step() -> None:
    current_index = max(int(st.session_state.get("step_index", 0)), 0)
    if current_index == 0:
        return
    st.session_state["step_index"] = current_index - 1
    st.session_state["show_result"] = False


def render_question(question: dict[str, Any]) -> None:
    prompt = question_copy(question["id"], "prompt", question.get("prompt", ""))
    help_text = question_copy(question["id"], "help", question.get("help", ""))
    placeholder = question_copy(question["id"], "placeholder", question.get("placeholder", ""))

    if st.session_state["step_index"] > 0:
        nav_cols = st.columns([1, 5])
        if nav_cols[0].button(t("back"), use_container_width=True, key=f"back_top_{question['id']}"):
            go_back_one_step()
            st.rerun()

    st.markdown(f"### {prompt}")
    if help_text:
        st.caption(help_text)

    with st.form(f"question_{question['id']}"):
        value = suggested_value(question["id"])
        if question["type"] == "text":
            input_value = st.text_input(
                "Answer",
                value=value,
                placeholder=placeholder,
                label_visibility="collapsed",
            )
        elif question["type"] == "textarea":
            input_value = st.text_area(
                "Answer",
                value=value,
                placeholder=placeholder,
                height=120,
                label_visibility="collapsed",
            )
        elif question["type"] == "radio":
            options = question["options"]
            try:
                index = options.index(value)
            except ValueError:
                index = 0
            input_value = st.radio(
                "Answer",
                options=options,
                index=index,
                format_func=lambda item: localized_mapping_label(question["id"], item, current_language()),
                horizontal=True,
                label_visibility="collapsed",
            )
        else:
            options = question["options"]
            option_keys = [option[0] for option in options]
            try:
                index = option_keys.index(value)
            except ValueError:
                index = 0
            input_value = st.selectbox(
                "Answer",
                options=option_keys,
                index=index,
                format_func=lambda item: localized_mapping_label(question["id"], item, current_language()),
                label_visibility="collapsed",
            )

        continue_clicked = st.form_submit_button(t("continue"), use_container_width=True)
        if continue_clicked:
            if not str(input_value or "").strip():
                st.error(t("field_required"))
            else:
                save_answer(question["id"], str(input_value))
                st.rerun()


def render_progress() -> None:
    answered = min(st.session_state["step_index"], len(QUESTION_FLOW))
    progress = answered / len(QUESTION_FLOW)
    st.progress(progress, text=t("progress").format(answered=answered, total=len(QUESTION_FLOW)))


def render_answer_summary() -> None:
    answers = st.session_state.get("answers", {})
    if not answers:
        st.info(t("no_answers"))
        return

    for question in QUESTION_FLOW[: st.session_state["step_index"]]:
        answer = answers.get(question["id"])
        if answer:
            prompt = question_copy(question["id"], "prompt", question.get("prompt", ""))
            st.markdown(f"**{prompt}**")
            st.write(answer_label(question, answer))


def render_public_intro() -> None:
    st.markdown(
        f"""
        <div class="workflow-card">
            <div style="font-size:1.2rem;font-weight:700;color:#12343b;">{public_variant_text("intro_title")}</div>
            <p style="margin-top:0.65rem;color:#334b50;">{public_variant_text("intro_body")}</p>
            <div style="margin-top:0.65rem;font-weight:600;color:#24464d;">{t("public_screen_time")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    value_cols = st.columns(3)
    value_blocks = [
        ("public_value_1_title", "public_value_1_body"),
        ("public_value_2_title", "public_value_2_body"),
        ("public_value_3_title", "public_value_3_body"),
    ]
    for column, (title_key, body_key) in zip(value_cols, value_blocks):
        with column:
            st.markdown(
                f"""
                <div class="workflow-card" style="height:100%;">
                    <div style="font-weight:700;color:#12343b;">{t(title_key)}</div>
                    <div style="margin-top:0.45rem;color:#334b50;">{t(body_key)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    process_col, fit_col = st.columns(2)
    with process_col:
        with st.container(border=True):
            st.subheader(t("public_process_title"))
            st.write(f"- {t('public_process_1')}")
            st.write(f"- {t('public_process_2')}")
            st.write(f"- {t('public_process_3')}")
    with fit_col:
        with st.container(border=True):
            st.subheader(t("public_fit_title"))
            for item in list(public_variant_text("sidebar_points"))[:3]:
                st.write(f"- {item}")


def render_public_header() -> None:
    entry_order = ["garage", "adu", "legalization"]
    current_entry = current_public_entry()
    cards = []
    for entry_key in entry_order:
        variant = PUBLIC_ENTRY_VARIANTS[entry_key]
        active_class = " active" if current_entry == entry_key else ""
        cards.append(
            (
                f'<a class="entry-card{active_class}" href="{public_entry_href(entry_key)}">'
                f'<div class="entry-card-title">{variant["selector_title"][current_language()]}</div>'
                f'<div class="entry-card-desc">{variant["selector_desc"][current_language()]}</div>'
                "</a>"
            )
        )
    cards_html = "".join(cards)

    st.markdown(
        (
            f'<div class="public-top-card">'
            f'<div style="font-size:2rem;font-weight:700;color:#12343b;line-height:1.05;">{t("public_main_title")}</div>'
            f'<div style="margin-top:0.55rem;font-size:1rem;color:#31464a;max-width:900px;">{t("public_main_subtitle")}</div>'
            f'<div style="margin-top:0.95rem;font-size:0.9rem;font-weight:700;color:#315a5d;text-transform:uppercase;letter-spacing:0.04em;">{t("entry_selector_label")}</div>'
            f'<div class="entry-grid">{cards_html}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_public_sidebar() -> None:
    answers = st.session_state.get("answers", {})
    if answers:
        result = compute_screening(answers_object())
        preview = localized_public_result_view(result)
        with st.container(border=True):
            st.subheader(t("early_signal"))
            st.write(preview["summary"])
            st.write(f"**{t('public_review_level')}**: {preview['review_level']}")
            st.caption(t("early_signal_caption"))

        st.subheader(t("your_intake_summary"))
        render_answer_summary()
        return

    st.subheader(str(public_variant_text("sidebar_title")) or t("what_we_ask"))
    for item in list(public_variant_text("sidebar_points")):
        st.write(f"- {item}")
    st.caption(t("public_sidebar_caption"))


def result_badges(result: Any) -> str:
    badges = [
        f'<span class="pill">{route_label(result.recommended_path)}</span>',
        f'<span class="pill risk-{result.risk_tier}">{risk_label(result.risk_tier)}</span>',
    ]
    for keyword in result.extracted_keywords[:4]:
        badges.append(f'<span class="pill">{keyword_label(keyword)}</span>')
    return "".join(badges)


def render_result(result: Any) -> None:
    display = localized_result_view(result)
    matched_notes = match_policy_notes(NOTES_PATH, result.knowledge_ids)
    st.markdown(
        f"""
        <div class="result-card">
            <div style="font-size:1.5rem;font-weight:700;color:#12343b;">{t("preliminary_result")}</div>
            <div style="margin-top:0.5rem;">{result_badges(result)}</div>
            <p style="margin-top:0.9rem;font-size:1rem;color:#24383d;">{display["summary"]}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(3)
    metric_cols[0].metric(t("recommended_path"), display["route"])
    metric_cols[1].metric(t("risk_tier"), display["risk"])
    metric_cols[2].metric(t("primary_service"), display["service"])

    detail_cols = st.columns(2)
    with detail_cols[0]:
        with st.container(border=True):
            st.subheader(t("current_reading"))
            st.write(f"**{t('jurisdiction')}**: {display['jurisdiction']}")
            st.write(f"**{t('project')}**: {display['project']}")
            if display["blockers"]:
                st.write(f"**{t('main_blockers')}**")
                for item in display["blockers"]:
                    st.write(f"- {item}")
            else:
                st.write(t("no_blockers"))

    with detail_cols[1]:
        with st.container(border=True):
            st.subheader(t("next_steps"))
            for item in display["steps"]:
                st.write(f"- {item}")
            st.write(f"**{t('why_routed')}**")
            for item in display["rationale"]:
                st.write(f"- {item}")

    if matched_notes:
        st.subheader(t("knowledge_notes"))
        for entry in matched_notes:
            st.markdown(
                f"""
                <div class="workflow-card">
                    <div style="font-weight:700;color:#12343b;">{entry['title']}</div>
                    <div style="margin-top:0.35rem;color:#334b50;">{entry['summary']}</div>
                    <div style="margin-top:0.5rem;"><a href="{entry['source_url']}" target="_blank">{t("source")}</a></div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_public_confirmation(result: Any) -> None:
    display = localized_public_result_view(result)
    st.markdown(
        f"""
        <div class="result-card">
            <div style="font-size:1.45rem;font-weight:700;color:#12343b;">{t("public_thank_you_title")}</div>
            <p style="margin-top:0.85rem;font-size:1rem;color:#24383d;">{t("public_thank_you_body")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    summary_cols = st.columns(2)
    with summary_cols[0]:
        with st.container(border=True):
            st.subheader(t("public_safe_result"))
            st.write(display["summary"])
            st.write(f"**{t('public_review_level')}**: {display['review_level']}")
            st.write(f"**{t('public_likely_next_step')}**: {display['likely_next_step']}")
            if display["blockers"]:
                st.write(f"**{t('public_possible_review_factors')}**")
                for item in display["blockers"]:
                    st.write(f"- {item}")
    with summary_cols[1]:
        with st.container(border=True):
            st.subheader(t("public_expected_contact"))
            st.write(t("public_expected_contact_body"))
            st.write(f"**{t('contact_preference')}**: {localized_mapping_label('contact_preference', answers_object().contact_preference or 'No preference', current_language())}")
            if answers_object().wechat_id:
                st.write(f"**{t('wechat_id')}**: {answers_object().wechat_id}")
            st.write(f"**{t('best_contact_time')}**: {answers_object().best_contact_time or t('not_provided')}")

    with st.container(border=True):
        st.subheader(t("public_next_step_title"))
        for item in display["steps"]:
            st.write(f"- {item}")


def render_contact_capture(result: Any, repository: LeadRepository) -> None:
    st.subheader(t("lead_capture"))
    st.caption(t("lead_capture_caption"))

    nav_cols = st.columns([1, 5])
    if nav_cols[0].button(t("back"), use_container_width=True, key="back_top_contact_capture"):
        go_back_one_step()
        st.rerun()

    with st.form("contact_capture"):
        full_name = st.text_input(t("full_name"), value=st.session_state["contact"]["full_name"])
        contact_cols = st.columns(3)
        email = contact_cols[0].text_input(t("email"), value=st.session_state["contact"]["email"])
        phone = contact_cols[1].text_input(t("phone"), value=st.session_state["contact"]["phone"])
        wechat_id = contact_cols[2].text_input(t("wechat_id"), value=st.session_state["contact"]["wechat_id"])
        contact_pref_value = st.session_state["contact"]["contact_preference"]
        if contact_pref_value not in CONTACT_PREFERENCE_OPTIONS:
            contact_pref_value = "No preference"
        contact_preference = st.selectbox(
            t("contact_preference"),
            options=CONTACT_PREFERENCE_OPTIONS,
            index=CONTACT_PREFERENCE_OPTIONS.index(contact_pref_value),
            format_func=lambda item: localized_mapping_label("contact_preference", item, current_language()),
        )
        best_contact_time = st.text_input(
            t("best_contact_time"),
            value=st.session_state["contact"]["best_contact_time"],
            placeholder=t("best_contact_placeholder"),
        )
        consent_to_contact = st.checkbox(
            t("consent_to_contact"),
            value=st.session_state["contact"]["consent_to_contact"] == "Yes",
        )
        submitted = st.form_submit_button(t("save_lead"), use_container_width=True)
        if submitted:
            error_message = validate_contact_inputs(
                full_name=full_name,
                email=email,
                phone=phone,
                wechat_id=wechat_id,
                contact_preference=contact_preference,
                require_consent=True,
                consent_to_contact=consent_to_contact,
            )
            if error_message:
                st.error(error_message)
            else:
                st.session_state["contact"] = {
                    "full_name": full_name.strip(),
                    "email": email.strip(),
                    "phone": phone.strip(),
                    "wechat_id": wechat_id.strip(),
                    "contact_preference": contact_preference,
                    "best_contact_time": best_contact_time.strip(),
                    "consent_to_contact": "Yes",
                }
                if not st.session_state["lead_saved"]:
                    current_answers = answers_object()
                    duplicate_lead = repository.find_duplicate_lead(current_answers)
                    if duplicate_lead is not None:
                        duplicate_lead.answers = current_answers
                        duplicate_lead.result = compute_screening(current_answers)
                        duplicate_lead.last_updated_at = utc_now_iso()
                        if not duplicate_lead.next_action.strip():
                            duplicate_lead.next_action = suggested_next_action_for_lead(
                                duplicate_lead.answers,
                                duplicate_lead.result,
                                duplicate_lead.stage,
                            )
                        delivery_result = deliver_lead(duplicate_lead, "lead.updated")
                        duplicate_lead = apply_delivery_result(duplicate_lead, delivery_result)
                        repository.update_lead(duplicate_lead)
                        st.success(t("duplicate_lead_updated"))
                    else:
                        lead = LeadRecord.create(current_answers, result)
                        delivery_result = deliver_lead(lead, "lead.created")
                        lead = apply_delivery_result(lead, delivery_result)
                        repository.save_lead(lead)
                    st.session_state["lead_saved"] = True
                st.session_state["show_result"] = True
                st.rerun()


def persist_admin_lead(lead: LeadRecord, repository: LeadRepository, event_type: str = "lead.updated") -> LeadRecord:
    lead.last_updated_at = utc_now_iso()
    delivery_result = deliver_lead(lead, event_type)
    lead = apply_delivery_result(lead, delivery_result)
    repository.update_lead(lead)
    return lead


def apply_quick_action(lead: LeadRecord, repository: LeadRepository, action: str) -> None:
    if action == "contacted":
        lead.stage = "contacted"
        if not lead.next_action.strip():
            lead.next_action = "Complete first qualification call and confirm timeline, ownership, and documents."
    elif action == "qualified":
        lead.stage = "qualified"
        lead.next_action = "Offer the paid screening step and schedule the next review conversation."
    elif action == "nurture":
        lead.stage = "nurture"
        if not lead.disposition_reason:
            lead.disposition_reason = "future_nurture"
        lead.next_action = "Set a future follow-up reminder and revisit when timing or readiness improves."
    elif action == "closed_lost":
        lead.stage = "closed_lost"
        if not lead.disposition_reason:
            lead.disposition_reason = "bad_fit"
        lead.next_action = "No active follow-up. Preserve notes in case the lead reopens later."
    else:
        return

    persist_admin_lead(lead, repository)
    st.success(t("quick_action_saved"))
    st.rerun()


def render_admin_lead_edit_form(lead: LeadRecord, repository: LeadRepository) -> None:
    with st.expander(t("edit_lead_intake")):
        with st.form(f"lead_edit_answers_{lead.id}"):
            property_address = st.text_input(t("address"), value=lead.answers.property_address)
            brief_goal = st.text_area(t("goal"), value=lead.answers.brief_goal, height=100)

            jurisdiction_keys = list(JURISDICTION_LABELS.keys())
            jurisdiction = st.selectbox(
                t("jurisdiction"),
                options=jurisdiction_keys,
                index=option_index(jurisdiction_keys, lead.answers.jurisdiction),
                format_func=lambda item: localized_mapping_label("jurisdiction", item, current_language()),
            )
            owner_on_title = st.radio(
                question_copy("owner_on_title", "prompt", ""),
                options=["Yes", "No", "Not sure"],
                index=option_index(["Yes", "No", "Not sure"], lead.answers.owner_on_title or "Not sure"),
                horizontal=True,
                format_func=lambda item: localized_mapping_label("owner_on_title", item, current_language()),
            )

            project_keys = list(PROJECT_LABELS.keys())
            project_type = st.selectbox(
                question_copy("project_type", "prompt", ""),
                options=project_keys,
                index=option_index(project_keys, lead.answers.project_type),
                format_func=lambda item: localized_mapping_label("project_type", item, current_language()),
            )
            structure_keys = list(STRUCTURE_LABELS.keys())
            structure_type = st.selectbox(
                question_copy("structure_type", "prompt", ""),
                options=structure_keys,
                index=option_index(structure_keys, lead.answers.structure_type),
                format_func=lambda item: localized_mapping_label("structure_type", item, current_language()),
            )

            yes_no_options = ["Yes", "No", "Not sure"]
            blocker_cols_a = st.columns(2)
            hillside = blocker_cols_a[0].radio(
                question_copy("hillside", "prompt", ""),
                options=yes_no_options,
                index=option_index(yes_no_options, lead.answers.hillside or "Not sure"),
                format_func=lambda item: localized_mapping_label("hillside", item, current_language()),
            )
            basement = blocker_cols_a[1].radio(
                question_copy("basement", "prompt", ""),
                options=yes_no_options,
                index=option_index(yes_no_options, lead.answers.basement or "Not sure"),
                format_func=lambda item: localized_mapping_label("basement", item, current_language()),
            )

            blocker_cols_b = st.columns(2)
            addition_without_permit = blocker_cols_b[0].radio(
                question_copy("addition_without_permit", "prompt", ""),
                options=yes_no_options,
                index=option_index(yes_no_options, lead.answers.addition_without_permit or "Not sure"),
                format_func=lambda item: localized_mapping_label("addition_without_permit", item, current_language()),
            )
            unpermitted_work = blocker_cols_b[1].radio(
                question_copy("unpermitted_work", "prompt", ""),
                options=yes_no_options,
                index=option_index(yes_no_options, lead.answers.unpermitted_work or "Not sure"),
                format_func=lambda item: localized_mapping_label("unpermitted_work", item, current_language()),
            )

            blocker_cols_c = st.columns(2)
            prior_violation = blocker_cols_c[0].radio(
                question_copy("prior_violation", "prompt", ""),
                options=yes_no_options,
                index=option_index(yes_no_options, lead.answers.prior_violation or "Not sure"),
                format_func=lambda item: localized_mapping_label("prior_violation", item, current_language()),
            )
            prior_plans = blocker_cols_c[1].radio(
                question_copy("prior_plans", "prompt", ""),
                options=yes_no_options,
                index=option_index(yes_no_options, lead.answers.prior_plans or "Not sure"),
                format_func=lambda item: localized_mapping_label("prior_plans", item, current_language()),
            )

            separate_utility_request = st.radio(
                question_copy("separate_utility_request", "prompt", ""),
                options=yes_no_options,
                index=option_index(yes_no_options, lead.answers.separate_utility_request or "Not sure"),
                horizontal=True,
                format_func=lambda item: localized_mapping_label("separate_utility_request", item, current_language()),
            )

            contact_cols = st.columns(2)
            full_name = contact_cols[0].text_input(t("name"), value=lead.answers.full_name)
            email = contact_cols[1].text_input(t("email"), value=lead.answers.email)
            secondary_contact_cols = st.columns(2)
            phone = secondary_contact_cols[0].text_input(t("phone"), value=lead.answers.phone)
            wechat_id = secondary_contact_cols[1].text_input(t("wechat_id"), value=lead.answers.wechat_id)
            contact_preference = st.selectbox(
                t("contact_preference"),
                options=CONTACT_PREFERENCE_OPTIONS,
                index=option_index(CONTACT_PREFERENCE_OPTIONS, lead.answers.contact_preference or "No preference"),
                format_func=lambda item: localized_mapping_label("contact_preference", item, current_language()),
            )
            best_contact_time = st.text_input(t("best_contact_time"), value=lead.answers.best_contact_time)

            source_cols = st.columns(2)
            source_tag = source_cols[0].text_input(t("source_tag"), value=lead.answers.source_tag)
            utm_source = source_cols[1].text_input(t("utm_source"), value=lead.answers.utm_source)
            utm_medium = source_cols[0].text_input(t("utm_medium"), value=lead.answers.utm_medium)
            utm_campaign = source_cols[1].text_input(t("utm_campaign"), value=lead.answers.utm_campaign)

            save_customer_changes = st.form_submit_button(t("save_customer_changes"), use_container_width=True)
            if save_customer_changes:
                error_message = validate_contact_inputs(
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    wechat_id=wechat_id,
                    contact_preference=contact_preference,
                )
                if error_message:
                    st.error(error_message)
                else:
                    lead.answers = ScreeningAnswers.from_dict(
                        {
                            "property_address": property_address,
                            "brief_goal": brief_goal,
                            "jurisdiction": jurisdiction,
                            "owner_on_title": owner_on_title,
                            "project_type": project_type,
                            "structure_type": structure_type,
                            "hillside": hillside,
                            "basement": basement,
                            "addition_without_permit": addition_without_permit,
                            "unpermitted_work": unpermitted_work,
                            "prior_violation": prior_violation,
                            "prior_plans": prior_plans,
                            "separate_utility_request": separate_utility_request,
                            "full_name": full_name,
                            "email": email,
                            "phone": phone,
                            "wechat_id": wechat_id,
                            "contact_preference": contact_preference,
                            "best_contact_time": best_contact_time,
                            "consent_to_contact": lead.answers.consent_to_contact or "Yes",
                            "source_tag": source_tag,
                            "utm_source": utm_source,
                            "utm_medium": utm_medium,
                            "utm_campaign": utm_campaign,
                        }
                    )
                    lead.result = compute_screening(lead.answers)
                    if not lead.next_action.strip():
                        lead.next_action = suggested_next_action_for_lead(
                            lead.answers,
                            lead.result,
                            lead.stage,
                        )
                    lead = persist_admin_lead(lead, repository)
                    st.success(t("customer_data_updated"))
                    st.rerun()

    with st.expander(t("delete_lead")):
        st.warning(t("delete_warning"))
        with st.form(f"lead_delete_{lead.id}"):
            confirm_delete = st.checkbox(t("delete_confirm"))
            submitted = st.form_submit_button(t("delete_lead_button"), use_container_width=True)
            if submitted:
                if not confirm_delete:
                    st.error(t("delete_confirm"))
                else:
                    delivery_result = deliver_lead(lead, "lead.deleted")
                    if delivery_result.configured and not delivery_result.success:
                        st.error(t("delete_sync_failed"))
                    else:
                        repository.delete_lead(lead.id)
                        st.success(t("lead_deleted"))
                        st.rerun()


def render_stage_guide() -> None:
    st.caption(t("stage_guide_note"))
    for stage in STAGE_OPTIONS:
        st.markdown(
            f"""
            <div class="workflow-card">
                <div style="font-weight:700;color:#12343b;">{stage_label(stage)}</div>
                <div style="margin-top:0.35rem;color:#334b50;">{STAGE_HELP[current_language()].get(stage, '')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _masked_config_value(name: str, value: str) -> str:
    if not value:
        return "missing"
    if name == "ADU_LEAD_WEBHOOK_URL":
        if "?token=" in value:
            base, token = value.split("?token=", 1)
            suffix = token[-6:] if len(token) >= 6 else token
            return f"{base}?token=***{suffix}"
        return value
    if name == "ADU_ADMIN_PASSWORD":
        return f"set ({len(value)} chars)"
    return value


def render_admin_config_diagnostics() -> None:
    with st.expander("Config diagnostics", expanded=False):
        names = [
            "ADU_LEAD_WEBHOOK_URL",
            "ADU_ADMIN_PASSWORD",
            "ADU_FORCE_PUBLIC_ONLY",
        ]
        for name in names:
            state = debug_setting_state(name)
            st.write(f"**{name}**")
            st.write(
                {
                    "effective_present": state["effective_present"],
                    "env_present": state["env_present"],
                    "direct_secret_present": state["direct_secret_present"],
                    "nested_secret_present": state["nested_secret_present"],
                    "secrets_available": state["secrets_available"],
                    "effective_value_preview": _masked_config_value(name, str(state["effective_value"])),
                }
            )


def get_admin_inbox_leads(repository: LeadRepository) -> tuple[list[LeadRecord], str]:
    local_leads = repository.list_leads()
    if not remote_lead_source_configured():
        return local_leads, "local_only"

    remote_leads, remote_error = fetch_remote_leads(limit=300)
    if remote_error:
        return local_leads, remote_error
    return merge_local_and_remote_leads(local_leads, remote_leads), "remote_ok"


def render_copilot_brief(lead: LeadRecord) -> None:
    brief = generate_copilot_brief(lead)
    with st.expander(t("ai_copilot"), expanded=True):
        st.write(f"**{t('ai_priority')}**: {brief.internal_priority}")
        score_cols = st.columns(3)
        score_cols[0].metric(t("ai_lead_score"), brief.lead_score)
        score_cols[1].metric(t("ai_lead_temperature"), brief.lead_temperature)
        score_cols[2].metric(t("ai_recommended_owner"), brief.recommended_owner)
        st.write(f"**{t('ai_summary')}**: {brief.lead_summary}")

        if brief.score_reasons:
            st.write(f"**{t('ai_score_reasons')}**")
            for item in brief.score_reasons:
                st.write(f"- {item}")

        st.write(f"**{t('ai_call_objectives')}**")
        for item in brief.call_objectives:
            st.write(f"- {item}")

        if brief.missing_information:
            st.write(f"**{t('ai_missing_information')}**")
            for item in brief.missing_information:
                st.write(f"- {item}")

        st.write(f"**{t('ai_document_requests')}**")
        for item in brief.document_requests:
            st.write(f"- {item}")

        st.text_area(
            t("ai_crm_handoff_note"),
            value=brief.crm_handoff_note,
            height=90,
            disabled=True,
            key=f"copilot_handoff_{lead.id}",
        )

        st.text_area(
            t("ai_outreach_draft"),
            value=brief.outreach_draft,
            height=140,
            disabled=True,
            key=f"copilot_draft_{lead.id}",
        )


def render_lead_inbox(repository: LeadRepository) -> None:
    leads, remote_status = get_admin_inbox_leads(repository)
    if webhook_configured():
        st.success(f"{t('webhook_ready')} {webhook_target_label()}")
    else:
        st.warning(t("webhook_missing"))
    render_admin_config_diagnostics()
    if remote_status == "remote_ok":
        st.caption("Admin inbox is using Google Sheets as the shared lead source.")
    elif remote_status not in {"local_only", ""}:
        st.caption(f"Remote inbox fallback: {remote_status}")
    metric_cols = st.columns(5)
    metric_cols[0].metric(t("leads"), len(leads))
    metric_cols[1].metric(route_label("A"), sum(1 for lead in leads if lead.result.recommended_path == "A"))
    metric_cols[2].metric(route_label("C"), sum(1 for lead in leads if lead.result.recommended_path == "C"))
    metric_cols[3].metric(route_label("B"), sum(1 for lead in leads if lead.result.recommended_path == "B"))
    metric_cols[4].metric(t("needs_reply_today"), sum(1 for lead in leads if lead_needs_attention(lead)))

    with st.expander(f"{t('funnel_snapshot')} / {t('source_overview')}"):
        stage_counts: dict[str, int] = {stage: 0 for stage in STAGE_OPTIONS}
        source_counts: dict[str, int] = {}
        for lead in leads:
            stage_counts[lead.stage] = stage_counts.get(lead.stage, 0) + 1
            source_key = lead.answers.source_tag or lead.answers.utm_source or "direct_or_unknown"
            source_counts[source_key] = source_counts.get(source_key, 0) + 1

        stage_cols = st.columns(3)
        for index, stage in enumerate(STAGE_OPTIONS[:6]):
            stage_cols[index % 3].metric(stage_label(stage), stage_counts.get(stage, 0))
        trailing_stage_cols = st.columns(4)
        for index, stage in enumerate(STAGE_OPTIONS[6:]):
            trailing_stage_cols[index].metric(stage_label(stage), stage_counts.get(stage, 0))

        st.write(f"**{t('top_sources')}**")
        for source_key, count in sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))[:8]:
            st.write(f"- {source_key}: {count}")

    csv_output = export_leads_csv(leads)
    st.download_button(
        t("download_csv"),
        data=csv_output,
        file_name="adu_screening_leads.csv",
        mime="text/csv",
        disabled=not bool(csv_output),
    )

    if not leads:
        st.info(t("no_leads"))
        return

    with st.expander(t("stage_guide")):
        render_stage_guide()

    filter_cols = st.columns([2, 1])
    search_query = filter_cols[0].text_input(t("search_leads"), placeholder=t("search_placeholder"))
    stage_filter_options = ["all"] + STAGE_OPTIONS
    selected_stage = filter_cols[1].selectbox(
        t("filter_stage"),
        options=stage_filter_options,
        format_func=lambda item: t("all_stages") if item == "all" else stage_label(item),
    )
    extra_filter_cols = st.columns(2)
    path_filter_options = ["all", "A", "C", "B"]
    selected_path = extra_filter_cols[0].selectbox(
        t("filter_path"),
        options=path_filter_options,
        format_func=lambda item: t("all_paths") if item == "all" else route_label(item),
    )
    source_options = ["all"] + sorted(
        {
            lead.answers.source_tag or lead.answers.utm_source or "direct_or_unknown"
            for lead in leads
        }
    )
    selected_source = extra_filter_cols[1].selectbox(
        t("filter_source"),
        options=source_options,
        format_func=lambda item: t("all_sources") if item == "all" else item,
    )

    normalized_search = search_query.strip().casefold()
    filtered_leads = []
    for lead in leads:
        if selected_stage != "all" and lead.stage != selected_stage:
            continue
        if selected_path != "all" and lead.result.recommended_path != selected_path:
            continue
        source_key = lead.answers.source_tag or lead.answers.utm_source or "direct_or_unknown"
        if selected_source != "all" and source_key != selected_source:
            continue
        haystack = " ".join(
            [
                lead.answers.full_name,
                lead.answers.email,
                lead.answers.phone,
                lead.answers.wechat_id,
                lead.answers.property_address,
            ]
        ).casefold()
        if normalized_search and normalized_search not in haystack:
            continue
        filtered_leads.append(lead)

    if not filtered_leads:
        st.info(t("no_leads"))
        return

    priority_queue = sorted(
        [lead for lead in filtered_leads if lead.stage in {"new", "needs_review", "contacted"}],
        key=lead_priority_key,
    )
    with st.expander(t("priority_queue"), expanded=bool(priority_queue)):
        if not priority_queue:
            st.info(t("queue_empty"))
        else:
            queue_rows = []
            for queued_lead in priority_queue[:12]:
                brief = generate_copilot_brief(queued_lead)
                queue_rows.append(
                    {
                        "name": queued_lead.answers.full_name,
                        "path": route_label(queued_lead.result.recommended_path),
                        "risk": risk_label(queued_lead.result.risk_tier),
                        "ai_score": brief.lead_score,
                        "owner": brief.recommended_owner,
                        "stage": stage_label(queued_lead.stage),
                        "source": queued_lead.answers.source_tag or queued_lead.answers.utm_source or "direct_or_unknown",
                        "address": queued_lead.answers.property_address,
                    }
                )
            st.dataframe(queue_rows, use_container_width=True, hide_index=True)

    options = {lead.id: lead for lead in filtered_leads}
    selected_id = st.selectbox(
        t("select_lead"),
        options=list(options.keys()),
        format_func=lambda item_id: f"{options[item_id].answers.full_name} | {risk_label(options[item_id].result.risk_tier)} | {options[item_id].answers.property_address}",
    )
    lead = options[selected_id]
    display = localized_result_view(lead.result)

    st.write(f"**{t('saved_at')}**: {lead.created_at}")
    st.write(f"**{t('name')}**: {lead.answers.full_name}")
    st.write(f"**{t('email')}**: {lead.answers.email}")
    st.write(f"**{t('phone')}**: {lead.answers.phone or t('not_provided')}")
    st.write(f"**{t('wechat_id')}**: {lead.answers.wechat_id or t('not_provided')}")
    st.write(
        f"**{t('contact_preference')}**: "
        f"{localized_mapping_label('contact_preference', lead.answers.contact_preference or 'No preference', current_language())}"
    )
    st.write(f"**{t('best_contact_time')}**: {lead.answers.best_contact_time or t('not_provided')}")
    st.write(f"**{t('address')}**: {lead.answers.property_address}")
    st.write(f"**{t('goal')}**: {lead.answers.brief_goal}")
    st.write(f"**{t('path')}**: {display['route']}")
    st.write(f"**{t('risk_tier')}**: {display['risk']}")
    st.write(f"**{t('lead_stage')}**: {stage_label(lead.stage)}")
    st.caption(STAGE_HELP[current_language()].get(lead.stage, ""))
    st.write(f"**{t('disposition_reason')}**: {disposition_label(lead.disposition_reason)}")
    st.write(f"**{t('assigned_to')}**: {lead.assigned_to or t('not_provided')}")
    st.write(f"**{t('next_action')}**: {lead.next_action or t('not_provided')}")
    st.write(f"**{t('last_updated')}**: {lead.last_updated_at or lead.created_at}")
    st.write(f"**{t('external_sync_status')}**: {lead.external_sync_status}")
    st.write(f"**{t('external_sync_at')}**: {lead.external_sync_at or t('not_provided')}")
    if lead.external_sync_error:
        st.write(f"**{t('external_sync_error')}**: {lead.external_sync_error}")
    st.write(f"**{t('recommended_service_short')}**: {display['service']}")
    st.write(f"**{t('source_info')}**")
    st.write(f"- {t('source_tag')}: {lead.answers.source_tag or t('not_provided')}")
    st.write(f"- {t('utm_source')}: {lead.answers.utm_source or t('not_provided')}")
    st.write(f"- {t('utm_medium')}: {lead.answers.utm_medium or t('not_provided')}")
    st.write(f"- {t('utm_campaign')}: {lead.answers.utm_campaign or t('not_provided')}")
    st.write(f"**{t('lead_blockers')}**")
    for item in display["blockers"]:
        st.write(f"- {item}")
    st.write(f"**{t('lead_rationale')}**")
    for item in display["rationale"]:
        st.write(f"- {item}")

    render_copilot_brief(lead)

    st.write(f"**{t('quick_actions')}**")
    quick_cols = st.columns(4)
    if quick_cols[0].button(t("mark_contacted"), use_container_width=True, key=f"quick_contacted_{lead.id}"):
        apply_quick_action(lead, repository, "contacted")
    if quick_cols[1].button(t("mark_qualified"), use_container_width=True, key=f"quick_qualified_{lead.id}"):
        apply_quick_action(lead, repository, "qualified")
    if quick_cols[2].button(t("move_to_nurture"), use_container_width=True, key=f"quick_nurture_{lead.id}"):
        apply_quick_action(lead, repository, "nurture")
    if quick_cols[3].button(t("mark_closed_lost"), use_container_width=True, key=f"quick_closed_lost_{lead.id}"):
        apply_quick_action(lead, repository, "closed_lost")

    with st.form(f"lead_update_{lead.id}"):
        updated_stage = st.selectbox(
            t("lead_stage"),
            options=STAGE_OPTIONS,
            index=STAGE_OPTIONS.index(lead.stage) if lead.stage in STAGE_OPTIONS else 0,
            format_func=stage_label,
        )
        disposition_reason = st.selectbox(
            t("disposition_reason"),
            options=DISPOSITION_OPTIONS,
            index=DISPOSITION_OPTIONS.index(lead.disposition_reason) if lead.disposition_reason in DISPOSITION_OPTIONS else 0,
            format_func=disposition_label,
        )
        assigned_to = st.text_input(t("assigned_to"), value=lead.assigned_to)
        next_action = st.text_input(t("next_action"), value=lead.next_action)
        internal_notes = st.text_area(t("internal_notes"), value=lead.internal_notes, height=140)
        save_update = st.form_submit_button(t("save_lead_updates"), use_container_width=True)
        if save_update:
            lead.stage = updated_stage
            lead.disposition_reason = disposition_reason
            lead.assigned_to = assigned_to.strip()
            lead.next_action = next_action.strip()
            lead.internal_notes = internal_notes.strip()
            lead = persist_admin_lead(lead, repository)
            st.success(t("lead_updated"))
            st.rerun()

    render_admin_lead_edit_form(lead, repository)


def render_knowledge_loop() -> None:
    workflow_md = load_markdown(WORKFLOW_PATH)
    business_loop_md = load_markdown(BUSINESS_LOOP_PATH)
    google_sheets_md = load_markdown(GOOGLE_SHEETS_SETUP_PATH)
    playbook_rows = get_playbook_rows(PLAYBOOK_PATH)

    st.info(t("workflow_note"))
    doc_tab, business_tab, sheets_tab, stage_tab, playbook_tab = st.tabs(
        [t("workflow_doc"), t("business_loop_doc"), t("google_sheets_setup"), t("stage_guide"), t("jurisdiction_seeds")]
    )
    with doc_tab:
        st.markdown(workflow_md)
    with business_tab:
        st.markdown(business_loop_md)
    with sheets_tab:
        st.markdown(google_sheets_md)
    with stage_tab:
        render_stage_guide()
    with playbook_tab:
        for row in playbook_rows:
            st.markdown(
                f"""
                <div class="workflow-card">
                    <div style="font-weight:700;color:#12343b;">{row['label']}</div>
                    <div style="margin-top:0.3rem;color:#334b50;">{row['routing_notes']}</div>
                    <div style="margin-top:0.6rem;"><strong>{t("best_fit_pages")}:</strong> {", ".join(row['front_door_pages'])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def suggested_public_base_url() -> str:
    try:
        headers = getattr(st.context, "headers", {})
        host = headers.get("Host", "")
        proto = headers.get("X-Forwarded-Proto", "")
        if host:
            is_local = host.startswith("localhost") or host.startswith("127.0.0.1")
            scheme = proto or ("http" if is_local else "https")
            if host.endswith("streamlit.app"):
                scheme = "https"
            return f"{scheme}://{host}"
    except Exception:
        pass
    return "http://localhost:8503"


def render_launch_kit() -> None:
    st.subheader(t("launch_kit_title"))
    st.caption(t("launch_kit_caption"))

    base_url = st.text_input(t("public_base_url"), value=suggested_public_base_url())
    normalized_base_url = normalize_public_base_url(base_url)
    if normalized_base_url != base_url.strip():
        st.caption(f"{t('public_base_url')}: {normalized_base_url}")
    launch_cols = st.columns(4)
    source = launch_cols[0].text_input(t("campaign_source"), value="wechat_sgv")
    medium = launch_cols[1].text_input(t("campaign_medium"), value="social")
    campaign = launch_cols[2].text_input(t("campaign_name"), value="spring_test")
    embed_mode = launch_cols[3].checkbox(t("embed_mode"), value=False)

    entry_order = [("default", t("default_path")), ("garage", PUBLIC_ENTRY_VARIANTS["garage"]["selector_title"][current_language()]), ("adu", PUBLIC_ENTRY_VARIANTS["adu"]["selector_title"][current_language()]), ("legalization", PUBLIC_ENTRY_VARIANTS["legalization"]["selector_title"][current_language()])]

    st.write(f"**{t('channel_templates')}**")
    for entry_key, label in entry_order:
        link = build_public_url(normalized_base_url, entry_key, source=source, medium=medium, campaign=campaign, embed=embed_mode)
        st.text_input(label, value=link, key=f"launch_link_{entry_key}")

    general_link = build_public_url(normalized_base_url, "default", source=source, medium=medium, campaign=campaign, embed=embed_mode)
    garage_link = build_public_url(normalized_base_url, "garage", source=source, medium=medium, campaign=campaign, embed=embed_mode)

    st.write(f"**{t('share_copy')}**")
    st.text_area(
        t("wechat_share_copy"),
        value=(
            "先做一个物业预筛，再决定值不值得继续花设计费。\n"
            f"{general_link}"
        ),
        height=90,
    )
    st.text_area(
        t("agent_share_copy"),
        value=(
            "If the homeowner wants an early property read before anyone quotes a path, send them here first:\n"
            f"{general_link}"
        ),
        height=90,
    )
    st.text_area(
        t("social_share_copy"),
        value=(
            "Not sure if your garage conversion looks straightforward or complicated? Start here:\n"
            f"{garage_link}"
        ),
        height=90,
    )


def render_view_banner(view_mode: str) -> None:
    if view_mode == "admin":
        st.caption(t("view_admin"))


def render_admin_gate() -> bool:
    if admin_access_granted():
        return True

    st.warning(t("admin_locked"))
    st.caption(t("admin_access_note"))
    with st.form("admin_unlock_form"):
        password = st.text_input(t("admin_password"), type="password")
        submitted = st.form_submit_button(t("unlock_admin"), use_container_width=True)
        if submitted:
            if is_valid_admin_password(password):
                st.session_state["admin_authenticated"] = True
                st.rerun()
            st.error(t("admin_password_invalid"))
    return False


def main() -> None:
    st.set_page_config(
        page_title="Lumanova Living ADU Pre-Screen",
        page_icon="🏠",
        layout="wide",
    )
    inject_css()
    initialize_state()
    sync_source_context_from_query_params()
    repository = get_repository()
    normalize_existing_leads(repository)
    view_mode = current_view_mode()

    language_cols = st.columns([5, 1.2])
    with language_cols[1]:
        selected_language = st.selectbox(
            t("language_label"),
            options=list(LANGUAGE_OPTIONS.keys()),
            index=list(LANGUAGE_OPTIONS.keys()).index(current_language()),
            format_func=lambda item: LANGUAGE_OPTIONS[item],
        )
        if selected_language != current_language():
            st.session_state["language"] = selected_language
            st.rerun()
    render_view_banner(view_mode)

    if view_mode == "admin":
        admin_cols = st.columns([5, 1.2])
        if admin_password_configured():
            if admin_access_granted() and admin_cols[1].button(t("logout_admin"), use_container_width=True):
                st.session_state["admin_authenticated"] = False
                st.rerun()
        else:
            admin_cols[0].warning(t("admin_unprotected"))

        if not render_admin_gate():
            return

    if view_mode == "public" and not is_embed_mode():
        render_public_header()

    if view_mode == "admin":
        hero_title, hero_body = hero_copy(view_mode)
        st.markdown(
            f"""
            <div class="hero-card">
                <div style="font-size:0.9rem;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;color:#315a5d;margin-bottom:0.45rem;">{hero_eyebrow(view_mode)}</div>
                <div class="hero-title">{hero_title}</div>
                <div style="font-size:1rem;color:#31464a;max-width:980px;">
                    {hero_body}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if view_mode == "admin":
        top_cols = st.columns([1, 1, 2])
    elif not is_embed_mode():
        top_cols = st.columns([1, 3])
    else:
        top_cols = st.columns([1, 4])

    if top_cols[0].button(t("reset_screening") if view_mode == "admin" else t("start_over"), use_container_width=True):
        reset_flow()
        st.rerun()

    if view_mode == "admin":
        if top_cols[1].button(t("load_example"), use_container_width=True):
            st.session_state["answers"] = {
                "property_address": "123 Example Ave, Pasadena, CA 91101",
                "brief_goal": "I want to convert my detached garage into a legal rental ADU.",
                "jurisdiction": "pasadena",
                "owner_on_title": "Yes",
                "project_type": "garage_conversion",
                "structure_type": "detached_garage",
                "hillside": "No",
                "basement": "No",
                "addition_without_permit": "No",
                "unpermitted_work": "No",
                "prior_violation": "No",
                "prior_plans": "No",
                "separate_utility_request": "Yes",
            }
            st.session_state["step_index"] = len(QUESTION_FLOW)
            st.session_state["lead_saved"] = False
            st.session_state["show_result"] = False
            st.session_state["contact"] = {
                "full_name": "",
                "email": "",
                "phone": "",
                "wechat_id": "",
                "contact_preference": "No preference",
                "best_contact_time": "",
                "consent_to_contact": "No",
            }
            st.rerun()
        top_cols[2].info(t("prelim_notice"))
    elif not is_embed_mode():
        top_cols[1].caption(t("public_notice"))
    else:
        top_cols[1].caption(t("public_notice"))

    if view_mode == "admin":
        tab_screen, tab_inbox, tab_loop, tab_launch = st.tabs([t("tab_prescreen"), t("tab_inbox"), t("tab_loop"), t("tab_launch")])
    else:
        tab_screen = st.container()
        tab_inbox = None
        tab_loop = None
        tab_launch = None

    with tab_screen:
        render_progress()
        main_col, side_col = st.columns([1.5, 1])
        with main_col:
            with st.container(border=True):
                question = current_question()
                if question is not None:
                    render_question(question)
                else:
                    result = compute_screening(answers_object())
                    if st.session_state["show_result"]:
                        if view_mode == "admin":
                            render_result(result)
                        else:
                            render_public_confirmation(result)
                    else:
                        render_contact_capture(result, repository)
        with side_col:
            with st.container(border=True):
                if view_mode == "admin":
                    st.subheader(t("captured_so_far"))
                    render_answer_summary()
                else:
                    render_public_sidebar()

    if tab_inbox is not None:
        with tab_inbox:
            render_lead_inbox(repository)

    if tab_loop is not None:
        with tab_loop:
            render_knowledge_loop()

    if tab_launch is not None:
        with tab_launch:
            render_launch_kit()


if __name__ == "__main__":
    main()
