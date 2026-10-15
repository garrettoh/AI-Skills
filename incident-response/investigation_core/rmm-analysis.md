# Remote management software analysis

Use this guide when parsed Windows evidence contains remote-management or remote-support software, or when persistence beyond the suspected malware is in scope. RMM products are dual-use. Separate installation/persistence from actual remote sessions and operator identity.

## Automated triage

The main investigation-orchestrator command runs RMM discovery within its normal source scan. Users provide their evidence folders once; separate RMM commands are unnecessary. The standalone commands below are optional diagnostics for a specific CSV or extraction issue.

From `incident-response` in the repository or the installed skills root, scan one EvtxECmd CSV or the complete KAPE parse directory:

```powershell
python investigation_core/rmm_triage.py "C:\case\DRDIN_KAPE\parse\EventLogs\EvtxECmd_Output.csv"
python investigation_core/rmm_triage.py "C:\case\DRDIN_KAPE\parse" --output "C:\case-output\rmm-indicators.jsonl"
```

The helper streams CSV rows and writes JSONL to stdout by default. `--output` must be outside the evidence root. It reports tool, evidence category, source path, logical CSV record (header is row 1), EVTX event ID/time, host/user, extracted endpoint domains/IPs, product identifiers, service/path clues, matched fields and bounded evidence excerpts. It does not open or contact extracted endpoints. Review raw source rows for interpretation; a keyword match is a pivot, not a verdict. Review the error summary and verify the expected input files were scanned.

## ScreenConnect / ConnectWise Control

Search installation directories and parsed EvtxECmd output for `ScreenConnect`, `ScreenConnect.ClientService.exe`, `ScreenConnect.WindowsClient.exe`, service installation events 7045/4697, and application records for “Network connection to host created successfully”, “Session connected” and “Session disconnected”. Extract the host from `Relay Server: relay://...`, installer service command arguments such as `h=<host>`, and explicit relay/server URLs. Correlate the host, service GUID, client version, executable path, instance fingerprint and session actor across records.

- A host under `*.screenconnect.com`, commonly `instance-…-relay.screenconnect.com`, indicates a vendor-hosted relay. Use **medium-priority review** as the default: establish whether the tenant, client GUID and session are approved.
- A custom tenant or self-hosted domain/IP should receive **high-priority review**. If it is not on the organization's approved support list, treat it as likely unauthorized/malicious until explained. A custom domain alone is not proof; verify ownership, tickets, client GUID and session activity.
- Installation as an auto-start LocalSystem service establishes persistence capability, not a remote session. A connection/session event establishes observed connectivity, not what the operator did. Check for logs showing install time, service state, network flow, interactive user, process activity and follow-on commands.
- Installer download location, version resource strings, and ClickOnce/AppData paths are useful identity clues. Do not infer hosting ownership from a product filename or signer alone.

## Splashtop

Pivot on `Splashtop Streamer`, `Splashtop SOS`, `SRServer.exe`, `SRService.exe`, `SRManager.exe`, `SRAppPB.exe`, and `SRAgent.exe`. Review service installation and startup events, service registry keys, uninstall records, Amcache/AppCompatCache/Prefetch, user activity and application/network events.

When those artifacts are available, inspect Splashtop registry values and logs for `CSRSOwner`, `CSRSTeamName`, `DCode`, `Client_IP`, `Client_SPID`, `DeviceName` and `UDID`. The live Windows log commonly resides at `C:\Program Files (x86)\Splashtop\Splashtop Remote\Server\log\SPLog.txt`; in a forensic collection, analyze only an acquired copy or parsed export. Search the log for connection/authentication/session events, relay/server hostnames, IPs, account/team identifiers and SPID. Treat SPID/UDID as correlation identifiers, not user identity or a maliciousness verdict.

The reference collection script that queries live services, registry and files is not an offline forensic parser. Do not run it against the evidence machine or mount. Map its source locations and value names to acquired registry hives, event logs and files; preserve timestamps and provenance.

## BeyondTrust / Bomgar and other RMM

Search for `BeyondTrust`, `Bomgar`, `bomgar-scc`, `Jump Client`, tenant/site names, auto-start services and their image paths. Extract any support hostname from the service name, installation path, command line, and product logs. Other common pivots include AnyDesk, TeamViewer, RustDesk/MeshAgent, ScreenConnect/ConnectWise, Splashtop, Atera, SimpleHelp, LogMeIn/GoTo, Zoho Assist and NinjaOne.

For each product, record:

1. First/last evidence and whether dates are file metadata, registry write, event time or execution evidence.
2. Service/task name, start type, account, image path and installation/update events.
3. Tenant/domain/IP, client or device ID, displayed operator, session connect/disconnect times and network destination when present.
4. Evidence of actual use, such as application connection logs, process execution, user activity or network flow. A service crash/restart loop is not proof of an active operator.
5. Whether the host, identity and tool are approved by the organization. Compare with help-desk records and vendor inventory before attributing persistence to an intruder.

Mask temporary tokens, signed URL query values, passwords and cryptographic blobs when quoting command lines or logs. Keep exact source citations in the analyst record while limiting sensitive material in user-facing summaries.
