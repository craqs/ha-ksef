DOMAIN = "ksef"

CONF_NIP = "nip"
CONF_TOKEN = "token"
CONF_USE_PROD = "use_prod"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"

DEFAULT_SCAN_INTERVAL = 30  # minutes

SENSOR_TYPES = [
    # (key, name, subject_type, period)
    ("issued_this_month",    "Issued This Month",    "Subject1", "this"),
    ("issued_last_month",    "Issued Last Month",    "Subject1", "last"),
    ("received_this_month",  "Received This Month",  "Subject2", "this"),
    ("received_last_month",  "Received Last Month",  "Subject2", "last"),
]
