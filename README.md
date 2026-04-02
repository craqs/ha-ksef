# KSeF Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant integration for the Polish [KSeF](https://ksef.mf.gov.pl) (Krajowy System e-Faktur) e-invoice system. Exposes your invoices as sensor entities so you can build dashboards, automations, and notifications around your invoicing activity.

## Features

- **4 sensor entities** per configured NIP:
  - Issued invoices — this month
  - Issued invoices — last month
  - Received invoices — this month
  - Received invoices — last month
- Each sensor's **state** = invoice count
- Each sensor's **attributes** include:
  - `total_net`, `total_gross`, `total_vat`, `currency`
  - `invoices` — list of invoice details (number, date, seller, buyer, amounts)
- Data refreshes every **30 minutes**
- Tokens are **cached** — no re-authentication needed between restarts
- Supports both **production** and **test** KSeF environments

## Installation via HACS

1. Open HACS → **Integrations**
2. Click the three-dot menu → **Custom repositories**
3. Add `https://github.com/craqs/ha-ksef` as an **Integration**
4. Search for **KSeF** and install
5. Restart Home Assistant

## Manual Installation

Copy the `custom_components/ksef` folder into your HA `config/custom_components/` directory and restart.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **KSeF**
3. Enter your **NIP** (10-digit tax ID) and **KSeF Token**
4. Choose whether to use the **production** or test environment
5. Click Submit — HA will verify your credentials immediately

### Obtaining a KSeF Token

1. Log in at [ksef.mf.gov.pl](https://ksef.mf.gov.pl) (or [ksef-test.mf.gov.pl](https://ksef-test.mf.gov.pl) for test)
2. Go to **Account → API Tokens**
3. Generate a new token with at least the **InvoiceRead** permission
4. Copy the full token string

## Example Dashboard Card

```yaml
type: entities
title: KSeF Invoices
entities:
  - entity: sensor.ksef_issued_this_month
    name: Issued this month
  - entity: sensor.ksef_received_this_month
    name: Received this month
  - entity: sensor.ksef_issued_last_month
    name: Issued last month
  - entity: sensor.ksef_received_last_month
    name: Received last month
```

## Example Automation — Notify on New Received Invoice

```yaml
alias: "KSeF: new invoice received"
trigger:
  - platform: state
    entity_id: sensor.ksef_received_this_month
condition:
  - condition: template
    value_template: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
action:
  - service: notify.mobile_app
    data:
      title: "New invoice received"
      message: >
        You have {{ states('sensor.ksef_received_this_month') }} invoices
        this month totalling
        {{ state_attr('sensor.ksef_received_this_month', 'total_gross') }} PLN.
```

## Sensor Attributes Example

```yaml
# sensor.ksef_received_this_month
state: 3
attributes:
  total_net: 2500.00
  total_gross: 3075.00
  total_vat: 575.00
  currency: PLN
  invoices:
    - ksef_number: "7743164091-20260401-..."
      invoice_number: "FA/001/2026"
      date: "2026-04-01"
      seller: "Seller Company Sp. z o.o."
      buyer: "Your Company Name"
      gross: 1230.00
      currency: PLN
      type: Vat
```

## License

MIT
