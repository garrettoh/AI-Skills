#!/usr/bin/env python3
"""Extract RMM persistence evidence and endpoint indicators from parsed KAPE CSVs."""
from __future__ import annotations

import argparse
import csv
import html
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


TOOLS = {
    "screenconnect": ("screenconnect", "connectwise control"),
    "splashtop": ("splashtop", "srserver.exe", "srservice.exe", "client_spid", "csrsowner"),
    "beyondtrust": ("beyondtrust", "bomgar", "bomgar-scc", "jump client"),
    "anydesk": ("anydesk",),
    "teamviewer": ("teamviewer",),
    "rustdesk": ("rustdesk",),
    "atera": ("atera",),
    "meshcentral": ("meshagent", "meshcentral"),
    "tactical_rmm": ("tacticalrmm", "tactical rmm"),
    "simplehelp": ("simplehelp",),
    "logmein": ("logmein", "gotoassist", "rescueassist"),
    "zoho_assist": ("zoho assist", "zohoassist"),
    "splashtop_sos": ("splashtop sos",),
    "ninjaone": ("ninjaone", "ninjarmm"),
    "action1": ("action1",),
    "connectwise": ("connectwise",),
}

HOST_RE = re.compile(
    r"(?i)(?<![\w-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z]{2,63}(?![\w-])"
)
LABELED_HOST_RE = re.compile(
    r"(?i)\b(?:relay(?: server)?|server|endpoint|host)\s*[:=]\s*"
    r"((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})"
)
IP_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
URL_RE = re.compile(r"(?i)\b(?:https?|relay)://[^\s\"'<>]+")
SCREENCONNECT_H_RE = re.compile(r"(?i)(?:[?&]|\b)h=([^&\s\"'<>]+)")
SPID_RE = re.compile(r"(?i)\b(?:client[_ ]?)?spid\b\s*[:=]\s*[\"']?([a-z0-9._:-]{3,})")
SENSITIVE_QUERY_RE = re.compile(
    r"(?i)([?&](?:x-amz-security-token|x-amz-signature|x-amz-credential|"
    r"token|access_token|signature|password|secret|key|k)=)[^&\s\"']+"
)
NON_DOMAIN_SUFFIXES = {
    "dll", "exe", "sys", "vbs", "bat", "cmd", "ps1", "psm1", "ini", "json",
    "xml", "csv", "txt", "log", "dat", "bin", "pdb", "config", "local", "invalid",
    "manifest", "resources", "cache", "tmp", "bak", "db", "pf",
}

TEXT_FIELDS = {
    "name", "applicationname", "batchvaluename", "batchvaluedata", "valuename", "batchkeypath",
    "eventid", "timecreated", "computer", "username", "provider", "channel",
    "mapdescription", "payload", "payloaddata1", "payloaddata2", "payloaddata3",
    "payloaddata4", "payloaddata5", "payloaddata6", "executableinfo", "description",
    "eventdata", "details", "imagepath", "servicename", "value", "valuedata",
    "keypath", "filename", "filepath", "fullpath", "displayname", "displayversion",
}


def safe_resolve(path: Path) -> Path:
    return path.expanduser().resolve()


def source_files(root: Path):
    if root.is_file():
        if root.suffix.casefold() == ".csv":
            yield root
        return
    yield from sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.casefold() == ".csv")


def selected_text(row):
    chunks = []
    for key, value in row.items():
        if value is None or not str(value).strip():
            continue
        if key.casefold() in TEXT_FIELDS or re.search(r"spid|csrs|udid|dcode|client.?ip", key, re.I):
            chunks.append((key, html.unescape(str(value))))
    return chunks


def detect_tools(chunks):
    combined = "\n".join(value for _, value in chunks).casefold()
    return [name for name, terms in TOOLS.items() if any(term in combined for term in terms)]


def extract_indicators(tool, chunks):
    domains = {}
    ips = {}
    matched_fields = set()
    hosts_for_classifier = set()
    for field, raw in chunks:
        text = html.unescape(raw)
        field_lower = field.casefold()

        # Explicit URL/relay fields are more reliable than an arbitrary hostname in a log.
        for match in URL_RE.finditer(text):
            candidate = match.group(0).rstrip(".,);]}")
            try:
                host = urlsplit(candidate).hostname
            except ValueError:
                host = None
            if host:
                add_host(host, field, domains, ips, matched_fields)
                hosts_for_classifier.add(host.casefold())

        if tool == "screenconnect":
            for match in SCREENCONNECT_H_RE.finditer(text):
                host_value = unquote(match.group(1)).strip(". ,;)]}")
                try:
                    parsed = urlsplit("//" + host_value)
                    host = parsed.hostname
                except ValueError:
                    host = None
                if not host:
                    host_match = HOST_RE.search(host_value)
                    host = host_match.group(0) if host_match else None
                if host:
                    add_host(host, field, domains, ips, matched_fields)
                    hosts_for_classifier.add(host.casefold())

        endpoint_context = bool(re.search(r"relay|server|endpoint|\bhost\b|https?://|\bh=", text, re.I))
        for match in LABELED_HOST_RE.finditer(text):
            host = match.group(1).casefold()
            add_host(host, field, domains, ips, matched_fields)
            if tool == "screenconnect":
                hosts_for_classifier.add(host)

        if tool != "screenconnect" and field_lower not in {"computer", "computername", "username", "provider"}:
            # A hostname embedded in an RMM client/service label or install path is useful
            # tenant context even when the export has no network event.
            for match in HOST_RE.finditer(text):
                host = match.group(0).casefold()
                if host not in {"microsoft.com", "windows.com"} and not host.endswith(".windows.com"):
                    add_host(host, field, domains, ips, matched_fields)
            if endpoint_context:
                for match in IP_RE.finditer(text):
                    try:
                        ipaddress.IPv4Address(match.group(0))
                    except ipaddress.AddressValueError:
                        continue
                    ips.setdefault(match.group(0), set()).add(field)
                    matched_fields.add(field)

    return domains, ips, hosts_for_classifier, matched_fields


def add_host(host, field, domains, ips, matched_fields):
    host = host.strip().rstrip(".").casefold()
    try:
        ipaddress.ip_address(host)
        ips.setdefault(host, set()).add(field)
    except ValueError:
        if HOST_RE.fullmatch(host) and host.rsplit(".", 1)[-1] not in NON_DOMAIN_SUFFIXES:
            domains.setdefault(host, set()).add(field)
    matched_fields.add(field)


def classify_record(tool, row, text):
    event_id = str(row.get("EventId", "")).strip()
    lower = text.casefold()
    if event_id in {"7045", "4697"} or "service was installed" in lower or "new service was installed" in lower:
        return "service-install"
    if tool == "screenconnect" and ("session connected" in lower or "connected\n" in lower or "network connection to host created successfully" in lower):
        return "remote-session-or-connection"
    if event_id == "7036" or "service entered the running state" in lower:
        return "service-state"
    if "scheduled task" in lower or "taskname" in lower:
        return "scheduled-task"
    if any(term in lower for term in ("appcompatcache", "amcache", "prefetch", "shellactivity", "uninstall")):
        return "execution-or-install-artifact"
    return "rmm-reference"


def extract_identifiers(tool, row, chunks):
    found = {}
    identifier_names = re.compile(r"(?i)^(?:client[_ ]?)?spid$|^(?:csrsowner|csrsteamname|dcode|client[_ ]?ip|device[_ ]?name|udid)$")
    value_names = ("ValueName", "BatchValueName", "Name", "RegistryValueName")
    data_names = ("ValueData", "BatchValueData", "Data", "RegistryValueData")
    for name_key in value_names:
        name = str(row.get(name_key, "")).strip()
        if not identifier_names.fullmatch(name):
            continue
        for data_key in data_names:
            value = str(row.get(data_key, "")).strip()
            if value and len(value) <= 300:
                found[f"{name}:{value}"] = True
                break
    for key, value in chunks:
        # Field-name based extraction avoids mistaking unrelated UUIDs for a Splashtop SPID.
        if re.search(r"spid|csrsowner|csrsteamname|dcode|client.?ip|device.?name|udid", key, re.I):
            value = str(value).strip()
            if value and len(value) <= 300:
                found[f"{key}:{value}"] = True
        for match in SPID_RE.finditer(str(value)):
            found[f"SPID:{match.group(1)}"] = True
        for match in re.finditer(
            r"(?i)(Client[_ ]?SPID|CSRSOwner|CSRSTeamName|DCode|Client[_ ]?IP|Device[_ ]?Name|UDID)"
            r"[^A-Za-z0-9]{1,20}(?:#text\s*[:=]\s*)?[\"']?([^,}\"'\s]{3,300})",
            str(value),
        ):
            found[f"{match.group(1)}:{match.group(2)}"] = True
    return sorted(found)


def safe_excerpt(value, limit=360):
    text = SENSITIVE_QUERY_RE.sub(r"\1[REDACTED]", html.unescape(str(value)))
    return text[:limit] + ("…" if len(text) > limit else "")


def record_object(path, number, row):
    chunks = selected_text(row)
    tools = detect_tools(chunks)
    if not tools:
        return []
    out = []
    for tool in tools:
        domains, ips, hosts, matched_fields = extract_indicators(tool, chunks)
        text = "\n".join(value for _, value in chunks)
        event_id = str(row.get("EventId", ""))
        domains_list = []
        for domain, fields in sorted(domains.items()):
            tier = None
            if tool == "screenconnect":
                tier = "vendor-hosted-relay-medium-review" if domain.endswith(".screenconnect.com") else "custom-or-self-hosted-high-review"
            domains_list.append({"value": domain, "fields": sorted(fields), "screenconnect_triage": tier})
        ips_list = [{"value": ip, "fields": sorted(fields)} for ip, fields in sorted(ips.items())]
        identifier_list = extract_identifiers(tool, row, chunks)
        service_or_path_fields = [
            {"field": key, "value": safe_excerpt(value)}
            for key, value in chunks
            if re.search(r"path|image|service|displayname|filename|filepath|keypath|executableinfo", key, re.I)
            and re.search(r"\\|/|\.exe|\.dll|\.sys", value, re.I)
        ]
        evidence_excerpt = [
            {"field": key, "value": safe_excerpt(value, 520)}
            for key, value in chunks
            if re.search(r"screenconnect|connectwise|splashtop|beyondtrust|bomgar|relay|session|spid|csrs|support\.[a-z]|\bh=", value, re.I)
        ][:5]
        if not (domains_list or ips_list or identifier_list or service_or_path_fields or text):
            continue
        out.append({
            "tool": tool,
            "evidence_type": classify_record(tool, row, text),
            "source": str(path),
            "record": number,
            "event_id": event_id,
            "timestamp_raw": row.get("TimeCreated", row.get("Timestamp", "")),
            "host": row.get("Computer", row.get("ComputerName", "")),
            "user": row.get("UserName", ""),
            "domains": domains_list,
            "ips": ips_list,
            "identifiers": identifier_list,
            "paths_and_service_values": service_or_path_fields,
            "evidence_excerpt": evidence_excerpt,
            "matched_fields": sorted(matched_fields),
            "triage_note": (
                "A *.screenconnect.com relay is vendor-hosted; treat as medium-priority review. "
                "An unrecognized custom tenant/self-hosted endpoint is high-priority and may be malicious; "
                "confirm authorization before making a verdict."
                if tool == "screenconnect" else
                "RMM product evidence is dual-use. Correlate install, service/task persistence, session, "
                "identity and network records with approved support activity."
            ),
        })
    return out


def scan(root):
    errors = []
    count_files = 0
    count_records = 0
    count_matches = 0
    for path in source_files(root):
        count_files += 1
        try:
            with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
                reader = csv.DictReader(stream)
                for number, row in enumerate(reader, 2):
                    count_records += 1
                    for item in record_object(path, number, row):
                        count_matches += 1
                        yield item
        except (OSError, csv.Error, UnicodeError) as exc:
            errors.append({"source": str(path), "error": str(exc)})
    scan.stats = {"files": count_files, "records": count_records, "matches": count_matches, "errors": errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="KAPE parse root or one EvtxECmd CSV")
    parser.add_argument("--output", type=Path, help="Write JSONL outside the evidence root (default: stdout)")
    args = parser.parse_args(argv)
    root = safe_resolve(args.root)
    if not root.exists():
        parser.error(f"input does not exist: {root}")
    output = safe_resolve(args.output) if args.output else None
    if output:
        protected = root if root.is_dir() else root.parent
        try:
            output.relative_to(protected)
        except ValueError:
            pass
        else:
            parser.error("--output must be outside the evidence root")
        output.parent.mkdir(parents=True, exist_ok=True)
    destination = output.open("w", encoding="utf-8", newline="") if output else sys.stdout
    try:
        for item in scan(root):
            destination.write(json.dumps(item, ensure_ascii=False) + "\n")
    finally:
        if output:
            destination.close()
    stats = scan.stats
    print(
        f"Scanned {stats['records']} CSV records in {stats['files']} files; "
        f"emitted {stats['matches']} RMM evidence records; errors: {len(stats['errors'])}.",
        file=sys.stderr,
    )
    for error in stats["errors"]:
        print(f"ERROR {error['source']}: {error['error']}", file=sys.stderr)
    return 2 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
