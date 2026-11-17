"""Offline CLI. It will never overwrite an observation and has no network calls."""
from __future__ import annotations
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from .core import evaluate, verify_receipt, InvalidEvidence


def _reject_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InvalidEvidence(f"duplicate JSON key refused: {key}")
        obj[key] = value
    return obj


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Synthetic-only, read-only causal twin example")
    p.add_argument("input",type=Path,help="synthetic JSON input file")
    p.add_argument("--out",type=Path,required=True,help="new append-only receipt path; must not exist")
    args=p.parse_args(argv)
    tmp=None
    try:
        if args.input.stat().st_size > 128*1024:
            raise InvalidEvidence("input exceeds 128 KiB")
        with args.input.open("r",encoding="utf-8") as f:
            data=json.load(f,object_pairs_hook=_reject_duplicate_keys,parse_constant=lambda x: (_ for _ in ()).throw(InvalidEvidence("nonfinite JSON constant")))
        report=evaluate(data)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        if args.out.exists():
            raise FileExistsError("output path exists; this tool never overwrites")
        fd,tmp=tempfile.mkstemp(prefix=".receipt-",suffix=".tmp",dir=args.out.parent)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(report,f,sort_keys=True,indent=2,allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.link(tmp,args.out) # atomic create-if-absent hard link, no competing writer overwrite
        with args.out.open("r",encoding="utf-8") as f:
            check=json.load(f)
        if not verify_receipt(check):
            raise RuntimeError("receipt readback mismatch")
        print(f"{report['decision']['state']}  receipt_sha256={report['receipt_sha256']}")
        print(f"saved={args.out}")
        return 0
    except (OSError,ValueError,TypeError,InvalidEvidence,RuntimeError) as e:
        print(f"REFUSED: {e}",file=sys.stderr)
        return 2
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


if __name__=="__main__":
    raise SystemExit(main())
