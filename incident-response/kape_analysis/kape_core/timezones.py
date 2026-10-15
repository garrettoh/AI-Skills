"""Shared timezone policy: UTC correlation, selectable presentation, explicit local sources."""
import json
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

SETTINGS = Path(__file__).with_name('settings.json')


@lru_cache(maxsize=128)
def zone(name):
    name = str(name).strip()
    if name.upper() in {'UTC', 'GMT', 'Z'}:
        return timezone.utc
    match = re.fullmatch(r'(?:UTC|GMT)?([+-])(\d{2}):(\d{2})', name, re.I)
    if match:
        hours, minutes = int(match[2]), int(match[3])
        if hours > 23 or minutes > 59:
            raise ValueError(f'Invalid UTC offset: {name}')
        return timezone((1 if match[1] == '+' else -1) * timedelta(hours=hours, minutes=minutes))
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f'Unknown timezone {name!r}. Use an IANA name such as America/Los_Angeles, UTC, or +05:30. Named zones require system timezone data or Python tzdata.') from exc


def list_zones():
    return sorted({'UTC', *available_timezones()})


def default_timezone(settings=SETTINGS):
    path = Path(settings)
    if not path.exists():
        return 'UTC'
    name = json.loads(path.read_text(encoding='utf-8-sig')).get('display_timezone', 'UTC')
    zone(name)
    return name


def display_timestamp(utc, name):
    if not utc:
        return None
    return datetime.fromisoformat(utc.replace('Z', '+00:00')).astimezone(zone(name)).isoformat(timespec='microseconds')


def source_rules(values):
    result = {}
    for value in values or []:
        if '=' not in value or '.' not in value.split('=', 1)[0]:
            raise ValueError('--source-timezone requires FAMILY.FIELD=ZONE (wildcards allowed)')
        key, name = value.split('=', 1)
        if not key.strip() or not name.strip():
            raise ValueError('Empty source timezone mapping')
        zone(name)
        result[key.casefold()] = name
    return result


class TimestampPolicy:
    def __init__(self, overrides=None, assume_utc=False):
        self.overrides = overrides or {}
        self.assume_utc = assume_utc
        for name in self.overrides.values():
            zone(name)

    def resolve(self, raw, family, field, verified=False, basis=None):
        try:
            value = datetime.fromisoformat(str(raw).strip().replace('Z', '+00:00'))
        except (ValueError, TypeError, OverflowError):
            return None, 'missing or unparseable timestamp'
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).isoformat(timespec='microseconds'), 'explicit offset in original timestamp'
        family, field = family.casefold(), field.casefold()
        chosen = next((self.overrides[k] for k in (family+'.'+field, family+'.*', '*.'+field, '*.*') if k in self.overrides), None)
        reason = f'user-specified source timezone: {chosen}' if chosen else basis
        if not chosen and verified:
            chosen = 'UTC'
            reason = reason or 'verified UTC export field'
        if not chosen and self.assume_utc:
            chosen, reason = 'UTC', 'user assumed UTC for unverified naive timestamp'
        if not chosen:
            return None, 'source timezone unverified; explicit source mapping required'
        tz = zone(chosen)
        if isinstance(tz, timezone):
            return value.replace(tzinfo=tz).astimezone(timezone.utc).isoformat(timespec='microseconds'), reason
        # A local clock time in a DST gap or repeated hour has no unique UTC instant.
        candidates = set()
        for fold in (0, 1):
            aware = value.replace(tzinfo=tz, fold=fold)
            utc = aware.astimezone(timezone.utc)
            if utc.astimezone(tz).replace(tzinfo=None) == value:
                candidates.add(utc.isoformat(timespec='microseconds'))
        if len(candidates) != 1:
            return None, f'{"ambiguous" if candidates else "nonexistent"} local time in {chosen}; supply a known UTC offset'
        return candidates.pop(), reason
