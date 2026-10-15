# Timestamp policy and timezone selection

UTC is the canonical correlation and sorting clock. Reports and timeline exports additionally display the chosen timezone. Raw timestamps and field names are retained; Python normalizes to microsecond precision while raw text retains original precision. Evidence is never rewritten.

## Verified export fields

Reviewed Eric Zimmerman public source on 2026-10-15. These defaults apply to standard exports, not arbitrarily transformed third-party CSVs.

| Artifact | Verified UTC fields / basis |
|---|---|
| EvtxECmd | TimeCreated, EVTX SystemTime |
| PECmd | Run times and source file times; Prefetch Helpers.FromFileTime uses FromFileTimeUtc |
| AmcacheParser | File/key last write and LinkDate; InstallDate is not automatically interpreted |
| AppCompatCacheParser | LastModifiedTimeUTC, explicitly converted to UTC |
| MFTECmd | NTFS SI/FN timestamps and USN UpdateTimestamp |
| RBCmd | DeletedOn, ToUniversalTime before export |
| LECmd / JLECmd | Target and source file times; DestList creation/modified timestamps |
| SrumECmd | Timestamp explicitly marked UTC; connection/start/end/event file times converted to UTC |
| WxTCmd | Activity and package Unix timestamps converted to UTC |
| RECmd | Hive key LastWriteTimestamp; plugin payload timestamps require individual verification |
| SBECmd | Export timezone is selectable. Naive ShellBags fields require explicit source mapping unless an explicit offset is present. |

Primary source references: [Prefetch helpers](https://github.com/EricZimmerman/Prefetch/blob/master/Prefetch/Helpers.cs), [AppCompatCache](https://github.com/EricZimmerman/AppCompatCacheParser), [Amcache](https://github.com/EricZimmerman/AmcacheParser), [MFT](https://github.com/EricZimmerman/MFT), [RBCmd](https://github.com/EricZimmerman/RBCmd), [Lnk](https://github.com/EricZimmerman/Lnk), [JumpList](https://github.com/EricZimmerman/JumpList), [SRUM](https://github.com/EricZimmerman/Srum/blob/master/SrumData/Srum.cs), [WxTCmd](https://github.com/EricZimmerman/WxTCmd/blob/master/WxTCmd/Program.cs), [Registry](https://github.com/EricZimmerman/Registry), [RECmd](https://github.com/EricZimmerman/RECmd), [SBECmd example export timezone](https://github.com/EricZimmerman/Issues/issues/160). [Microsoft file time conventions](https://learn.microsoft.com/en-us/windows/win32/sysinfo/file-times) distinguish NTFS UTC from FAT local times.

## Select a timezone

Installation: `python scripts/install.py --timezone America/Los_Angeles` or PowerShell `./scripts/install.ps1 -Timezone America/Los_Angeles`. Reinstallation preserves the existing preference when omitted. The default for a new installation is UTC.

Analysis: append `--timezone Asia/Kolkata` to investigate.py or correlate_timeline.py. Use `--list-timezones` to list available IANA names. UTC and fixed offsets such as `+05:30` also work. Named zones require system timezone data or Python's tzdata package. No packages are silently installed.

The main orchestrator saves case-settings.json. Priority is analysis option, saved case preference, installation preference, UTC. Changing display timezone reuses cached analysis. Changing source mappings triggers a rescan. The offline HTML evidence timeline offers a timezone input; it changes dates, histogram and date filters locally, without changing exports or authored analyst narrative times.

For a known local export, use `--source-timezone 'shellbags.*=America/Los_Angeles'` or a specific `FAMILY.FIELD=ZONE`. Repeated options and wildcards are supported; an explicit offset in the original timestamp always wins. Mapping a whole family is an analyst assertion, not automatic detection. Source timezone cannot be inferred from the analyst computer's timezone. Unknown plugin fields remain untimed. DST repeated hours and missing hours remain untimed until an offset is supplied. Prefer IANA names over PST/EST abbreviations so historical daylight saving rules apply.

Timeline JSONL/CSV retain timestamp_utc, timestamp_raw, timezone_basis and add timestamp_display/display_timezone. Triage JSON keeps first_utc/last_utc for machine correlation; Markdown displays the selected zone. Start/end CLI bounds still require explicit offsets.
