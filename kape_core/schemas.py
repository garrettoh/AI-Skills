PROFILES = [
 ("evtx","ez-evtx-parser",{"EventId","TimeCreated","Provider"},["TimeCreated"]),
 ("prefetch","ez-prefetch-parser",{"ExecutableName","RunCount"},["LastRun"]+["LastRun"+str(i) for i in range(8)]),
 ("amcache-files","ez-prefetch-parser",{"SHA1","FullPath","FileKeyLastWriteTimestamp"},["FileKeyLastWriteTimestamp","LinkDate"]),
 ("appcompat","ez-prefetch-parser",{"CacheEntryPosition","LastModifiedTimeUTC","Path"},["LastModifiedTimeUTC"]),
 ("mft","ez-filesystem-parser",{"EntryNumber","Created0x10","ParentPath"},[v+s for v in ["Created","LastModified","LastRecordChange","LastAccess"] for s in ["0x10","0x30"]]),
 ("usn","ez-filesystem-parser",{"UpdateReasons","UpdateTimestamp","EntryNumber"},["UpdateTimestamp"]),
 ("ntfs-boot","ez-filesystem-parser",{"MftClusterBlockNumber","BytesPerSector"},[]),
 ("ntfs-security","ez-filesystem-parser",{"OwnerSid","DaclAceCount","Hash"},[]),
 ("registry","ez-registry-parser",{"HivePath","KeyPath","ValueData"},["LastWriteTimestamp"]),
 ("registry-detail","ez-registry-parser",{"BatchKeyPath","BatchValueName"},["Timestamp","ExecutionTime","LastExecuted","ExecutedOn","OpenedOn","LastOpened","LastClosed","CreatedOn","LastStart","LastStop","NameKeyLastWrite","ParametersKeyLastWrite","LastLoginTime","LastPasswordChange","LastIncorrectPassword","LastDectectionTime","FirstConnectLOCAL","LastConnectedLOCAL"]),
 ("srum","ez-srum-parser",{"ExeInfo","Sid","Timestamp","AppId"},["Timestamp","ConnectStartTime","StartTime","EndTime","EventTimestamp"]),
 ("recycle-bin","ez-recyclebin-parser",{"SourceName","FileName","DeletedOn"},["DeletedOn"]),
 ("shellbags","ez-fileaccess-parser",{"BagPath","ShellType","AbsolutePath"},["FirstInteracted","LastInteracted","LastWriteTime","CreatedOn","ModifiedOn","AccessedOn"]),
 ("jumplist-auto","ez-fileaccess-parser",{"AppId","InteractionCount","TargetCreated"},["CreationTime","LastModified","TargetCreated","TargetModified","TargetAccessed","SourceCreated","SourceModified","SourceAccessed"]),
 ("jumplist-custom","ez-fileaccess-parser",{"AppId","EntryName","TargetCreated"},["TargetCreated","TargetModified","TargetAccessed","SourceCreated","SourceModified","SourceAccessed"]),
 ("shortcut","ez-fileaccess-parser",{"TargetCreated","TargetIDAbsolutePath","HeaderFlags"},["TargetCreated","TargetModified","TargetAccessed","SourceCreated","SourceModified","SourceAccessed"]),
 ("activity","ez-activity-parser",{"ActivityType","Executable","StartTime"},["StartTime","EndTime","LastModifiedTime","LastModifiedOnClient"]),
 ("activity-packages","ez-activity-parser",{"Platform","AdditionalInformation","Expires"},["Expires"])
]
def classify(headers,filename=""):
 h=set(headers)
 for family,skill,required,times in PROFILES:
  if required<=h:
   return dict(family=family,skill=skill,basis="header signature",time_fields=[t for t in times if t in h])
 if "amcache" in filename.lower() and ("KeyLastWriteTimestamp" in h or "ProgramId" in h):
  return dict(family="amcache-metadata",skill="ez-prefetch-parser",basis="filename plus metadata columns",time_fields=[t for t in ["KeyLastWriteTimestamp","InstallDate"] if t in h])
 return dict(family="unknown",skill=None,basis="no supported signature",time_fields=[])
