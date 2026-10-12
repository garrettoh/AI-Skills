# Artifact routing

- ez-evtx-parser: Hunt EvtxECmd CSV exports for event IDs, processes, users, hosts, IPs and IOCs.
- ez-prefetch-parser: Hunt PECmd Prefetch, Amcache and AppCompatCache CSV exports for executable and hash pivots.
- ez-registry-parser: Hunt RECmd batch and plugin CSV exports for persistence, run keys, services, tasks and users.
- ez-filesystem-parser: Hunt MFTECmd MFT, USN, boot and security CSV exports for file, ADS and deletion pivots.
- ez-fileaccess-parser: Hunt LECmd shortcuts, jump lists and SBECmd ShellBags CSV exports for file and folder access pivots.
- ez-srum-parser: Hunt SrumECmd CSV exports for application, user, network volume and resource usage pivots.
- ez-recyclebin-parser: Hunt RBCmd CSV exports for deleted file paths, sizes and deletion timestamps.
- ez-activity-parser: Hunt parsed Windows Activity and package-ID CSV exports for activity and executable pivots.

Header signatures take precedence. RECmd plugin details remain registry exports even when they contain execution/access evidence. Unknown schemas can be searched but cannot supply timeline fields until a verified profile is added.

PECmd discovery is header-based under ProgramExecution/ProgramExecution1 or any nested folder. Detailed rows provide LastRun and PreviousRun0–6; flattened rows provide RunTime. Both route to ez-prefetch-parser. Avoid treating companion exports as independent execution counts; select one export per acquisition when counting runs.
