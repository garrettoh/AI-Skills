"""Verify automatic acquisition-folder placement and exact output overrides."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from investigation_core.output_paths import infer_artifact_parent, configured_destination

with tempfile.TemporaryDirectory(prefix='output-layout-') as temp:
 root=Path(temp)/'Tenant A'/'HOST01_20261015_0840'
 kape=root/'HOST01_KAPE'/'parse'; hindsight=root/'Hindsight_Manual_Drops'
 kape.mkdir(parents=True);hindsight.mkdir()
 assert infer_artifact_parent({'kape':str(kape),'hindsight':str(hindsight)})==root
 assert infer_artifact_parent({'kape':str(kape)})==root
 assert infer_artifact_parent({'hindsight':str(hindsight)})==root
 assert infer_artifact_parent({'kape':str(root/'parsed-csvs'),'hindsight':str(root/'browser-jsonl')}) is None
 args=argparse.Namespace(case='incident',output_root=None,output_directory=None)
 assert configured_destination(args,{'kape':str(kape),'hindsight':str(hindsight)})==root/'agent_output'
 args.output_directory=str(Path(temp)/'fixed-output')
 assert configured_destination(args,{'kape':str(kape)})==Path(args.output_directory)
 args.output_directory=None;args.output_root=str(Path(temp)/'legacy')
 assert configured_destination(args,{'kape':str(kape)})==Path(temp)/'legacy'/'incident'
 # Unrecognized single-root evidence falls back to the existing case layout.
 args.output_root=None
 cwd=Path.cwd()
 try:
  os.chdir(temp)
  assert configured_destination(args,{'kape':str(root/'parsed-csvs')})==Path(temp)/'agent_output'/'incident'
 finally:os.chdir(cwd)
print('PASS: KAPE/Hindsight siblings, KAPE-only, Hindsight-only, exact override, legacy root and generic evidence fallback')
