# Kópavogur Waste Collection for Home Assistant

Custom Home Assistant integration for Kópavogur sorphirðudagatal.

## Install manually

Copy `custom_components/kopavogur_waste` into your Home Assistant `/config/custom_components/` folder and restart Home Assistant.

Then go to **Settings → Devices & services → Add integration → Kópavogur Waste Collection** and enter your address.

## HACS custom repository

1. Put this repository on GitHub.
2. In HACS: **Integrations → three dots → Custom repositories**.
3. Add the GitHub repo URL and choose category **Integration**.
4. Install and restart Home Assistant.

## What it creates

For each waste type returned by Kópavogur it creates:

- next pickup date sensor
- days until pickup sensor

## Notes

The pickup endpoint is:

`https://www.kopavogur.is/_/moya/garbage-collection/api/pickup?location=<id>&limit=0`

Address lookup on the public site may change. This integration tries several likely lookup endpoints and includes manual setup fallback using the `location` id.
