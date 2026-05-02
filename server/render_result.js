// ── render result ─────────────────────────────────────
const TYPE_LABELS = {
  invoice:        'Rechnung',
  dunning:        'Mahnung',
  penalty_notice: 'Strafverfügung',
  offer:          'Angebot',
  contract:       'Vertrag',
  note:           'Notiz',
  unknown:        'Unbekannt',
};

const FIELD_LABELS = {
  customer_name:              'Empfänger',
  invoice_number:             'Rechnungs-Nr.',
  invoice_date:               'Datum',
  document_date:              'Datum',
  due_date:                   'Fällig am',
  amount_total:               'Gesamtbetrag',
  amount_due:                 'Offener Betrag',
  amount_tax:                 'MwSt.',
  currency:                   'Währung',
  iban:                       'IBAN',
  reminder_level:             'Mahnstufe',
  vehicle_plate:              'Kennzeichen',
  authority_name:             'Behörde',
  case_number:                'Aktenzeichen',
  incident_date:              'Tatdatum',
  referenced_invoice_number:  'Urspr. Rechnung',
  reference_number:           'Referenz',
};

// Felder die im UI angezeigt werden — in dieser Reihenfolge
const DISPLAY_FIELDS = [
  'amount_total', 'amount_due',
  'due_date', 'invoice_date', 'document_date',
  'invoice_number', 'case_number', 'reference_number', 'referenced_invoice_number',
  'iban',
  'vehicle_plate', 'authority_name',
];

// Confidence → Sprache
function entityConfidenceText(confidence) {
  if (confidence >= 0.75) return 'Soll ich das zuordnen?';
  if (confidence >= 0.45) return 'Vermutlich richtig. Stimmt das?';
  return 'Für wen ist das?';
}

// IBAN confidence_note → verständlicher Hinweis
function ibanHint(note) {
  if (!note) return null;
  if (note.includes('truncated') || note.includes('manual check')) {
    return 'IBAN unvollständig — bitte manuell prüfen.';
  }
  if (note.includes('validation failed')) {
    return 'IBAN konnte nicht geprüft werden.';
  }
  return null;
}

function renderResult(data) {
  const typeKey = data.detected_document_type || 'unknown';
  $('r-title').textContent = 'Erkannt.';
  $('r-type').textContent = TYPE_LABELS[typeKey] || typeKey;

  const container = $('r-fields');
  container.innerHTML = '';

  // Nur definierte Felder, in festgelegter Reihenfolge, confidence >= 0.40
  const fieldMap = {};
  (data.extracted_fields || []).forEach(f => { fieldMap[f.field_key] = f; });

  let ibanWarning = null;

  DISPLAY_FIELDS.forEach(key => {
    const f = fieldMap[key];
    if (!f || f.confidence < 0.40) return;

    // IBAN: technische Note in verständlichen Hinweis übersetzen
    if (key === 'iban') {
      const hint = ibanHint(f.confidence_note);
      if (hint) ibanWarning = hint;
      // IBAN nur zeigen wenn confidence >= 0.80 (valide)
      if (f.confidence < 0.80) return;
    }

    const label = FIELD_LABELS[key] || key;
    const row = document.createElement('div');
    row.className = 'field-row';
    row.innerHTML = `
      <span class="field-key">${label}</span>
      <span class="field-val">${f.field_value}</span>
    `;
    container.appendChild(row);
  });

  // Entity suggestion — Sprache statt Prozent
  const s = data.entity_suggestion;
  if (s && s.suggested_entity_name && s.confidence >= 0.40) {
    $('r-entity').style.display = 'block';
    $('r-entity-name').textContent = s.suggested_entity_name;
    $('r-entity-conf').textContent = entityConfidenceText(s.confidence);
  } else if (s && (!s.suggested_entity_id || s.confidence < 0.40)) {
    $('r-entity').style.display = 'block';
    $('r-entity-name').textContent = '—';
    $('r-entity-conf').textContent = 'Für wen ist das?';
  }

  // Review banner — nur IBAN-Warnung oder review_required ohne technischen Text
  const showReview = ibanWarning || (s && s.review_required && typeKey === 'unknown');
  if (showReview) {
    $('r-review').style.display = 'flex';
    $('r-review-text').textContent = ibanWarning || 'Bitte kurz prüfen.';
  } else {
    $('r-review').style.display = 'none';
  }
}
