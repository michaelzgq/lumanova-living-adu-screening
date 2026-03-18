const SHEET_NAME = 'Leads';
const SHARED_TOKEN = 'replace-me';

function doPost(e) {
  try {
    const token = (e && e.parameter && e.parameter.token) || '';
    if (!token || token !== SHARED_TOKEN) {
      return jsonResponse({ ok: false, error: 'unauthorized' }, 401);
    }

    const rawBody = (e && e.postData && e.postData.contents) || '';
    if (!rawBody) {
      return jsonResponse({ ok: false, error: 'missing body' }, 400);
    }

    const payload = JSON.parse(rawBody);
    const lead = payload.lead || {};
    const answers = lead.answers || {};
    const result = lead.result || {};

    const sheet = getOrCreateSheet_();
    ensureHeaderRow_(sheet);

    sheet.appendRow([
      payload.sent_at || '',
      payload.event_type || '',
      lead.id || '',
      lead.created_at || '',
      lead.last_updated_at || '',
      answers.full_name || '',
      answers.email || '',
      answers.phone || '',
      answers.wechat_id || '',
      answers.contact_preference || '',
      answers.best_contact_time || '',
      answers.property_address || '',
      answers.brief_goal || '',
      answers.jurisdiction || '',
      answers.owner_on_title || '',
      answers.project_type || '',
      answers.structure_type || '',
      answers.hillside || '',
      answers.basement || '',
      answers.addition_without_permit || '',
      answers.unpermitted_work || '',
      answers.prior_violation || '',
      answers.prior_plans || '',
      answers.separate_utility_request || '',
      result.recommended_path || '',
      result.risk_tier || '',
      result.recommended_service || '',
      lead.stage || '',
      lead.disposition_reason || '',
      lead.assigned_to || '',
      lead.next_action || '',
      answers.source_tag || '',
      answers.utm_source || '',
      answers.utm_medium || '',
      answers.utm_campaign || '',
      lead.external_sync_status || '',
      JSON.stringify(payload),
    ]);

    return jsonResponse({ ok: true }, 200);
  } catch (error) {
    return jsonResponse({ ok: false, error: String(error) }, 500);
  }
}

function getOrCreateSheet_() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = spreadsheet.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(SHEET_NAME);
  }
  return sheet;
}

function ensureHeaderRow_(sheet) {
  if (sheet.getLastRow() > 0) {
    return;
  }

  sheet.appendRow([
    'received_at',
    'event_type',
    'lead_id',
    'created_at',
    'last_updated_at',
    'full_name',
    'email',
    'phone',
    'wechat_id',
    'contact_preference',
    'best_contact_time',
    'property_address',
    'brief_goal',
    'jurisdiction',
    'owner_on_title',
    'project_type',
    'structure_type',
    'hillside',
    'basement',
    'addition_without_permit',
    'unpermitted_work',
    'prior_violation',
    'prior_plans',
    'separate_utility_request',
    'recommended_path',
    'risk_tier',
    'recommended_service',
    'stage',
    'disposition_reason',
    'assigned_to',
    'next_action',
    'source_tag',
    'utm_source',
    'utm_medium',
    'utm_campaign',
    'external_sync_status',
    'raw_payload_json',
  ]);
}

function jsonResponse(payload, statusCode) {
  const output = ContentService.createTextOutput(JSON.stringify(payload));
  output.setMimeType(ContentService.MimeType.JSON);
  return output;
}
