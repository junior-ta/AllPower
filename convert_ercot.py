"""Convert the current ERCOT native-load workbook to AllPower's hourly CSV.

Run from the AllPower repository root:
    python3 convert_ercot.py
Requires pandas and openpyxl. Original workbook is never modified.

Timestamp denotes interval END in UTC. ERCOT's hour-ending label H maps
to the local interval starting H-1; add one elapsed hour AFTER conversion.
This handles HE24 and spring HE02 (followed by HE04) without filling data.
Ambiguous autumn hours are deliberately rejected for manual review.
Reference: https://github.com/gridstatus/gridstatus/blob/main/gridstatus/ercot.py
(_read_html_display and _process_post_settlements_load_data).
"""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def convert(source, destination):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('Output must not overwrite the source workbook.')
    if destination.exists():
        raise ValueError(f'Output already exists: {destination}. Rename it before rerunning.')
    df = pd.read_excel(source, sheet_name='Native Load Report', engine='openpyxl')
    required = {'Hour Ending', 'ERCOT'}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required - set(df.columns)}')
    if df.empty:
        raise ValueError('Workbook has no data rows.')
    if df[['Hour Ending', 'ERCOT']].isna().any().any():
        raise ValueError('Missing timestamp or demand value. No rows were dropped.')

    labels = df['Hour Ending'].astype(str).str.strip()
    parts = labels.str.extract(r'^(\d{2}/\d{2}/\d{4}) (\d{2}):00$')
    if parts.isna().any().any():
        raise ValueError('Unexpected hour-ending format; review the workbook (including autumn DST markers).')
    dates = pd.to_datetime(parts[0], format='%m/%d/%Y', errors='raise')
    hours = parts[1].astype(int)
    if not hours.between(1, 24).all():
        raise ValueError('Hour-ending labels must be between 01 and 24.')
    starts = dates + pd.to_timedelta(hours - 1, unit='h')
    # Raise rather than infer ambiguous fall hours or fabricate missing hours.
    utc_ends = (starts.dt.tz_localize('America/Chicago', ambiguous='raise',
                                    nonexistent='raise').dt.tz_convert('UTC')
                + pd.Timedelta(hours=1))
    demand = pd.to_numeric(df['ERCOT'], errors='raise')
    if not ((demand > 0) & (demand < 200000)).all():
        raise ValueError('Demand is missing, nonfinite, or outside the training loader bounds.')
    out = pd.DataFrame({'timestamp': utc_ends, 'demand_mw': demand})
    if out['timestamp'].duplicated().any():
        raise ValueError('Duplicate UTC timestamps. No rows were dropped.')
    out = out.sort_values('timestamp').reset_index(drop=True)
    gaps = out['timestamp'].diff().iloc[1:] != pd.Timedelta(hours=1)
    if gaps.any():
        raise ValueError(f'{int(gaps.sum())} non-hourly gaps found. Nothing was filled or saved.')
    report = {
        'source': source.name,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_url': 'https://www.ercot.com/gridinfo/load/load_hist',
        'source_timezone': 'America/Chicago',
        'timestamp_meaning': 'interval end, UTC',
        'source_rows': len(df), 'output_rows': len(out),
        'first_timestamp': out['timestamp'].iloc[0].isoformat(),
        'last_timestamp': out['timestamp'].iloc[-1].isoformat(),
        'missing_required_values': 0, 'duplicate_timestamps': 0,
        'non_hourly_gaps': 0, 'invalid_demand_values': 0,
        'rows_dropped_or_filled': 0,
        'demand_min_mw': float(demand.min()),
        'demand_max_mw': float(demand.max()),
    }
    out['timestamp'] = out['timestamp'].map(lambda t: t.isoformat())
    destination.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(destination, index=False)
    destination.with_suffix('.quality.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(out):,} rows; no missing values, duplicates, or hourly gaps.')
    print(f'Saved: {destination}')
    print(f'Quality report: {destination.with_suffix(".quality.json")}')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', nargs='?', default='data/raw/Native_Load_2026.xlsx')
    parser.add_argument('--out', default='data/ercot_hourly.csv')
    args = parser.parse_args()
    try:
        convert(args.source, args.out)
    except Exception as exc:
        parser.exit(1, f'STOP: {exc}\n')
