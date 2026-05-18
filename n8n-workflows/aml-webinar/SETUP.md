# AML Webinar n8n Workflows Setup

These workflows replicate the Zapier integrations for the AML Webinar Stealth funnel, moving data from Aevent to GoHighLevel (PAP).

## Workflows Included

| # | Workflow | Aevent Trigger | GHL Tags Applied |
|---|----------|----------------|------------------|
| 01 | Registrants | Registration | `AML-Webinar-Registrant`, `AML-Stealth` |
| 02 | Attendees | Attendance | `AML-Webinar-Attendee`, `AML-Stealth` |
| 03 | CTA1 Clicker | CTA1 Click | `AML-Webinar-CTA1-Clicked`, `AML-Hot-Lead` |
| 04 | CTA2 Clicker | CTA2 Click | `AML-Webinar-CTA2-Clicked`, `AML-Hot-Lead` |
| 05 | CTA3 Clicker | CTA3 Click | `AML-Webinar-CTA3-Clicked`, `AML-Hot-Lead` |
| 06 | Left Before CTA | Left <120mins | `AML-Webinar-Left-Before-CTA`, `AML-Nurture-Needed` |
| 07 | No Show | No Show | `AML-Webinar-No-Show`, `AML-Re-Engage` |
| 08 | Stayed Till CTA | Stayed 121+mins | `AML-Webinar-Stayed-Till-CTA`, `AML-Warm-Lead` |

## Pre-Requisites

1. **GHL API Credentials** - Create an HTTP Header Auth credential in n8n:
   - Name: `GHL API Key`
   - Header Name: `Authorization`
   - Header Value: `Bearer YOUR_GHL_API_KEY`

2. **Aevent Webhook Setup** - Configure Aevent to send webhooks to your n8n instance for each event type.

## Import Instructions

1. Open your n8n instance
2. Go to **Workflows** > **Import from File**
3. Import each JSON file from this folder
4. Configure the **GHL API Key** credential in each workflow
5. Update webhook URLs in Aevent to point to each workflow's webhook endpoint
6. Activate each workflow

## Webhook Endpoints (after import)

After importing, n8n will generate webhook URLs. Copy these to Aevent:

- Registration: `https://your-n8n.com/webhook/aml-webinar-registrant`
- Attendance: `https://your-n8n.com/webhook/aml-webinar-attendee`
- CTA1 Click: `https://your-n8n.com/webhook/aml-webinar-cta1`
- CTA2 Click: `https://your-n8n.com/webhook/aml-webinar-cta2`
- CTA3 Click: `https://your-n8n.com/webhook/aml-webinar-cta3`
- Left Early: `https://your-n8n.com/webhook/aml-webinar-left-early`
- No Show: `https://your-n8n.com/webhook/aml-webinar-no-show`
- Stayed Till CTA: `https://your-n8n.com/webhook/aml-webinar-stayed-till-cta`

## Expected Aevent Webhook Payload

Each Aevent webhook should include:

```json
{
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+1234567890",
  "watch_time": 125
}
```

## Custom Fields in GHL

These workflows create/update the following custom fields:

- `webinar_registered_at` - Timestamp of registration
- `webinar_attended_at` - Timestamp of attendance
- `webinar_name` - "AML Webinar Stealth"
- `webinar_watch_time` - Minutes watched
- `cta1_clicked_at` / `cta2_clicked_at` / `cta3_clicked_at` - CTA click timestamps
- `cta_engagement` - Which CTA was clicked
- `webinar_left_at` - Timestamp when left early
- `webinar_dropoff_zone` - "Before-CTA" for early leavers
- `no_show_recorded_at` - Timestamp of no-show record
- `webinar_status` - "No-Show" for no-shows
- `stayed_till_cta_at` - Timestamp for full watchers
- `webinar_engagement` - "Full-Watch-To-CTA"

## Workflow Logic

Each workflow follows this pattern:

1. **Webhook Trigger** - Receives data from Aevent
2. **Lookup Contact** - Searches GHL for existing contact by email
3. **Branch** - If contact exists → update; if not → create new
4. **Update/Create** - Applies appropriate tags and custom fields

## Notes

- Workflows are imported in **inactive** state - activate after configuring credentials
- Test with a single workflow before activating all
- The GHL API v1 `/contacts/lookup` endpoint is used for finding existing contacts
- Tags are additive - existing tags on the contact are preserved
